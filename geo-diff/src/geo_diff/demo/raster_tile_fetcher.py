from __future__ import annotations

import io
import logging
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Sequence

import numpy as np
import rasterio
from PIL import Image
from rasterio.io import DatasetReader
from rasterio.windows import Window
from rasterio.warp import transform
from shapely.geometry import Point

from tile_fetcher.services.models import ProviderImage, XYXYBox
from tile_fetcher.utils.image_provider import ImageProviderClient
from tile_fetcher.utils.projection_mapper import ProjectionMapperClient

logger = logging.getLogger(__name__)

EPSG4326 = "EPSG:4326"


@dataclass(slots=True)
class DemoRasterScene:
    gid: str
    raster_ref: str
    bands: tuple[int, ...] = (1, 2, 3)

    def path(self) -> str:
        if _looks_remote(self.raster_ref):
            return self.raster_ref
        return str(Path(self.raster_ref).expanduser())


def build_demo_rasterio_image_provider(
    scenes: Mapping[str, DemoRasterScene],
) -> ImageProviderClient:
    async def fetch_image(
        gid: str,
        pixel_bbox: XYXYBox,
        timeout_seconds: float,
    ) -> ProviderImage:
        del timeout_seconds
        scene = _require_scene(scenes, gid)
        with rasterio.open(scene.path()) as dataset:
            window = _pixel_window(pixel_bbox, dataset.width, dataset.height)
            data = dataset.read(
                indexes=list(scene.bands),
                window=window,
                boundless=True,
                fill_value=0,
            )
        image_bytes = _encode_png(_to_rgb(data))
        logger.info(
            "fetched raster image",
            extra={
                "gid": gid,
                "bbox": pixel_bbox.to_string(),
                "window_width": window.width,
                "window_height": window.height,
            },
        )
        return ProviderImage(
            image_bytes=image_bytes,
            pixel_bbox=XYXYBox(
                xmin=float(window.col_off),
                ymin=float(window.row_off),
                xmax=float(window.col_off + window.width),
                ymax=float(window.row_off + window.height),
            ),
        )

    return ImageProviderClient(
        fetch_image=fetch_image,
    )


def build_demo_rasterio_projection_mapper(scenes: Mapping[str, DemoRasterScene]) -> ProjectionMapperClient:
    async def geo_to_pixel_points(
        gid: str,
        points: Sequence[Point],
        timeout_seconds: float,
    ) -> list[Point]:
        del timeout_seconds
        scene = _require_scene(scenes, gid)
        with rasterio.open(scene.path()) as dataset:
            pixel_points: list[Point] = []
            for point in points:
                x, y = _to_dataset_crs(dataset, point.x, point.y)
                row, col = dataset.index(x, y)
                pixel_points.append(Point(float(col), float(row)))
        return pixel_points

    return ProjectionMapperClient(
        geo_to_pixel_points=geo_to_pixel_points,
    )


def _to_dataset_crs(dataset: DatasetReader, lon: float, lat: float) -> tuple[float, float]:
    if str(dataset.crs) == EPSG4326:
        return lon, lat
    xs, ys = _transform_xy(EPSG4326, dataset.crs, [lon], [lat])
    return xs[0], ys[0]


def _pixel_window(pixel_bbox: XYXYBox, width: int, height: int) -> Window:
    col_off = max(0, int(math.floor(pixel_bbox.xmin)))
    row_off = max(0, int(math.floor(pixel_bbox.ymin)))
    col_end = min(width, int(math.ceil(pixel_bbox.xmax)))
    row_end = min(height, int(math.ceil(pixel_bbox.ymax)))
    safe_width = max(1, col_end - col_off)
    safe_height = max(1, row_end - row_off)
    return Window.from_slices(
        (row_off, row_off + safe_height),
        (col_off, col_off + safe_width),
    )


def _transform_xy(
    source_crs: object,
    target_crs: object,
    xs: Sequence[float],
    ys: Sequence[float],
) -> tuple[list[float], list[float]]:
    transformed = transform(source_crs, target_crs, list(xs), list(ys))
    if len(transformed) < 2:
        raise ValueError("Coordinate transform must return x/y sequences.")
    return transformed[0], transformed[1]


def _to_rgb(data: np.ndarray) -> np.ndarray:
    if data.ndim != 3:
        raise ValueError("Raster read must return (bands, height, width).")

    bands, height, width = data.shape
    if bands == 1:
        band = _normalize_band(data[0])
        stacked = np.stack([band, band, band], axis=0)
    elif bands >= 3:
        stacked = np.stack([_normalize_band(data[index]) for index in range(3)], axis=0)
    else:
        raise ValueError("Raster image provider requires at least 1 band.")

    return np.moveaxis(stacked, 0, -1).reshape(height, width, 3)


def _normalize_band(band: np.ndarray) -> np.ndarray:
    if band.dtype == np.uint8:
        return band

    candidate = np.nan_to_num(band.astype(np.float32), nan=0.0)
    low = float(np.percentile(candidate, 2))
    high = float(np.percentile(candidate, 98))
    if high <= low:
        high = low + 1.0
    clipped = np.clip(candidate, low, high)
    scaled = (clipped - low) / (high - low)
    return (scaled * 255.0).astype(np.uint8)


def _encode_png(rgb: np.ndarray) -> bytes:
    image = Image.fromarray(rgb, mode="RGB")
    out = io.BytesIO()
    image.save(out, format="PNG")
    return out.getvalue()


def _looks_remote(value: str) -> bool:
    return value.startswith(("http://", "https://", "s3://"))


def _require_scene(
    scenes: Mapping[str, DemoRasterScene],
    gid: str,
) -> DemoRasterScene:
    try:
        return scenes[gid]
    except KeyError as exc:
        raise KeyError(f"Unknown raster gid '{gid}'.") from exc
