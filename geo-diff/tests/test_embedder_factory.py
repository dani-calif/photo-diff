from __future__ import annotations

import unittest

from geo_diff.services.embedder_factory import build_image_embedder
from geo_diff.services.embedding import ImageEmbeddingService
from geo_diff.settings import AppSettings, EmbedderBackend
from geo_diff_internal.adapters.embedder_adapter import InternalEmbedderAdapter


class EmbedderFactoryTests(unittest.TestCase):
    @staticmethod
    def _settings(embedder_backend: EmbedderBackend) -> AppSettings:
        return AppSettings(
            api_url="https://api.example.com/embed/image",
            sending_system="geo-diff-tests",
            embedder_backend=embedder_backend,
            tile_api_base_url="https://imagery.example.com",
        )

    def test_build_image_embedder_uses_http_backend_by_default(self) -> None:
        embedder = build_image_embedder(self._settings(EmbedderBackend.HTTP))

        self.assertIsInstance(embedder, ImageEmbeddingService)

    def test_build_image_embedder_uses_internal_backend(self) -> None:
        embedder = build_image_embedder(self._settings(EmbedderBackend.INTERNAL))

        self.assertIsInstance(embedder, InternalEmbedderAdapter)
