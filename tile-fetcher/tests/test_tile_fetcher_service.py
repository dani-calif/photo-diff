from __future__ import annotations

import base64
import unittest
from dataclasses import dataclass
from io import BytesIO
from typing import Sequence

from PIL import Image, ImageDraw
from pyproj import CRS, Transformer
from shapely.geometry import Point

from tile_fetcher import (
    ImageProviderClient,
    Point as GeometryPoint,
    ProjectionMapperClient,
    ProviderImage,
    TileFetchService,
    XYXYBox,
)


@dataclass(slots=True)
class _FakeImageProvider:
    template_image_bytes: bytes
    fetch_image_calls: list[tuple[str, str, float]]

    async def fetch_image(
        self,
        gid: str,
        pixel_bbox: XYXYBox,
        timeout_seconds: float,
    ) -> ProviderImage:
        self.fetch_image_calls.append((gid, pixel_bbox.to_string(), timeout_seconds))
        rendered_width = max(1, int(round(pixel_bbox.width)))
        rendered_height = max(1, int(round(pixel_bbox.height)))
        return ProviderImage(
            image_bytes=_resize_image(
                self.template_image_bytes,
                width=rendered_width,
                height=rendered_height,
            ),
            pixel_bbox=pixel_bbox,
        )


class _FakeProjectionMapper:
    def __init__(self, pixel_quads: dict[str, list[GeometryPoint]]) -> None:
        self._pixel_quads = pixel_quads
        self.geo_to_pixel_calls: list[tuple[str, list[GeometryPoint], float]] = []

    async def geo_to_pixel_points(
        self,
        gid: str,
        points: Sequence[GeometryPoint],
        timeout_seconds: float,
    ) -> list[GeometryPoint]:
        self.geo_to_pixel_calls.append((gid, list(points), timeout_seconds))
        return self._pixel_quads[gid]


