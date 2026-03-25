from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from shapely.geometry import Point
from tile_fetcher.settings import TileFetcherSettings
from tile_fetcher.utils import ProjectionMapperClient


@dataclass(slots=True)
class MockInternalProjectionMapper:
    async def geo_to_pixel_points(
        self,
        gid: str,
        points: Sequence[Point],
        timeout_seconds: float,
    ) -> list[Point]:
        del timeout_seconds
        offset = float(sum(ord(char) for char in gid) % 1000)
        return [
            Point((point.x * 10_000.0) + offset, (point.y * 10_000.0) + offset)
            for point in points
        ]


def build_projection_mapper(settings: TileFetcherSettings) -> ProjectionMapperClient:
    del settings
    mapper = MockInternalProjectionMapper()
    return ProjectionMapperClient(geo_to_pixel_points=mapper.geo_to_pixel_points)
