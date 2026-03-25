from __future__ import annotations

import asyncio
import base64
import logging
import math
from io import BytesIO
from typing import Sequence

from PIL import Image
from pyproj import CRS, Transformer
from shapely.geometry import Point

from tile_fetcher.services.models import PointQuad, XYXYBox
from tile_fetcher.utils import ImageProviderClient, ProjectionMapperClient

logger = logging.getLogger(__name__)


class TileFetchService:
    def __init__(
        self,
        *,
        image_provider: ImageProviderClient,
        projection_mapper: ProjectionMapperClient,
        timeout_seconds: float,
    ) -> None:
        self._image_provider = image_provider
        self._projection_mapper = projection_mapper
        self._timeout_seconds = timeout_seconds

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
                center=Point(lon, lat),
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
        center: Point,
        buffer_size_meters: float,
        north_aligned: bool,
    ) -> bytes:
        geo_quad = _build_geo_quad(center=center, buffer_size_meters=buffer_size_meters)
        pixel_quad = await self._resolve_pixel_quad(image_id=image_id, geo_quad=geo_quad)
        fetch_bbox = pixel_quad.bounding_box

        logger.info(
            "fetching tile image",
            extra={
                "image_id": image_id,
                "buffer_size_meters": buffer_size_meters,
                "target_bbox": fetch_bbox.to_string(),
                "north_aligned": north_aligned,
            },
        )
        provider_image = await self._image_provider.fetch_image(
            image_id,
            fetch_bbox,
            self._timeout_seconds,
        )
        return await asyncio.to_thread(
            _render_tile_crop,
            source_image_bytes=provider_image.image_bytes,
            source_pixel_bbox=provider_image.pixel_bbox,
            target_pixel_quad=pixel_quad,
            target_fetch_bbox=fetch_bbox,
            north_aligned=north_aligned,
        )

    async def _resolve_pixel_quad(
        self,
        *,
        image_id: str,
        geo_quad: PointQuad,
    ) -> PointQuad:
        pixel_points = await self._projection_mapper.geo_to_pixel_points(
            image_id,
            list(geo_quad.points()),
            self._timeout_seconds,
        )
        if len(pixel_points) != 4:
            raise ValueError(f"geo_to_pixel_points for '{image_id}' must return 4 items.")
        return PointQuad(
            upper_left=pixel_points[0],
            lower_left=pixel_points[1],
            lower_right=pixel_points[2],
            upper_right=pixel_points[3],
        )


def _build_geo_quad(*, center: Point, buffer_size_meters: float) -> PointQuad:
    half_size_meters = buffer_size_meters / 2.0
    projected_crs = _local_metric_crs(center)
    to_projected = Transformer.from_crs("EPSG:4326", projected_crs, always_xy=True)
    to_geographic = Transformer.from_crs(projected_crs, "EPSG:4326", always_xy=True)
    center_x, center_y = to_projected.transform(center.x, center.y)

    return PointQuad(
        upper_left=_projected_offset_to_geo(
            center_x=center_x,
            center_y=center_y,
            east_meters=-half_size_meters,
            north_meters=half_size_meters,
            to_geographic=to_geographic,
        ),
        lower_left=_projected_offset_to_geo(
            center_x=center_x,
            center_y=center_y,
            east_meters=-half_size_meters,
            north_meters=-half_size_meters,
            to_geographic=to_geographic,
        ),
        lower_right=_projected_offset_to_geo(
            center_x=center_x,
            center_y=center_y,
            east_meters=half_size_meters,
            north_meters=-half_size_meters,
            to_geographic=to_geographic,
        ),
        upper_right=_projected_offset_to_geo(
            center_x=center_x,
            center_y=center_y,
            east_meters=half_size_meters,
            north_meters=half_size_meters,
            to_geographic=to_geographic,
        ),
    )


def _projected_offset_to_geo(
    *,
    center_x: float,
    center_y: float,
    east_meters: float,
    north_meters: float,
    to_geographic: Transformer,
) -> Point:
    lon, lat = to_geographic.transform(center_x + east_meters, center_y + north_meters)
    return Point(lon, lat)


def _local_metric_crs(point: Point) -> CRS:
    return CRS.from_proj4(
        f"+proj=aeqd +lat_0={point.y} +lon_0={point.x} +datum=WGS84 +units=m +no_defs"
    )


def _render_tile_crop(
    *,
    source_image_bytes: bytes,
    source_pixel_bbox: XYXYBox,
    target_pixel_quad: PointQuad,
    target_fetch_bbox: XYXYBox,
    north_aligned: bool,
) -> bytes:
    if north_aligned:
        return _warp_source_quad_to_square(
            source_image_bytes=source_image_bytes,
            source_pixel_bbox=source_pixel_bbox,
            target_pixel_quad=target_pixel_quad,
        )
    return _crop_source_bbox(
        source_image_bytes=source_image_bytes,
        source_pixel_bbox=source_pixel_bbox,
        target_pixel_bbox=target_fetch_bbox,
    )


