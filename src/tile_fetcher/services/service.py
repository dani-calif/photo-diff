from __future__ import annotations

import asyncio
import base64
import logging
import math
from io import BytesIO
from typing import Sequence, TypeVar

from PIL import Image

from tile_fetcher.constants import DEFAULT_ROTATION_SAFE_EXPAND_FACTOR
from tile_fetcher.services.models import GeoPoint, PixelBBox, PixelPoint
from tile_fetcher.utils import ImageProviderClient, ProjectionMapperClient

logger = logging.getLogger("tile-fetcher.service")
T = TypeVar("T")


class TileFetchService:
    def __init__(
        self,
        *,
        image_provider: ImageProviderClient,
        projection_mapper: ProjectionMapperClient,
        timeout_seconds: float,
        expand_factor: float = DEFAULT_ROTATION_SAFE_EXPAND_FACTOR,
    ) -> None:
        if expand_factor <= 1.0:
            raise ValueError("tile expand factor must be greater than 1.0.")
        self._image_provider = image_provider
        self._projection_mapper = projection_mapper
        self._timeout_seconds = timeout_seconds
        self._expand_factor = expand_factor

    async def fetch_tiles_at_point_as_base64(
        self,
        *,
        image_ids: Sequence[str],
        lon: float,
        lat: float,
        buffer_size_meters: float,
        north_aligned: bool = True,
    ) -> list[str]:
        if not image_ids:
            raise ValueError("image_ids cannot be empty.")
        if buffer_size_meters <= 0.0:
            raise ValueError("buffer_size_meters must be greater than 0.")

        logger.info(
            "fetching tiles",
            extra={
                "image_ids_count": len(image_ids),
                "lon": lon,
                "lat": lat,
                "buffer_size_meters": buffer_size_meters,
                "north_aligned": north_aligned,
            },
        )

        output: list[str] = []
        for raw_image_id in image_ids:
            image_id = raw_image_id.strip()
            if not image_id:
                raise ValueError("image_ids must contain only non-empty strings.")

            aligned_bytes = await self._fetch_image_bytes_for_id(
                image_id=image_id,
                center=GeoPoint(lon=lon, lat=lat),
                buffer_size_meters=buffer_size_meters,
                north_aligned=north_aligned,
            )
            output.append(base64.b64encode(aligned_bytes).decode("ascii"))

        logger.info("fetched tiles", extra={"image_ids_count": len(output)})
        return output

    async def _fetch_image_bytes_for_id(
        self,
        *,
        image_id: str,
        center: GeoPoint,
        buffer_size_meters: float,
        north_aligned: bool,
    ) -> bytes:
        tile = await self._image_provider.resolve_tile_for_point(
            image_id,
            center,
            self._timeout_seconds,
        )
        pixel_center = await self._resolve_pixel_center(image_id=image_id, center=center)
        target_bbox = await self._build_target_bbox(
            image_id=image_id,
            center=center,
            pixel_center=pixel_center,
            buffer_size_meters=buffer_size_meters,
        )

        expand_factor = self._expand_factor
        if north_aligned:
            expand_factor = max(expand_factor, DEFAULT_ROTATION_SAFE_EXPAND_FACTOR)
        expanded_bbox = target_bbox.expand(expand_factor)

        logger.info(
            "fetching tile image",
            extra={
                "image_id": image_id,
                "tile_azimuth": tile.azimuth,
                "buffer_size_meters": buffer_size_meters,
                "target_bbox": target_bbox.to_string(),
                "expanded_bbox": expanded_bbox.to_string(),
            },
        )
        provider_image = await self._image_provider.fetch_image(
            image_id,
            expanded_bbox,
            self._timeout_seconds,
        )
        return await asyncio.to_thread(
            _crop_with_optional_alignment,
            provider_image.image_bytes,
            provider_image.azimuth,
            target_bbox,
            expanded_bbox,
            north_aligned,
        )

    async def _build_target_bbox(
        self,
        *,
        image_id: str,
        center: GeoPoint,
        pixel_center: PixelPoint,
        buffer_size_meters: float,
    ) -> PixelBBox:
        x_neighbor, y_neighbor = await self._resolve_geo_points(
            image_id=image_id,
            pixels=[
                PixelPoint(x=pixel_center.x + 1.0, y=pixel_center.y),
                PixelPoint(x=pixel_center.x, y=pixel_center.y + 1.0),
            ],
        )
        x_resolution = _meters_between(center, x_neighbor)
        y_resolution = _meters_between(center, y_neighbor)
        if x_resolution <= 0.0 or y_resolution <= 0.0:
            raise ValueError(f"Could not calculate pixel resolution for image_id '{image_id}'.")

        return PixelBBox.around(
            pixel_center,
            half_width=buffer_size_meters / x_resolution,
            half_height=buffer_size_meters / y_resolution,
        )

    async def _resolve_pixel_center(self, *, image_id: str, center: GeoPoint) -> PixelPoint:
        pixels = await self._projection_mapper.geo_to_pixel_points(
            image_id,
            [center],
            self._timeout_seconds,
        )
        return _require_single_item(pixels, f"geo_to_pixel_points for '{image_id}'")

    async def _resolve_geo_points(
        self,
        *,
        image_id: str,
        pixels: Sequence[PixelPoint],
    ) -> tuple[GeoPoint, GeoPoint]:
        geo_points = await self._projection_mapper.pixel_to_geo_points(
            image_id,
            pixels,
            self._timeout_seconds,
        )
        if len(geo_points) != 2:
            raise ValueError(f"pixel_to_geo_points for '{image_id}' must return 2 items.")
        return geo_points[0], geo_points[1]


