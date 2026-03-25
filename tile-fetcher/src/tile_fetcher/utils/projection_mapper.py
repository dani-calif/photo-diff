from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, Sequence

from shapely.geometry import Point

class GeoToPixelPointsFn(Protocol):
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
