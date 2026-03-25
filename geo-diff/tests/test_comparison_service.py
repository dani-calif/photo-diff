from __future__ import annotations

import unittest
from dataclasses import dataclass
from math import sqrt
from typing import Sequence

from geo_diff.services.comparison import (
    CompareImageMatrixRequest,
    CompareImagesRequest,
    ImageComparisonService,
)
from geo_diff.services.embedding import ImageEmbedder


@dataclass(slots=True)
class _FakeEmbeddingService(ImageEmbedder):
    embeddings: list[list[float]]
    calls: list[list[str]]

    async def embed_images(self, images_base64: Sequence[str]) -> list[list[float]]:
        self.calls.append(list(images_base64))
        return self.embeddings


class ImageComparisonServiceTests(unittest.IsolatedAsyncioTestCase):
    async def test_compare_images_uses_similarity_service_result(self) -> None:
        embedding_service = _FakeEmbeddingService(
            embeddings=[[1.0, 0.0], [0.5, 0.5]],
            calls=[],
        )

        comparer = ImageComparisonService(embedding_service)
        result = await comparer.compare_images(CompareImagesRequest(image_a="a.jpg", image_b="b.jpg"))

        self.assertEqual(embedding_service.calls, [["a.jpg", "b.jpg"]])
        self.assertAlmostEqual(result.cosine_similarity, 1.0 / sqrt(2.0))

    async def test_compare_images_requires_two_embeddings(self) -> None:
        embedding_service = _FakeEmbeddingService(
            embeddings=[[1.0, 0.0, 0.0]],
            calls=[],
        )

        app = ImageComparisonService(embedding_service)

        with self.assertRaisesRegex(ValueError, "returned 1 embeddings"):
            await app.compare_images(CompareImagesRequest(image_a="a.jpg", image_b="b.jpg"))

    async def test_compare_image_matrix_returns_square_matrix(self) -> None:
        embedding_service = _FakeEmbeddingService(
            embeddings=[[1.0, 0.0], [0.0, 1.0], [1.0, 1.0]],
            calls=[],
        )

        app = ImageComparisonService(embedding_service)
        result = await app.compare_image_matrix(
            CompareImageMatrixRequest(
                image_ids=["img-1", "img-2", "img-3"],
                images=["b64-1", "b64-2", "b64-3"],
            )
        )

        self.assertEqual(embedding_service.calls, [["b64-1", "b64-2", "b64-3"]])
        self.assertEqual(result.image_ids, ["img-1", "img-2", "img-3"])
        self.assertEqual(len(result.cosine_similarity_matrix), 3)
        self.assertEqual(result.cosine_similarity_matrix[0][0], 1.0)
        self.assertEqual(result.cosine_similarity_matrix[0][1], 0.0)
        self.assertAlmostEqual(result.cosine_similarity_matrix[0][2], 1.0 / sqrt(2.0))

    async def test_compare_image_matrix_rejects_mismatched_lengths(self) -> None:
        embedding_service = _FakeEmbeddingService(
            embeddings=[[1.0, 0.0]],
            calls=[],
        )

        app = ImageComparisonService(embedding_service)
        with self.assertRaisesRegex(ValueError, "same length"):
            await app.compare_image_matrix(
                CompareImageMatrixRequest(
                    image_ids=["img-1", "img-2"],
                    images=["b64-1"],
                )
            )


if __name__ == "__main__":
    unittest.main()