class TileFetchServiceTests(unittest.IsolatedAsyncioTestCase):
    async def test_fetch_tiles_at_point_as_base64_fetches_enclosing_bbox_of_projected_geo_square(self) -> None:
        provider = _FakeImageProvider(
            template_image_bytes=_make_gradient_image(),
            fetch_image_calls=[],
        )
        projection_mapper = _FakeProjectionMapper(
            pixel_quads={
                "img-1": [
                    Point(100.0, 100.0),
                    Point(90.0, 130.0),
                    Point(120.0, 140.0),
                    Point(130.0, 110.0),
                ]
            }
        )
        service = TileFetchService(
            image_provider=ImageProviderClient(
                fetch_image=provider.fetch_image,
            ),
            projection_mapper=ProjectionMapperClient(
                geo_to_pixel_points=projection_mapper.geo_to_pixel_points,
            ),
            timeout_seconds=10.0,
        )

        encoded = await service.fetch_tiles_at_point_as_base64(
            image_ids=["img-1"],
            lon=34.0,
            lat=31.0,
            buffer_size_meters=5.0,
        )

        self.assertEqual(len(projection_mapper.geo_to_pixel_calls), 1)
        gid, geo_points, timeout_seconds = projection_mapper.geo_to_pixel_calls[0]
        self.assertEqual((gid, timeout_seconds), ("img-1", 10.0))
        self.assertEqual(len(geo_points), 4)
        self.assertLess(geo_points[0].x, geo_points[3].x)
        self.assertGreater(geo_points[0].y, geo_points[1].y)
        self.assertEqual(
            provider.fetch_image_calls,
            [("img-1", "90.0,100.0,130.0,140.0", 10.0)],
        )

        rendered = _decode_image(encoded[0])
        self.assertEqual(rendered.size, (32, 32))

    async def test_buffer_size_meters_is_the_full_square_side_length(self) -> None:
        provider = _FakeImageProvider(
            template_image_bytes=_make_gradient_image(),
            fetch_image_calls=[],
        )
        captured_geo_points: list[GeometryPoint] = []

        async def capture_geo_to_pixel_points(
            gid: str,
            points: Sequence[GeometryPoint],
            timeout_seconds: float,
        ) -> list[GeometryPoint]:
            del gid, timeout_seconds
            captured_geo_points.extend(points)
            return [
                Point(0.0, 0.0),
                Point(0.0, 20.0),
                Point(20.0, 20.0),
                Point(20.0, 0.0),
            ]

        service = TileFetchService(
            image_provider=ImageProviderClient(fetch_image=provider.fetch_image),
            projection_mapper=ProjectionMapperClient(
                geo_to_pixel_points=capture_geo_to_pixel_points,
            ),
            timeout_seconds=10.0,
        )

        await service.fetch_tiles_at_point_as_base64(
            image_ids=["img-1"],
            lon=34.7818,
            lat=32.0853,
            buffer_size_meters=20.0,
        )

        self.assertEqual(len(captured_geo_points), 4)
        top_edge_meters = _distance_meters(captured_geo_points[0], captured_geo_points[3])
        left_edge_meters = _distance_meters(captured_geo_points[0], captured_geo_points[1])
        self.assertAlmostEqual(top_edge_meters, 20.0, delta=0.25)
        self.assertAlmostEqual(left_edge_meters, 20.0, delta=0.25)

    async def test_north_aligned_flag_changes_output(self) -> None:
        source_bytes = _make_split_color_image()

        async def run(north_aligned: bool) -> tuple[str, list[tuple[str, str, float]]]:
            provider = _FakeImageProvider(
                template_image_bytes=source_bytes,
                fetch_image_calls=[],
            )
            projection_mapper = _FakeProjectionMapper(
                pixel_quads={
                    "img-1": [
                        Point(100.0, 100.0),
                        Point(90.0, 130.0),
                        Point(120.0, 140.0),
                        Point(130.0, 110.0),
                    ]
                }
            )
            service = TileFetchService(
                image_provider=ImageProviderClient(
                    fetch_image=provider.fetch_image,
                ),
                projection_mapper=ProjectionMapperClient(
                    geo_to_pixel_points=projection_mapper.geo_to_pixel_points,
                ),
                timeout_seconds=10.0,
            )
            images = await service.fetch_tiles_at_point_as_base64(
                image_ids=["img-1"],
                lon=0.0,
                lat=0.0,
                buffer_size_meters=5.0,
                north_aligned=north_aligned,
            )
            return images[0], provider.fetch_image_calls

        north_aligned_image, north_calls = await run(True)
        raw_orientation_image, raw_calls = await run(False)

        self.assertNotEqual(north_aligned_image, raw_orientation_image)
        self.assertEqual(north_calls, [("img-1", "90.0,100.0,130.0,140.0", 10.0)])
        self.assertEqual(raw_calls, [("img-1", "90.0,100.0,130.0,140.0", 10.0)])
        self.assertEqual(_decode_image(north_aligned_image).size, (32, 32))
        self.assertEqual(_decode_image(raw_orientation_image).size, (40, 40))

    async def test_strip_pixel_bbox_returns_base64_image(self) -> None:
        provider = _FakeImageProvider(
            template_image_bytes=_make_gradient_image(),
            fetch_image_calls=[],
        )

        async def strip_pixel_bbox(
            gid: str,
            pixel_bbox: XYXYBox,
            timeout_seconds: float,
        ) -> bytes:
            return (await provider.fetch_image(gid, pixel_bbox, timeout_seconds)).image_bytes

        service = TileFetchService(
            image_provider=ImageProviderClient(
                fetch_image=provider.fetch_image,
                strip_pixel_bbox=strip_pixel_bbox,
            ),
            projection_mapper=ProjectionMapperClient(
                geo_to_pixel_points=lambda *_args, **_kwargs: None  # type: ignore[arg-type]
            ),
            timeout_seconds=10.0,
        )

        encoded = await service.strip_pixel_bbox(
            gid="img-1",
            x_min=10,
            y_min=20,
            x_max=50,
            y_max=70,
        )

        self.assertEqual(_decode_image(encoded).size, (40, 50))

    async def test_strip_rotation_routes_delegate_to_provider(self) -> None:
        provider = _FakeImageProvider(
            template_image_bytes=_make_gradient_image(),
            fetch_image_calls=[],
        )

        async def strip_rotation_by_view_angle_pixel(
            gid: str,
            x_center_pixel: int,
            y_center_pixel: float,
            tile_size_pixels: float,
            max_output_width: int,
            max_output_height: int,
            timeout_seconds: float,
        ) -> bytes:
            del gid, x_center_pixel, y_center_pixel, tile_size_pixels, timeout_seconds
            return _resize_image(
                provider.template_image_bytes,
                width=max_output_width,
                height=max_output_height,
            )

        async def strip_rotation_by_view_angle_geo(
            gid: str,
            x_center_geo: float,
            y_center_geo: float,
            tile_size_meters: int,
            max_output_width: int,
            max_output_height: int,
            timeout_seconds: float,
        ) -> bytes:
            del gid, x_center_geo, y_center_geo, tile_size_meters, timeout_seconds
            return _resize_image(
                provider.template_image_bytes,
                width=max_output_width,
                height=max_output_height,
            )

        service = TileFetchService(
            image_provider=ImageProviderClient(
                fetch_image=provider.fetch_image,
                strip_rotation_by_view_angle_pixel=strip_rotation_by_view_angle_pixel,
                strip_rotation_by_view_angle_geo=strip_rotation_by_view_angle_geo,
            ),
            projection_mapper=ProjectionMapperClient(
                geo_to_pixel_points=lambda *_args, **_kwargs: None  # type: ignore[arg-type]
            ),
            timeout_seconds=10.0,
        )

        pixel_image = await service.strip_rotation_by_view_angle_pixel(
            gid="img-1",
            x_center_pixel=100,
            y_center_pixel=200.0,
            tile_size_pixels=128.0,
            max_output_width=64,
            max_output_height=32,
        )
        geo_image = await service.strip_rotation_by_view_angle_geo(
            gid="img-1",
            x_center_geo=34.0,
            y_center_geo=31.0,
            tile_size_meters=250,
            max_output_width=48,
            max_output_height=24,
        )

        self.assertEqual(_decode_image(base64.b64encode(pixel_image).decode("ascii")).size, (64, 32))
        self.assertEqual(_decode_image(base64.b64encode(geo_image).decode("ascii")).size, (48, 24))


