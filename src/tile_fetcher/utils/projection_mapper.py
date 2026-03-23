from __future__ import annotations

from dataclasses import dataclass
from typing import Awaitable, Callable, Sequence

from tile_fetcher.constants import KEY_IMAGE_ID, KEY_LAT, KEY_LON, KEY_X, KEY_Y
from tile_fetcher.errors import TileFetchError
from tile_fetcher.http import HttpClient
from tile_fetcher.services.models import GeoPoint, PixelPoint
from tile_fetcher.utils.image_provider import extract_first_object


@dataclass(slots=True)
class ProjectionMapperClient:
    geo_to_pixel_points: Callable[[str, Sequence[GeoPoint], float], Awaitable[list[PixelPoint]]]
    pixel_to_geo_points: Callable[[str, Sequence[PixelPoint], float], Awaitable[list[GeoPoint]]]


def build_http_projection_mapper(
    *,
    api_base_url: str,
    g2i_path: str,
    i2g_path: str,
    http_client: HttpClient,
) -> ProjectionMapperClient:
    base_url = api_base_url.rstrip("/")

    async def geo_to_pixel_points(
        gid: str,
        points: Sequence[GeoPoint],
        timeout_seconds: float,
    ) -> list[PixelPoint]:
        pixels: list[PixelPoint] = []
        for point in points:
            try:
                response = await http_client.get(
                    f"{base_url}{g2i_path}",
                    timeout=timeout_seconds,
                    params={
                        KEY_IMAGE_ID: gid,
                        KEY_LON: str(point.lon),
                        KEY_LAT: str(point.lat),
                    },
                )
                response.raise_for_status()
            except Exception as exc:
                raise TileFetchError(
                    f"Failed to map geo point to pixel for '{gid}': {exc}"
                ) from exc

            pixels.append(
                PixelPoint.from_mapping(extract_first_object(response.json(), "g2i response"))
            )
        return pixels

    async def pixel_to_geo_points(
        gid: str,
        points: Sequence[PixelPoint],
        timeout_seconds: float,
    ) -> list[GeoPoint]:
        geo_points: list[GeoPoint] = []
        for point in points:
            try:
                response = await http_client.get(
                    f"{base_url}{i2g_path}",
                    timeout=timeout_seconds,
                    params={
                        KEY_IMAGE_ID: gid,
                        KEY_X: str(point.x),
                        KEY_Y: str(point.y),
                    },
                )
                response.raise_for_status()
            except Exception as exc:
                raise TileFetchError(
                    f"Failed to map pixel to geo point for '{gid}': {exc}"
                ) from exc

            geo_points.append(
                GeoPoint.from_mapping(extract_first_object(response.json(), "i2g response"))
            )
        return geo_points

    return ProjectionMapperClient(
        geo_to_pixel_points=geo_to_pixel_points,
        pixel_to_geo_points=pixel_to_geo_points,
    )
