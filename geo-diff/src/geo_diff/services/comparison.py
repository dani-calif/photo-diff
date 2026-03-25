from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from geo_diff.services.embedding import ImageEmbedder
from geo_diff.services.similarity import CosineSimilarityService


@dataclass(slots=True)
class CompareImagesRequest:
    image_a: str
    image_b: str


@dataclass(slots=True)
class CompareImagesResult:
    image_a: str
    image_b: str
    cosine_similarity: float


@dataclass(slots=True)
class CompareImageMatrixRequest:
    image_ids: list[str]
    images: list[str]


@dataclass(slots=True)
class CompareImageMatrixResult:
    image_ids: list[str]
    cosine_similarity_matrix: list[list[float]]


class ImageComparisonService:
    def __init__(
        self,
        embedding_service: ImageEmbedder,
        similarity_service: CosineSimilarityService | None = None,
    ) -> None:
        self._embedding_service = embedding_service
        self._similarity_service = similarity_service or CosineSimilarityService()

    async def compare_images(self, request: CompareImagesRequest) -> CompareImagesResult:
        embeddings = await self._embedding_service.embed_images(
            [request.image_a, request.image_b]
        )
        if len(embeddings) != 2:
            raise ValueError(
                f"Embedding API returned {len(embeddings)} embeddings for 2 input images."
            )
        embedding_a, embedding_b = embeddings
        similarity = self._similarity_service.cosine_similarity(embedding_a, embedding_b)

        return CompareImagesResult(
            image_a=request.image_a,
            image_b=request.image_b,
            cosine_similarity=similarity,
        )

    async def compare_image_matrix(
        self, request: CompareImageMatrixRequest
    ) -> CompareImageMatrixResult:
        if not request.image_ids:
            raise ValueError("image_ids cannot be empty.")
        if len(request.image_ids) != len(request.images):
            raise ValueError("image_ids and images must have the same length.")

        embeddings = await self._embedding_service.embed_images(request.images)
        if len(embeddings) != len(request.image_ids):
            raise ValueError(
                f"Embedding API returned {len(embeddings)} embeddings for "
                f"{len(request.image_ids)} images."
            )

        matrix = _build_cosine_similarity_matrix(embeddings, self._similarity_service)
        return CompareImageMatrixResult(
            image_ids=request.image_ids,
            cosine_similarity_matrix=matrix,
        )


def _build_cosine_similarity_matrix(
    embeddings: Sequence[Sequence[float]],
    similarity_service: CosineSimilarityService,
) -> list[list[float]]:
    if not embeddings:
        raise ValueError("embeddings cannot be empty.")

    size = len(embeddings)
    matrix: list[list[float]] = [[0.0] * size for _ in range(size)]
    for i in range(size):
        matrix[i][i] = 1.0
        for j in range(i + 1, size):
            value = similarity_service.cosine_similarity(embeddings[i], embeddings[j])
            matrix[i][j] = value
            matrix[j][i] = value
    return matrix
