from __future__ import annotations

import math
import unittest
from dataclasses import dataclass
from io import BytesIO
from typing import Sequence

from PIL import Image, ImageDraw
from shapely.geometry import Point

from tile_fetcher import (
    ImageProviderClient,
    Point as GeometryPoint,
    ProjectionMapperClient,
    ProviderImage,
    ResolvedImage,
    TileFetchService,
    XYXYBox,
)


@dataclass(slots=True)
class _FakeImageProvider:
    image_bytes: bytes
    azimuth: float
    resolved_image: ResolvedImage
    find_tile_calls: list[tuple[str, float, float, float]]
    fetch_image_calls: list[tuple[str, str, float]]

    async def resolve_tile_for_point(
        self, gid: str, point: GeometryPoint, timeout_seconds: float
    ) -> ResolvedImage:
        self.find_tile_calls.append((gid, point.x, point.y, timeout_seconds))
        return self.resolved_image

    async def fetch_image(self, gid: str, pixel_bbox: XYXYBox, timeout_seconds: float) -> ProviderImage:
        self.fetch_image_calls.append((gid, pixel_bbox.to_string(), timeout_seconds))
        return ProviderImage(image_bytes=self.image_bytes, azimuth=self.azimuth)


class _FakeProjectionMapper:
    def __init__(self, points: dict[str, GeometryPoint]) -> None:
        self._points = points
        self.geo_to_pixel_calls: list[tuple[str, float, float, float]] = []
        self.pixel_to_geo_calls: list[tuple[str, float, float, float]] = []

    async def geo_to_pixel_points(
        self, gid: str, points: Sequence[GeometryPoint], timeout_seconds: float
    ) -> list[GeometryPoint]:
        point = points[0]
        self.geo_to_pixel_calls.append((gid, point.x, point.y, timeout_seconds))
        return [self._points[gid]]

    async def pixel_to_geo_points(
        self, gid: str, points: Sequence[GeometryPoint], timeout_seconds: float
    ) -> list[GeometryPoint]:
        center = self._points[gid]
        output: list[GeometryPoint] = []
        for point in points:
            self.pixel_to_geo_calls.append((gid, point.x, point.y, timeout_seconds))
            if math.isclose(point.x, center.x + 1.0) and math.isclose(point.y, center.y):
                output.append(Point(_degrees_for_meters(1.0), 0.0))
                continue
            if math.isclose(point.x, center.x) and math.isclose(point.y, center.y + 1.0):
                output.append(Point(0.0, _degrees_for_meters(1.0)))
                continue
            raise AssertionError(f"Unexpected projection lookup: {(gid, point.x, point.y)}")
        return output


class TileFetchServiceTests(unittest.IsolatedAsyncioTestCase):
    async def test_fetch_tiles_at_point_as_base64_uses_meter_buffer(self) -> None:
        source_bytes = _make_split_color_image()
        provider = _FakeImageProvider(
            image_bytes=source_bytes,
            azimuth=90.0,
            resolved_image=ResolvedImage(
                bounds=XYXYBox(xmin=0.0, ymin=0.0, xmax=20.0, ymax=20.0),
                azimuth=15.0,
            ),
            find_tile_calls=[],
            fetch_image_calls=[],
        )
        projection_mapper = _FakeProjectionMapper(
            points={
                "img-1": Point(100.0, 120.0),
                "img-2": Point(150.0, 160.0),
            }
        )
        service = TileFetchService(
            image_provider=ImageProviderClient(
                resolve_tile_for_point=provider.resolve_tile_for_point,
                fetch_image=provider.fetch_image,
            ),
            projection_mapper=ProjectionMapperClient(
                geo_to_pixel_points=projection_mapper.geo_to_pixel_points,
                pixel_to_geo_points=projection_mapper.pixel_to_geo_points,
            ),
            timeout_seconds=10.0,
            expand_factor=2.0,
        )

        encoded = await service.fetch_tiles_at_point_as_base64(
            image_ids=["img-1"],
            lon=0.0,
            lat=0.0,
            buffer_size_meters=5.0,
        )

        self.assertEqual(len(encoded), 1)
        self.assertTrue(isinstance(encoded[0], str) and encoded[0])
        self.assertEqual(provider.find_tile_calls, [("img-1", 0.0, 0.0, 10.0)])
        self.assertEqual(
            projection_mapper.geo_to_pixel_calls,
            [("img-1", 0.0, 0.0, 10.0)],
        )
        self.assertEqual(
            provider.fetch_image_calls,
            [("img-1", "90.0,110.0,110.0,130.0", 10.0)],
        )

    async def test_north_aligned_flag_changes_output(self) -> None:
        source_bytes = _make_split_color_image()

        async def run(north_aligned: bool) -> str:
            provider = _FakeImageProvider(
                image_bytes=source_bytes,
                azimuth=90.0,
                resolved_image=ResolvedImage(
                    bounds=XYXYBox(xmin=0.0, ymin=0.0, xmax=20.0, ymax=20.0),
                    azimuth=90.0,
                ),
                find_tile_calls=[],
                fetch_image_calls=[],
            )
            projection_mapper = _FakeProjectionMapper(points={"img-1": Point(100.0, 120.0)})
            service = TileFetchService(
                image_provider=ImageProviderClient(
                    resolve_tile_for_point=provider.resolve_tile_for_point,
                    fetch_image=provider.fetch_image,
                ),
                projection_mapper=ProjectionMapperClient(
                    geo_to_pixel_points=projection_mapper.geo_to_pixel_points,
                    pixel_to_geo_points=projection_mapper.pixel_to_geo_points,
                ),
                timeout_seconds=10.0,
                expand_factor=2.0,
            )
            images = await service.fetch_tiles_at_point_as_base64(
                image_ids=["img-1"],
                lon=0.0,
                lat=0.0,
                buffer_size_meters=5.0,
                north_aligned=north_aligned,
            )
            return images[0]

        north_aligned = await run(True)
        raw_orientation = await run(False)
        self.assertNotEqual(north_aligned, raw_orientation)


def _degrees_for_meters(meters: float) -> float:
    earth_radius_meters = 6_371_000.0
    return math.degrees(meters / earth_radius_meters)


def _make_split_color_image() -> bytes:
    image = Image.new("RGB", (400, 400), color=(0, 0, 0))
    draw = ImageDraw.Draw(image)
    draw.rectangle((0, 0, 199, 399), fill=(255, 0, 0))
    draw.rectangle((200, 0, 399, 399), fill=(0, 0, 255))

    out = BytesIO()
    image.save(out, format="PNG")
    return out.getvalue()


if __name__ == "__main__":
    unittest.main()
