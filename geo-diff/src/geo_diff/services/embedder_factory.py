from __future__ import annotations

from geo_diff.services.embedding import ImageEmbedder, ImageEmbeddingService
from geo_diff.settings import AppSettings, EmbedderBackend
from geo_diff_internal.adapters.embedder_adapter import build_embedder as build_internal_embedder


def build_image_embedder(settings: AppSettings) -> ImageEmbedder:
    if settings.embedder_backend is EmbedderBackend.HTTP:
        return ImageEmbeddingService(
            api_url=settings.api_url,
            sending_system=settings.sending_system,
            timeout_seconds=settings.timeout_seconds,
        )
    if settings.embedder_backend is EmbedderBackend.INTERNAL:
        return build_internal_embedder(settings)
    raise ValueError(f"Unsupported embedder backend: {settings.embedder_backend}")
