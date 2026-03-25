from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO

from PIL import Image, ImageDraw, ImageFont
from tile_fetcher.services.models import ProviderImage, XYXYBox
from tile_fetcher.settings import TileFetcherSettings
from tile_fetcher.utils import ImageProviderClient

FONT = ImageFont.load_default()


@dataclass(slots=True)
class MockInternalImageProvider:
    async def fetch_image(
        self,
        gid: str,
        pixel_bbox: XYXYBox,
        timeout_seconds: float,
    ) -> ProviderImage:
        del timeout_seconds
        return ProviderImage(
            image_bytes=_render_image(
                gid=gid,
                width=max(1, int(round(pixel_bbox.width))),
                height=max(1, int(round(pixel_bbox.height))),
                label=f"bbox {pixel_bbox.to_string()}",
            ),
            pixel_bbox=pixel_bbox,
        )

    async def strip_pixel_bbox(
        self,
        gid: str,
        pixel_bbox: XYXYBox,
        timeout_seconds: float,
    ) -> bytes:
        del timeout_seconds
        return _render_image(
            gid=gid,
            width=max(1, int(round(pixel_bbox.width))),
            height=max(1, int(round(pixel_bbox.height))),
            label=f"pixel {pixel_bbox.to_string()}",
        )

    async def strip_rotation_by_view_angle_pixel(
        self,
        gid: str,
        x_center_pixel: int,
        y_center_pixel: float,
        tile_size_pixels: float,
        max_output_width: int,
        max_output_height: int,
        timeout_seconds: float,
    ) -> bytes:
        del timeout_seconds
        return _render_image(
            gid=gid,
            width=max(1, max_output_width),
            height=max(1, max_output_height),
            label=(
                f"pixel center=({x_center_pixel},{y_center_pixel}) "
                f"size={tile_size_pixels}"
            ),
        )

    async def strip_rotation_by_view_angle_geo(
        self,
        gid: str,
        x_center_geo: float,
        y_center_geo: float,
        tile_size_meters: int,
        max_output_width: int,
        max_output_height: int,
        timeout_seconds: float,
    ) -> bytes:
        del timeout_seconds
        return _render_image(
            gid=gid,
            width=max(1, max_output_width),
            height=max(1, max_output_height),
            label=f"geo center=({x_center_geo},{y_center_geo}) size={tile_size_meters}",
        )


def build_image_provider(settings: TileFetcherSettings) -> ImageProviderClient:
    del settings
    provider = MockInternalImageProvider()
    return ImageProviderClient(
        fetch_image=provider.fetch_image,
        strip_pixel_bbox=provider.strip_pixel_bbox,
        strip_rotation_by_view_angle_pixel=provider.strip_rotation_by_view_angle_pixel,
        strip_rotation_by_view_angle_geo=provider.strip_rotation_by_view_angle_geo,
    )


def _render_image(*, gid: str, width: int, height: int, label: str) -> bytes:
    image = Image.new("RGB", (width, height), color=(238, 243, 247))
    draw = ImageDraw.Draw(image)
    draw.rectangle((0, 0, width - 1, height - 1), outline=(36, 53, 71), width=2)
    draw.text((10, 10), gid, fill=(16, 24, 32), font=FONT)
    draw.text((10, 28), label, fill=(16, 24, 32), font=FONT)

    out = BytesIO()
    image.save(out, format="PNG")
    return out.getvalue()
