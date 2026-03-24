from __future__ import annotations

import unittest
from dataclasses import dataclass
from typing import Sequence

from shapely.geometry import Point

from geo_diff.services.comparison import (
    CompareImageMatrixRequest,
    CompareImageMatrixResult,
    CompareImagesRequest,
    CompareImagesResult,
)
from geo_diff.services.service import GeoDiffService
from tile_fetcher import ImageProviderClient, ProjectionMapperClient, TileFetchService


@dataclass(slots=True)
class _FakeComparisonService:
    last_compare_images: CompareImagesRequest | None = None
    last_compare_matrix: CompareImageMatrixRequest | None = None

    async def compare_images(self, request: CompareImagesRequest) -> CompareImagesResult:
        self.last_compare_images = request
        return CompareImagesResult(
            image_a=request.image_a,
            image_b=request.image_b,
            cosine_similarity=0.9,
        )

    async def compare_image_matrix(
        self,
        request: CompareImageMatrixRequest,
    ) -> CompareImageMatrixResult:
        self.last_compare_matrix = request
        return CompareImageMatrixResult(
            image_ids=request.image_ids,
            cosine_similarity_matrix=[[1.0, 0.8], [0.8, 1.0]],
        )


class _FakeTileFetchService(TileFetchService):
    def __init__(self, images: list[str]) -> None:
        self.images = images
        self.last_call: tuple[list[str], float, float, float, bool] | None = None
        super().__init__(
            image_provider=ImageProviderClient(
                resolve_tile_for_point=self._unused_resolve_tile_for_point,
                fetch_image=self._unused_fetch_image,
            ),
            projection_mapper=ProjectionMapperClient(
                geo_to_pixel_points=self._unused_geo_to_pixel_points,
                pixel_to_geo_points=self._unused_pixel_to_geo_points,
            ),
            timeout_seconds=1.0,
        )

    async def fetch_tiles_at_point_as_base64(
        self,
        *,
        image_ids: Sequence[str],
        lon: float,
        lat: float,
        buffer_size_meters: float,
        north_aligned: bool = True,
    ) -> list[str]:
        self.last_call = (list(image_ids), lon, lat, buffer_size_meters, north_aligned)
        return self.images

    async def _unused_resolve_tile_for_point(self, gid: str, point: Point, timeout_seconds: float):
        raise AssertionError(f"Unexpected call: resolve_tile_for_point({gid}, {point}, {timeout_seconds})")

    async def _unused_fetch_image(self, gid: str, pixel_bbox, timeout_seconds: float):
        raise AssertionError(f"Unexpected call: fetch_image({gid}, {pixel_bbox}, {timeout_seconds})")

    async def _unused_geo_to_pixel_points(
        self,
        gid: str,
        points: Sequence[Point],
        timeout_seconds: float,
    ) -> list[Point]:
        raise AssertionError(f"Unexpected call: geo_to_pixel_points({gid}, {points}, {timeout_seconds})")

    async def _unused_pixel_to_geo_points(
        self,
        gid: str,
        points: Sequence[Point],
        timeout_seconds: float,
    ) -> list[Point]:
        raise AssertionError(f"Unexpected call: pixel_to_geo_points({gid}, {points}, {timeout_seconds})")


class GeoDiffServiceTests(unittest.IsolatedAsyncioTestCase):
    async def test_compare_raw_images_normalizes_input(self) -> None:
        comparison = _FakeComparisonService()
        service = GeoDiffService(
            comparison_service=comparison,
            tile_fetch_service=_FakeTileFetchService(images=[]),
        )

        result = await service.compare_raw_images(
            image_a="data:image/png;base64,YQ==",
            image_b="Yg==",
        )

        self.assertEqual(result.cosine_similarity, 0.9)
        self.assertEqual(comparison.last_compare_images, CompareImagesRequest("YQ==", "Yg=="))

    async def test_compare_point_uses_tile_fetch_service(self) -> None:
        comparison = _FakeComparisonService()
        tile_fetcher = _FakeTileFetchService(images=["YQ==", "Yg=="])
        service = GeoDiffService(
            comparison_service=comparison,
            tile_fetch_service=tile_fetcher,
        )

        result = await service.compare_point(
            image_ids=["img-1", "img-2"],
            lon=34.0,
            lat=31.0,
            buffer_size_meters=12.5,
            north_aligned=False,
        )

        self.assertEqual(result.image_ids, ["img-1", "img-2"])
        self.assertEqual(
            tile_fetcher.last_call,
            (["img-1", "img-2"], 34.0, 31.0, 12.5, False),
        )
        self.assertEqual(
            comparison.last_compare_matrix,
            CompareImageMatrixRequest(image_ids=["img-1", "img-2"], images=["YQ==", "Yg=="]),
        )


if __name__ == "__main__":
    unittest.main()
