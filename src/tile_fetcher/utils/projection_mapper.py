from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, Sequence

from pydantic import BaseModel
from shapely.geometry import Point
from tile_fetcher.errors import TileFetchError
from tile_fetcher.http import HttpClient
from tile_fetcher.utils.image_provider import extract_first_object


class GeoToPixelPointsFn(Protocol):
    async def __call__(
        self,
        gid: str,
        points: Sequence[Point],
        timeout_seconds: float,
    ) -> list[Point]:
        ...


class PixelToGeoPointsFn(Protocol):
    async def __call__(
        self,
        gid: str,
        points: Sequence[Point],
        timeout_seconds: float,
    ) -> list[Point]:
        ...


@dataclass(slots=True)
class ProjectionMapperClient:
    geo_to_pixel_points: GeoToPixelPointsFn
    pixel_to_geo_points: PixelToGeoPointsFn


class GeoToPixelQuery(BaseModel):
    image_id: str
    lon: float
    lat: float


class PixelToGeoQuery(BaseModel):
    image_id: str
    x: float
    y: float


class GeoPointPayload(BaseModel):
    lon: float
    lat: float

    def to_point(self) -> Point:
        return Point(self.lon, self.lat)


class PixelPointPayload(BaseModel):
    x: float
    y: float

    def to_point(self) -> Point:
        return Point(self.x, self.y)


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
        points: Sequence[Point],
        timeout_seconds: float,
    ) -> list[Point]:
        pixels: list[Point] = []
        for point in points:
            try:
                response = await http_client.get(
                    f"{base_url}{g2i_path}",
                    timeout=timeout_seconds,
                    params=_string_params(
                        GeoToPixelQuery(image_id=gid, lon=point.x, lat=point.y)
                    ),
                )
                response.raise_for_status()
            except Exception as exc:
                raise TileFetchError(
                    f"Failed to map geo point to pixel for '{gid}': {exc}"
                ) from exc

            pixels.append(
                PixelPointPayload.model_validate(
                    extract_first_object(response.json(), "g2i response")
                ).to_point()
            )
        return pixels

    async def pixel_to_geo_points(
        gid: str,
        points: Sequence[Point],
        timeout_seconds: float,
    ) -> list[Point]:
        geo_points: list[Point] = []
        for point in points:
            try:
                response = await http_client.get(
                    f"{base_url}{i2g_path}",
                    timeout=timeout_seconds,
                    params=_string_params(
                        PixelToGeoQuery(image_id=gid, x=point.x, y=point.y)
                    ),
                )
                response.raise_for_status()
            except Exception as exc:
                raise TileFetchError(
                    f"Failed to map pixel to geo point for '{gid}': {exc}"
                ) from exc

            geo_points.append(
                GeoPointPayload.model_validate(
                    extract_first_object(response.json(), "i2g response")
                ).to_point()
            )
        return geo_points

    return ProjectionMapperClient(
        geo_to_pixel_points=geo_to_pixel_points,
        pixel_to_geo_points=pixel_to_geo_points,
    )


def _string_params(model: BaseModel) -> dict[str, str]:
    return {key: str(value) for key, value in model.model_dump().items()}
