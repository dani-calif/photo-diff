from __future__ import annotations

import unittest
from typing import Sequence

from fastapi.testclient import TestClient

from geo_diff.app import create_app
from geo_diff.services.comparison import CompareImageMatrixResult, CompareImagesResult
from geo_diff.settings import AppSettings


class _FakeGeoDiffService:
    def __init__(self, *, error: Exception | None = None) -> None:
        self.error = error
        self.last_compare_raw: tuple[str, str] | None = None
        self.last_compare_point: tuple[list[str], float, float, float, bool] | None = None

    async def compare_raw_images(
        self,
        *,
        image_a: str,
        image_b: str,
    ) -> CompareImagesResult:
        self.last_compare_raw = (image_a, image_b)
        if self.error is not None:
            raise self.error
        return CompareImagesResult(
            image_a="YQ==",
            image_b="Yg==",
            cosine_similarity=0.9,
        )

    async def compare_point(
        self,
        *,
        image_ids: Sequence[str],
        lon: float,
        lat: float,
        buffer_size_meters: float,
        north_aligned: bool = True,
    ) -> CompareImageMatrixResult:
        self.last_compare_point = (
            list(image_ids),
            lon,
            lat,
            buffer_size_meters,
            north_aligned,
        )
        if self.error is not None:
            raise self.error
        return CompareImageMatrixResult(
            image_ids=list(image_ids),
            cosine_similarity_matrix=[[1.0, 0.8], [0.8, 1.0]],
        )


class RouteTests(unittest.TestCase):
    @staticmethod
    def _settings() -> AppSettings:
        return AppSettings(
            api_url="https://api.example.com/embed/image",
            sending_system="geo-diff-tests",
            tile_api_base_url="https://imagery.example.com",
        )

    def test_compare_raw_images_returns_similarity(self) -> None:
        fake_service = _FakeGeoDiffService()
        app = create_app(geo_diff_service=fake_service, settings=self._settings())
        client = TestClient(app)

        response = client.post(
            "/compare-raw-images",
            json={"image_a": "YQ==", "image_b": "Yg=="},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["cosine_similarity"], 0.9)
        self.assertEqual(fake_service.last_compare_raw, ("YQ==", "Yg=="))

    def test_compare_raw_images_returns_400_for_runtime_error(self) -> None:
        fake_service = _FakeGeoDiffService(error=ValueError("bad image"))
        app = create_app(geo_diff_service=fake_service, settings=self._settings())
        client = TestClient(app)

        response = client.post(
            "/compare-raw-images",
            json={"image_a": "YQ==", "image_b": "Yg=="},
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["detail"], "bad image")

    def test_compare_point_returns_matrix_and_passes_default_alignment(self) -> None:
        fake_service = _FakeGeoDiffService()
        app = create_app(geo_diff_service=fake_service, settings=self._settings())
        client = TestClient(app)

        response = client.post(
            "/compare-point",
            json={
                "image_ids": ["img-1", "img-2"],
                "lon": 34.0,
                "lat": 31.0,
                "buffer_size_meters": 15.0,
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["image_ids"], ["img-1", "img-2"])
        self.assertEqual(response.json()["cosine_similarity_matrix"][0][1], 0.8)
        self.assertEqual(
            fake_service.last_compare_point,
            (["img-1", "img-2"], 34.0, 31.0, 15.0, True),
        )

    def test_compare_point_passes_alignment_flag(self) -> None:
        fake_service = _FakeGeoDiffService()
        app = create_app(geo_diff_service=fake_service, settings=self._settings())
        client = TestClient(app)

        response = client.post(
            "/compare-point",
            json={
                "image_ids": ["img-1", "img-2"],
                "lon": 34.0,
                "lat": 31.0,
                "buffer_size_meters": 15.0,
                "north_aligned": False,
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            fake_service.last_compare_point,
            (["img-1", "img-2"], 34.0, 31.0, 15.0, False),
        )


if __name__ == "__main__":
    unittest.main()