def _warp_source_quad_to_square(
    *,
    source_image_bytes: bytes,
    source_pixel_bbox: XYXYBox,
    target_pixel_quad: PointQuad,
) -> bytes:
    with Image.open(BytesIO(source_image_bytes)) as source_image:
        image = source_image.convert("RGB")
        local_quad = _localize_quad(
            quad=target_pixel_quad,
            source_bbox=source_pixel_bbox,
            image_width=image.width,
            image_height=image.height,
        )
        square_size = _square_output_size(local_quad)
        warped = image.transform(
            (square_size, square_size),
            Image.Transform.QUAD,
            data=_quad_transform_data(local_quad),
            resample=Image.Resampling.BICUBIC,
        )
    out = BytesIO()
    warped.save(out, format="PNG")
    return out.getvalue()


def _crop_source_bbox(
    *,
    source_image_bytes: bytes,
    source_pixel_bbox: XYXYBox,
    target_pixel_bbox: XYXYBox,
) -> bytes:
    with Image.open(BytesIO(source_image_bytes)) as source_image:
        image = source_image.convert("RGB")
        left, top = _localize_point(
            point=Point(target_pixel_bbox.xmin, target_pixel_bbox.ymin),
            source_bbox=source_pixel_bbox,
            image_width=image.width,
            image_height=image.height,
        )
        right, bottom = _localize_point(
            point=Point(target_pixel_bbox.xmax, target_pixel_bbox.ymax),
            source_bbox=source_pixel_bbox,
            image_width=image.width,
            image_height=image.height,
        )
        output_width = max(1, int(round(right - left)))
        output_height = max(1, int(round(bottom - top)))
        cropped = image.transform(
            (output_width, output_height),
            Image.Transform.EXTENT,
            data=(left, top, right, bottom),
            resample=Image.Resampling.BICUBIC,
        )
    out = BytesIO()
    cropped.save(out, format="PNG")
    return out.getvalue()


def _localize_quad(
    *,
    quad: PointQuad,
    source_bbox: XYXYBox,
    image_width: int,
    image_height: int,
) -> PointQuad:
    return PointQuad(
        upper_left=_localize_shapely_point(
            point=quad.upper_left,
            source_bbox=source_bbox,
            image_width=image_width,
            image_height=image_height,
        ),
        lower_left=_localize_shapely_point(
            point=quad.lower_left,
            source_bbox=source_bbox,
            image_width=image_width,
            image_height=image_height,
        ),
        lower_right=_localize_shapely_point(
            point=quad.lower_right,
            source_bbox=source_bbox,
            image_width=image_width,
            image_height=image_height,
        ),
        upper_right=_localize_shapely_point(
            point=quad.upper_right,
            source_bbox=source_bbox,
            image_width=image_width,
            image_height=image_height,
        ),
    )


def _localize_point(
    *,
    point: Point,
    source_bbox: XYXYBox,
    image_width: int,
    image_height: int,
) -> tuple[float, float]:
    localized = _localize_shapely_point(
        point=point,
        source_bbox=source_bbox,
        image_width=image_width,
        image_height=image_height,
    )
    return localized.x, localized.y


def _localize_shapely_point(
    *,
    point: Point,
    source_bbox: XYXYBox,
    image_width: int,
    image_height: int,
) -> Point:
    if source_bbox.width <= 0.0 or source_bbox.height <= 0.0:
        raise ValueError("source pixel bbox must define positive area.")
    x = ((point.x - source_bbox.xmin) / source_bbox.width) * image_width
    y = ((point.y - source_bbox.ymin) / source_bbox.height) * image_height
    return Point(x, y)


def _square_output_size(quad: PointQuad) -> int:
    average_width = (
        _distance(quad.upper_left, quad.upper_right)
        + _distance(quad.lower_left, quad.lower_right)
    ) / 2.0
    average_height = (
        _distance(quad.upper_left, quad.lower_left)
        + _distance(quad.upper_right, quad.lower_right)
    ) / 2.0
    return max(1, int(round(max(average_width, average_height))))


def _quad_transform_data(quad: PointQuad) -> tuple[float, float, float, float, float, float, float, float]:
    return (
        quad.upper_left.x,
        quad.upper_left.y,
        quad.lower_left.x,
        quad.lower_left.y,
        quad.lower_right.x,
        quad.lower_right.y,
        quad.upper_right.x,
        quad.upper_right.y,
    )


def _distance(point_a: Point, point_b: Point) -> float:
    return math.hypot(point_b.x - point_a.x, point_b.y - point_a.y)
