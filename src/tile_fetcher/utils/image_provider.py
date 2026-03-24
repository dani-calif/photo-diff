from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Mapping, Protocol

from pydantic import BaseModel, Field
from shapely.geometry import Point
from tile_fetcher.errors import TileFetchError
from tile_fetcher.http import HttpClient
from tile_fetcher.services.models import ProviderImage, ResolvedImage, XYXYBox

logger = logging.getLogger(__name__)


class ResolveTileForPointFn(Protocol):
    async def __call__(
        self,
        gid: str,
        point: Point,
        timeout_seconds: float,
    ) -> ResolvedImage:
        ...


class FetchImageFn(Protocol):
    async def __call__(
        self,
        gid: str,
        pixel_bbox: XYXYBox,
        timeout_seconds: float,
    ) -> ProviderImage:
        ...


class ResolveTileQuery(BaseModel):
    image_id: str
    lon: float
    lat: float


class FetchImageQuery(BaseModel):
    image_id: str
    bbox: str


class ResolvedImagePayload(BaseModel):
    image_id: str = Field(min_length=1)
    bbox: str = Field(min_length=1)
    azimuth: float

    def to_domain(self) -> ResolvedImage:
        return ResolvedImage(
            bounds=XYXYBox.from_string(self.bbox),
            azimuth=self.azimuth,
        )


class FetchedImagePayload(BaseModel):
    url: str = Field(min_length=1)
    azimuth: float


@dataclass(slots=True)
class ImageProviderClient:
    resolve_tile_for_point: ResolveTileForPointFn
    fetch_image: FetchImageFn


def build_http_image_provider(
    *,
    api_base_url: str,
    geo_path: str,
    light_path: str,
    http_client: HttpClient,
) -> ImageProviderClient:
    base_url = api_base_url.rstrip("/")

    async def resolve_tile_for_point(gid: str, point: Point, timeout_seconds: float) -> ResolvedImage:
        try:
            response = await http_client.get(
                f"{base_url}{geo_path}",
                timeout=timeout_seconds,
                params=_string_params(
                    ResolveTileQuery(image_id=gid, lon=point.x, lat=point.y)
                ),
            )
            response.raise_for_status()
        except Exception as exc:
            raise TileFetchError(f"Failed to resolve tile for '{gid}': {exc}") from exc

        for candidate in _extract_tile_objects(response.json()):
            resolved_image_payload = ResolvedImagePayload.model_validate(candidate)
            if resolved_image_payload.image_id == gid:
                resolved_image = resolved_image_payload.to_domain()
                logger.info(
                    "resolved tile",
                    extra={
                        "gid": gid,
                        "bbox_width": resolved_image.bounds.width,
                        "bbox_height": resolved_image.bounds.height,
                        "azimuth": resolved_image.azimuth,
                    },
                )
                return resolved_image

        raise ValueError(f"No wms/geo tile found for gid '{gid}'.")

    async def fetch_image(gid: str, pixel_bbox: XYXYBox, timeout_seconds: float) -> ProviderImage:
        try:
            response = await http_client.get(
                f"{base_url}{light_path}",
                timeout=timeout_seconds,
                params=_string_params(
                    FetchImageQuery(image_id=gid, bbox=pixel_bbox.to_string())
                ),
            )
            response.raise_for_status()
        except Exception as exc:
            raise TileFetchError(f"Failed to fetch source image for '{gid}': {exc}") from exc

        fetched_image = FetchedImagePayload.model_validate(
            _extract_first_object(response.json(), "wms/light response")
        )

        try:
            image_response = await http_client.get(fetched_image.url, timeout=timeout_seconds)
            image_response.raise_for_status()
        except Exception as exc:
            raise TileFetchError(f"Failed to download source image for '{gid}': {exc}") from exc

        return ProviderImage(
            image_bytes=image_response.content,
            azimuth=fetched_image.azimuth,
        )

    return ImageProviderClient(
        resolve_tile_for_point=resolve_tile_for_point,
        fetch_image=fetch_image,
    )


def extract_first_object(body: Any, context: str) -> Mapping[str, Any]:
    return _extract_first_object(body, context)


def _extract_first_object(body: Any, context: str) -> Mapping[str, Any]:
    if isinstance(body, Mapping):
        if "data" not in body:
            return body

        data = body["data"]
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
        if "data" in body and isinstance(body["data"], list):
            candidates = body["data"]
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


def _string_params(model: BaseModel) -> dict[str, str]:
    return {key: str(value) for key, value in model.model_dump().items()}
