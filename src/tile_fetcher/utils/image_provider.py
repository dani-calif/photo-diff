from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Mapping

from tile_fetcher.constants import (
    KEY_AZIMUTH,
    KEY_BBOX,
    KEY_DATA,
    KEY_IMAGE_ID,
    KEY_LAT,
    KEY_LON,
    KEY_URL,
)
from tile_fetcher.errors import TileFetchError
from tile_fetcher.http import HttpClient
from tile_fetcher.services.models import GeoPoint, ImageTile, PixelBBox, ProviderImage

logger = logging.getLogger("tile-fetcher.image-provider")


@dataclass(slots=True)
class ImageProviderClient:
    resolve_tile_for_point: Callable[[str, GeoPoint, float], Awaitable[ImageTile]]
    fetch_image: Callable[[str, PixelBBox, float], Awaitable[ProviderImage]]


def build_http_image_provider(
    *,
    api_base_url: str,
    geo_path: str,
    light_path: str,
    http_client: HttpClient,
) -> ImageProviderClient:
    base_url = api_base_url.rstrip("/")

    async def resolve_tile_for_point(gid: str, point: GeoPoint, timeout_seconds: float) -> ImageTile:
        try:
            response = await http_client.get(
                f"{base_url}{geo_path}",
                timeout=timeout_seconds,
                params={
                    KEY_IMAGE_ID: gid,
                    KEY_LON: str(point.lon),
                    KEY_LAT: str(point.lat),
                },
            )
            response.raise_for_status()
        except Exception as exc:
            raise TileFetchError(f"Failed to resolve tile for '{gid}': {exc}") from exc

        for candidate in _extract_tile_objects(response.json()):
            if str(candidate[KEY_IMAGE_ID]) == gid:
                tile = ImageTile.from_mapping(candidate)
                logger.info(
                    "resolved tile",
                    extra={
                        "gid": tile.image_id,
                        "bbox_width": tile.bbox.width,
                        "bbox_height": tile.bbox.height,
                        "azimuth": tile.azimuth,
                    },
                )
                return tile

        raise ValueError(f"No wms/geo tile found for gid '{gid}'.")

    async def fetch_image(gid: str, pixel_bbox: PixelBBox, timeout_seconds: float) -> ProviderImage:
        try:
            response = await http_client.get(
                f"{base_url}{light_path}",
                timeout=timeout_seconds,
                params={
                    KEY_IMAGE_ID: gid,
                    KEY_BBOX: pixel_bbox.to_string(),
                },
            )
            response.raise_for_status()
        except Exception as exc:
            raise TileFetchError(f"Failed to fetch source image for '{gid}': {exc}") from exc

        candidate = _extract_first_object(response.json(), "wms/light response")
        source_url = str(candidate[KEY_URL]).strip()
        if not source_url:
            raise ValueError("wms/light response must include non-empty url.")

        try:
            image_response = await http_client.get(source_url, timeout=timeout_seconds)
            image_response.raise_for_status()
        except Exception as exc:
            raise TileFetchError(f"Failed to download source image for '{gid}': {exc}") from exc

        return ProviderImage(
            image_bytes=image_response.content,
            azimuth=float(candidate[KEY_AZIMUTH]),
        )

    return ImageProviderClient(
        resolve_tile_for_point=resolve_tile_for_point,
        fetch_image=fetch_image,
    )


def extract_first_object(body: Any, context: str) -> Mapping[str, Any]:
    return _extract_first_object(body, context)


def _extract_first_object(body: Any, context: str) -> Mapping[str, Any]:
    if isinstance(body, Mapping):
        if KEY_DATA not in body:
            return body

        data = body[KEY_DATA]
        if isinstance(data, Mapping):
            return data
        if isinstance(data, list):
            if not data:
                raise ValueError(f"{context} data list is empty.")
            first = data[0]
            if isinstance(first, Mapping):
                return first
            raise ValueError(f"{context} data item must be a JSON object.")
        raise ValueError(f"{context} data field must be object or list.")

    if isinstance(body, list):
        if not body:
            raise ValueError(f"{context} list is empty.")
        first = body[0]
        if isinstance(first, Mapping):
            return first
        raise ValueError(f"{context} list item must be a JSON object.")

    raise ValueError(f"{context} must be an object or list of objects.")


def _extract_tile_objects(body: Any) -> list[Mapping[str, Any]]:
    if isinstance(body, list):
        candidates = body
    elif isinstance(body, Mapping):
        if KEY_DATA in body and isinstance(body[KEY_DATA], list):
            candidates = body[KEY_DATA]
        else:
            candidates = [body]
    else:
        raise ValueError("wms/geo response must be an object or list.")

    if not candidates:
        raise ValueError("wms/geo response does not contain tile candidates.")

    objects: list[Mapping[str, Any]] = []
    for item in candidates:
        if not isinstance(item, Mapping):
            raise ValueError("wms/geo response candidates must be JSON objects.")
        objects.append(item)
    return objects