def _crop_with_optional_alignment(
    source_image_bytes: bytes,
    azimuth_degrees: float,
    target_bbox: PixelBBox,
    expanded_bbox: PixelBBox,
    north_aligned: bool,
) -> bytes:
    rotation_degrees = -azimuth_degrees if north_aligned else 0.0
    return _rotate_and_center_crop(
        source_image_bytes=source_image_bytes,
        rotation_degrees=rotation_degrees,
        width_ratio=target_bbox.width / expanded_bbox.width,
        height_ratio=target_bbox.height / expanded_bbox.height,
    )


def _rotate_and_center_crop(
    *,
    source_image_bytes: bytes,
    rotation_degrees: float,
    width_ratio: float,
    height_ratio: float,
) -> bytes:
    with Image.open(BytesIO(source_image_bytes)) as source_image:
        rotated = source_image.convert("RGB").rotate(
            rotation_degrees,
            resample=Image.Resampling.BICUBIC,
            expand=True,
        )

    crop_width = min(max(1, int(round(rotated.width * width_ratio))), rotated.width)
    crop_height = min(max(1, int(round(rotated.height * height_ratio))), rotated.height)
    left, top, right, bottom = _center_crop_box(
        width=rotated.width,
        height=rotated.height,
        crop_width=crop_width,
        crop_height=crop_height,
    )
    cropped = rotated.crop((left, top, right, bottom))
    out = BytesIO()
    cropped.save(out, format="PNG")
    return out.getvalue()


def _center_crop_box(
    *,
    width: int,
    height: int,
    crop_width: int,
    crop_height: int,
) -> tuple[int, int, int, int]:
    center_x = width / 2.0
    center_y = height / 2.0
    left = int(round(center_x - crop_width / 2.0))
    top = int(round(center_y - crop_height / 2.0))
    left = max(0, min(left, width - crop_width))
    top = max(0, min(top, height - crop_height))
    return left, top, left + crop_width, top + crop_height


def _meters_between(point_a: GeoPoint, point_b: GeoPoint) -> float:
    earth_radius_meters = 6_371_000.0
    lat1 = math.radians(point_a.lat)
    lat2 = math.radians(point_b.lat)
    delta_lat = math.radians(point_b.lat - point_a.lat)
    delta_lon = math.radians(point_b.lon - point_a.lon)

    sin_lat = math.sin(delta_lat / 2.0)
    sin_lon = math.sin(delta_lon / 2.0)
    a = sin_lat * sin_lat + math.cos(lat1) * math.cos(lat2) * sin_lon * sin_lon
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return earth_radius_meters * c


def _require_single_item(items: Sequence[T], context: str) -> T:
    if len(items) != 1:
        raise ValueError(f"{context} must return exactly 1 item.")
    return items[0]