def _decode_image(image_b64: str) -> Image.Image:
    return Image.open(BytesIO(base64.b64decode(image_b64))).convert("RGB")


def _make_gradient_image() -> bytes:
    image = Image.new("RGB", (300, 300), color=(0, 0, 0))
    draw = ImageDraw.Draw(image)
    for x in range(300):
        draw.line((x, 0, x, 299), fill=(x % 255, 100, 200))

    out = BytesIO()
    image.save(out, format="PNG")
    return out.getvalue()


def _make_split_color_image() -> bytes:
    image = Image.new("RGB", (400, 400), color=(0, 0, 0))
    draw = ImageDraw.Draw(image)
    draw.rectangle((0, 0, 199, 399), fill=(255, 0, 0))
    draw.rectangle((200, 0, 399, 399), fill=(0, 0, 255))

    out = BytesIO()
    image.save(out, format="PNG")
    return out.getvalue()


def _resize_image(image_bytes: bytes, *, width: int, height: int) -> bytes:
    with Image.open(BytesIO(image_bytes)) as source_image:
        resized = source_image.convert("RGB").resize((width, height), Image.Resampling.BICUBIC)
    out = BytesIO()
    resized.save(out, format="PNG")
    return out.getvalue()


def _distance_meters(a: GeometryPoint, b: GeometryPoint) -> float:
    projected_crs = _utm_crs_for_point(a)
    to_projected = Transformer.from_crs("EPSG:4326", projected_crs, always_xy=True)
    ax, ay = to_projected.transform(a.x, a.y)
    bx, by = to_projected.transform(b.x, b.y)
    return ((bx - ax) ** 2 + (by - ay) ** 2) ** 0.5


def _utm_crs_for_point(point: GeometryPoint) -> CRS:
    zone = int((point.x + 180.0) / 6.0) + 1
    epsg = 32600 + zone if point.y >= 0.0 else 32700 + zone
    return CRS.from_epsg(epsg)


if __name__ == "__main__":
    unittest.main()
