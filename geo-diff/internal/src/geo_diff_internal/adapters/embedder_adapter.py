from __future__ import annotations

from collections.abc import Sequence

from geo_diff.services.embedding import ImageEmbedder, ImageEmbeddingService
from geo_diff.settings import AppSettings


class InternalEmbedderAdapter(ImageEmbedder):
    """Internal adapter seam.

    Replace this implementation in the internal mirror when wiring an internal
    embedding client or library.
    """

    def __init__(self, settings: AppSettings) -> None:
        self._embedder = ImageEmbeddingService(
            api_url=settings.api_url,
            sending_system=settings.sending_system,
            timeout_seconds=settings.timeout_seconds,
        )

    async def embed_images(self, images_base64: Sequence[str]) -> list[list[float]]:
        return await self._embedder.embed_images(images_base64)


def build_embedder(settings: AppSettings) -> ImageEmbedder:
    return InternalEmbedderAdapter(settings)
