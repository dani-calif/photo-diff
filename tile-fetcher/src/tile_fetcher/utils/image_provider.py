from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from tile_fetcher.services.models import ProviderImage, XYXYBox


class FetchImageFn(Protocol):
    async def __call__(
        self,
        gid: str,
        pixel_bbox: XYXYBox,
        timeout_seconds: float,
    ) -> ProviderImage:
        ...


class StripPixelBboxFn(Protocol):
    async def __call__(
        self,
        gid: str,
        pixel_bbox: XYXYBox,
        timeout_seconds: float,
    ) -> bytes:
        ...


class StripRotationByViewAnglePixelFn(Protocol):
    async def __call__(
        self,
        gid: str,
        x_center_pixel: int,
        y_center_pixel: float,
        tile_size_pixels: float,
        max_output_width: int,
        max_output_height: int,
        timeout_seconds: float,
    ) -> bytes:
        ...


class StripRotationByViewAngleGeoFn(Protocol):
    async def __call__(
        self,
        gid: str,
        x_center_geo: float,
        y_center_geo: float,
        tile_size_meters: int,
        max_output_width: int,
        max_output_height: int,
        timeout_seconds: float,
    ) -> bytes:
        ...


@dataclass(slots=True)
class ImageProviderClient:
    fetch_image: FetchImageFn
    strip_pixel_bbox: StripPixelBboxFn | None = None
    strip_rotation_by_view_angle_pixel: StripRotationByViewAnglePixelFn | None = None
    strip_rotation_by_view_angle_geo: StripRotationByViewAngleGeoFn | None = None
