from __future__ import annotations

from tile_fetcher.services.service import TileFetchService
from tile_fetcher.settings import TileFetcherSettings
from tile_fetcher_internal.adapters.image_provider import build_image_provider
from tile_fetcher_internal.adapters.projection_mapper import build_projection_mapper


def build_tile_fetch_service(settings: TileFetcherSettings) -> TileFetchService:
    return TileFetchService(
        image_provider=build_image_provider(settings),
        projection_mapper=build_projection_mapper(settings),
        timeout_seconds=settings.timeout_seconds,
    )
