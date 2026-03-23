from __future__ import annotations

import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from photo_diff.app import create_app
from photo_diff.services.comparison import (
    CompareImageMatrixRequest,
    CompareImageMatrixResult,
    CompareImagesRequest,
    CompareImagesResult,
)
from photo_diff.config import AppSettings


class _FakeComparisonApp:
    def __init__(self, *, error: Exception | None = None) -> None:
        self.error = error
        self.last_request: CompareImagesRequest | None = None
        self.last_matrix_request: CompareImageMatrixRequest | None = None

    async def compare_images(self, request: CompareImagesRequest) -> CompareImagesResult:
        self.last_request = request
        if self.error is not None:
            raise self.error
        return CompareImagesResult(
            image_a=request.image_a,
            image_b=request.image_b,
            embedding_dimensions=4,
            cosine_similarity=0.9,
        )

    async def compare_image_matrix(
        self, request: CompareImageMatrixRequest
    ) -> CompareImageMatrixResult:
        self.last_matrix_request = request
        if self.error is not None:
            raise self.error
        return CompareImageMatrixResult(
            image_ids=request.image_ids,
            embedding_dimensions=4,
            cosine_similarity_matrix=[
                [1.0, 0.8],
                [0.8, 1.0],
            ],
        )


class ApiTests(unittest.TestCase):
    @staticmethod
    def _settings() -> AppSettings:
        return AppSettings.from_overrides(
            api_url="https://api.example.com/embed/image",
            aerial_api_url="https://aerial.example.com",
        )

    def test_compare_endpoint_returns_similarity(self) -> None:
        fake = _FakeComparisonApp()
        app = create_app(comparison_service=fake, settings=self._settings())
        client = TestClient(app)

        response = client.post(
            "/compare-raw-images",
            json={"image_a": "YQ==", "image_b": "Yg=="},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["cosine_similarity"], 0.9)
        self.assertEqual(fake.last_request, CompareImagesRequest("YQ==", "Yg=="))

    def test_compare_endpoint_returns_400_for_runtime_error(self) -> None:
        fake = _FakeComparisonApp(error=ValueError("bad image"))
        app = create_app(comparison_service=fake, settings=self._settings())
        client = TestClient(app)

        response = client.post(
            "/compare-raw-images",
            json={"image_a": "YQ==", "image_b": "Yg=="},
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["detail"], "bad image")

    def test_compare_endpoint_rejects_non_base64_payload(self) -> None:
        fake = _FakeComparisonApp()
        app = create_app(comparison_service=fake, settings=self._settings())
        client = TestClient(app)

        response = client.post(
            "/compare-raw-images",
            json={"image_a": "not-base64", "image_b": "Yg=="},
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("valid base64", response.json()["detail"])

    def test_compare_matrix_endpoint_returns_matrix(self) -> None:
        fake = _FakeComparisonApp()
        app = create_app(comparison_service=fake, settings=self._settings())
        client = TestClient(app)

        with patch(
            "photo_diff.app.load_aerial_images_by_ids_at_geopoint_as_base64",
            return_value=["YQ==", "Yg=="],
        ):
            response = client.post(
                "/compare-point",
                json={"image_ids": ["img-1", "img-2"], "lon": 34.0, "lat": 31.0},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["image_ids"], ["img-1", "img-2"])
        self.assertEqual(response.json()["cosine_similarity_matrix"][0][1], 0.8)
        self.assertEqual(
            fake.last_matrix_request,
            CompareImageMatrixRequest(
                image_ids=["img-1", "img-2"],
                images=["YQ==", "Yg=="],
            ),
        )


if __name__ == "__main__":
    unittest.main()
