from __future__ import annotations

import unittest
from dataclasses import dataclass

from photo_diff.services.comparison import (
    CompareImageMatrixRequest,
    CompareImagesRequest,
    ImageComparisonService,
)


@dataclass(slots=True)
class _FakeEmbeddingService:
    embeddings: list[list[float]]
    calls: list[list[str]]

    async def embed_images(self, image_refs: list[str]) -> list[list[float]]:
        self.calls.append(image_refs)
        return self.embeddings


@dataclass(slots=True)
class _FakeSimilarityService:
    result: float
    calls: list[tuple[list[float], list[float]]]

    def cosine_similarity(self, vector_a: list[float], vector_b: list[float]) -> float:
        self.calls.append((vector_a, vector_b))
        return self.result


class ImageComparisonAppTests(unittest.IsolatedAsyncioTestCase):
    async def test_compare_images_uses_similarity_service_result(self) -> None:
        embedding_service = _FakeEmbeddingService(
            embeddings=[[1.0, 0.0], [0.5, 0.5]],
            calls=[],
        )
        similarity_service = _FakeSimilarityService(result=0.42, calls=[])

        app = ImageComparisonService(embedding_service, similarity_service)
        result = await app.compare_images(CompareImagesRequest(image_a="a.jpg", image_b="b.jpg"))

        self.assertEqual(embedding_service.calls, [["a.jpg", "b.jpg"]])
        self.assertEqual(similarity_service.calls, [([1.0, 0.0], [0.5, 0.5])])
        self.assertEqual(result.embedding_dimensions, 2)
        self.assertEqual(result.cosine_similarity, 0.42)

    async def test_compare_images_requires_two_embeddings(self) -> None:
        embedding_service = _FakeEmbeddingService(
            embeddings=[[1.0, 0.0, 0.0]],
            calls=[],
        )
        similarity_service = _FakeSimilarityService(result=0.42, calls=[])

        app = ImageComparisonService(embedding_service, similarity_service)

        with self.assertRaisesRegex(ValueError, "returned 1 embeddings"):
            await app.compare_images(CompareImagesRequest(image_a="a.jpg", image_b="b.jpg"))
        self.assertEqual(similarity_service.calls, [])

    async def test_compare_image_matrix_returns_square_matrix(self) -> None:
        embedding_service = _FakeEmbeddingService(
            embeddings=[[1.0, 0.0], [0.0, 1.0], [1.0, 1.0]],
            calls=[],
        )
        similarity_service = _FakeSimilarityService(result=0.0, calls=[])

        app = ImageComparisonService(embedding_service, similarity_service)
        result = await app.compare_image_matrix(
            CompareImageMatrixRequest(
                image_ids=["img-1", "img-2", "img-3"],
                images=["b64-1", "b64-2", "b64-3"],
            )
        )

        self.assertEqual(embedding_service.calls, [["b64-1", "b64-2", "b64-3"]])
        self.assertEqual(result.image_ids, ["img-1", "img-2", "img-3"])
        self.assertEqual(result.embedding_dimensions, 2)
        self.assertEqual(len(result.cosine_similarity_matrix), 3)
        self.assertEqual(result.cosine_similarity_matrix[0][0], 1.0)

    async def test_compare_image_matrix_rejects_mismatched_lengths(self) -> None:
        embedding_service = _FakeEmbeddingService(
            embeddings=[[1.0, 0.0]],
            calls=[],
        )
        similarity_service = _FakeSimilarityService(result=0.0, calls=[])

        app = ImageComparisonService(embedding_service, similarity_service)
        with self.assertRaisesRegex(ValueError, "same length"):
            await app.compare_image_matrix(
                CompareImageMatrixRequest(
                    image_ids=["img-1", "img-2"],
                    images=["b64-1"],
                )
            )


if __name__ == "__main__":
    unittest.main()
