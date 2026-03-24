from __future__ import annotations

import io
import tempfile
import unittest
from pathlib import Path

import numpy as np
import rasterio
from PIL import Image
from rasterio.transform import from_origin
from shapely.geometry import Point

from geo_diff.demo.raster_tile_fetcher import (
    DemoRasterScene,
    build_demo_rasterio_image_provider,
    build_demo_rasterio_projection_mapper,
)
from tile_fetcher import Point as GeometryPoint
from tile_fetcher import XYXYBox


class DemoRasterTileFetcherTests(unittest.IsolatedAsyncioTestCase):
    async def test_projection_mapper_converts_between_geo_and_pixel(self) -> None:
        raster_path = _create_test_raster()
        scene = DemoRasterScene(gid="scene-1", raster_ref=str(raster_path), bands=(1, 2, 3))
        mapper = build_demo_rasterio_projection_mapper({"scene-1": scene})

        pixels = await mapper.geo_to_pixel_points(
            "scene-1",
            [Point(10.025, 49.975)],
            1.0,
        )
        self.assertEqual(pixels, [GeometryPoint(2.0, 2.0)])

        geo_points = await mapper.pixel_to_geo_points("scene-1", [Point(2.0, 2.0)], 1.0)
        self.assertAlmostEqual(geo_points[0].x, 10.025, places=6)
        self.assertAlmostEqual(geo_points[0].y, 49.975, places=6)

    async def test_image_provider_fetches_pixel_window(self) -> None:
        raster_path = _create_test_raster()
        scene = DemoRasterScene(gid="scene-1", raster_ref=str(raster_path), bands=(1, 2, 3))
        provider = build_demo_rasterio_image_provider({"scene-1": scene})

        image = await provider.fetch_image("scene-1", XYXYBox(1.0, 1.0, 4.0, 4.0), 1.0)
        with Image.open(io.BytesIO(image.image_bytes)) as rendered:
            self.assertEqual(rendered.size, (3, 3))

        resolved_image = await provider.resolve_tile_for_point("scene-1", Point(10.0, 50.0), 1.0)
        self.assertAlmostEqual(resolved_image.bounds.xmin, 10.0, places=6)
        self.assertAlmostEqual(resolved_image.bounds.ymax, 50.0, places=6)


def _create_test_raster() -> Path:
    temp_dir = Path(tempfile.mkdtemp(prefix="demo-raster-tile-fetcher-test-"))
    raster_path = temp_dir / "scene.tif"
    transform = from_origin(10.0, 50.0, 0.01, 0.01)
    data = np.zeros((3, 5, 5), dtype=np.uint8)
    data[0] = np.arange(25, dtype=np.uint8).reshape(5, 5)
    data[1] = 100
    data[2] = 200

    with rasterio.open(
        raster_path,
        "w",
        driver="GTiff",
        height=5,
        width=5,
        count=3,
        dtype=data.dtype,
        crs="EPSG:4326",
        transform=transform,
    ) as dataset:
        dataset.write(data)
    return raster_path


if __name__ == "__main__":
    unittest.main()
