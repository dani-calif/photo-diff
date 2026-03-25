from __future__ import annotations

import unittest
from dataclasses import dataclass
from typing import Sequence

from fastapi.testclient import TestClient

from geo_diff.app import create_app
from geo_diff.services.comparison import ImageComparisonService
from geo_diff.services.embedding import ImageEmbedder
from geo_diff.services.service import GeoDiffService
from geo_diff.settings import AppSettings
from tile_fetcher import ImageProviderClient, ProjectionMapperClient, TileFetchService
from shapely.geometry import Point


@dataclass(slots=True)
class _FakeEmbedder(ImageEmbedder):
    embeddings: list[list[float]] | None = None
    error: Exception | None = None
    calls: list[list[str]] | None = None

    async def embed_images(self, images_base64: Sequence[str]) -> list[list[float]]:
        if self.calls is not None:
            self.calls.append(list(images_base64))
        if self.error is not None:
            raise self.error
        if self.embeddings is None:
            raise AssertionError("embeddings must be provided when no error is configured")
        return self.embeddings


class _FakeTileFetchService(TileFetchService):
    def __init__(self, images: list[str]) -> None:
        self.images = images
        self.last_call: tuple[list[str], float, float, float, bool] | None = None
        super().__init__(
            image_provider=ImageProviderClient(fetch_image=self._unused_fetch_image),
            projection_mapper=ProjectionMapperClient(
                geo_to_pixel_points=self._unused_geo_to_pixel_points
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

    async def _unused_fetch_image(self, gid: str, pixel_bbox, timeout_seconds: float):
        raise AssertionError(f"Unexpected call: fetch_image({gid}, {pixel_bbox}, {timeout_seconds})")

    async def _unused_geo_to_pixel_points(
        self,
        gid: str,
        points: Sequence[Point],
        timeout_seconds: float,
    ) -> list[Point]:
        raise AssertionError(f"Unexpected call: geo_to_pixel_points({gid}, {points}, {timeout_seconds})")


class RouteTests(unittest.TestCase):
    @staticmethod
    def _settings() -> AppSettings:
        return AppSettings(
            api_url="https://api.example.com/embed/image",
            sending_system="geo-diff-tests",
        )

    @staticmethod
    def _build_service(
        *,
        embeddings: list[list[float]] | None = None,
        error: Exception | None = None,
        tile_images: list[str] | None = None,
    ) -> tuple[GeoDiffService, _FakeEmbedder, _FakeTileFetchService]:
        embedder = _FakeEmbedder(embeddings=embeddings, error=error, calls=[])
        tile_fetcher = _FakeTileFetchService(tile_images or ["YQ==", "Yg=="])
        service = GeoDiffService(
            comparison_service=ImageComparisonService(embedder),
            tile_fetch_service=tile_fetcher,
        )
        return service, embedder, tile_fetcher

    def test_compare_raw_images_returns_similarity(self) -> None:
        service, embedder, _ = self._build_service(
            embeddings=[[1.0, 0.0], [1.0, 0.0]],
        )
        app = create_app(geo_diff_service=service, settings=self._settings())
        client = TestClient(app)

        response = client.post(
            "/compare-raw-images",
            json={"image_a": "YQ==", "image_b": "Yg=="},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["cosine_similarity"], 1.0)
        self.assertEqual(embedder.calls, [["YQ==", "Yg=="]])

    def test_compare_raw_images_returns_400_for_runtime_error(self) -> None:
        service, _, _ = self._build_service(error=ValueError("bad image"))
        app = create_app(geo_diff_service=service, settings=self._settings())
        client = TestClient(app)

        response = client.post(
            "/compare-raw-images",
            json={"image_a": "YQ==", "image_b": "Yg=="},
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["detail"], "bad image")

    def test_compare_point_returns_matrix_and_passes_default_alignment(self) -> None:
        service, embedder, tile_fetcher = self._build_service(
            embeddings=[[1.0, 0.0], [0.0, 1.0]],
        )
        app = create_app(geo_diff_service=service, settings=self._settings())
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
        self.assertEqual(response.json()["cosine_similarity_matrix"][0][1], 0.0)
        self.assertEqual(
            tile_fetcher.last_call,
            (["img-1", "img-2"], 34.0, 31.0, 15.0, True),
        )
        self.assertEqual(embedder.calls, [["YQ==", "Yg=="]])

    def test_compare_point_passes_alignment_flag(self) -> None:
        service, _, tile_fetcher = self._build_service(
            embeddings=[[1.0, 0.0], [0.0, 1.0]],
        )
        app = create_app(geo_diff_service=service, settings=self._settings())
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
            tile_fetcher.last_call,
            (["img-1", "img-2"], 34.0, 31.0, 15.0, False),
        )


if __name__ == "__main__":
    unittest.main()
