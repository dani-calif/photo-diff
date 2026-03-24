from __future__ import annotations

import logging
from dataclasses import asdict

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from geo_diff.services.comparison import ImageComparisonService, ImageComparisonUseCase
from geo_diff.services.embedding import EmbeddingApiError, ImageEmbeddingService
from geo_diff.services.service import GeoDiffService, GeoDiffUseCase
from geo_diff.services.similarity import CosineSimilarityService
from geo_diff.settings import AppSettings, load_settings
from tile_fetcher import (
    TileFetchError,
    TileFetchService,
    build_http_image_provider,
    build_http_projection_mapper,
)
from tile_fetcher.http import HttpxGetClient

logger = logging.getLogger(__name__)


class CompareImagesPayload(BaseModel):
    image_a: str = Field(min_length=1)
    image_b: str = Field(min_length=1)


class ComparePointPayload(BaseModel):
    image_ids: list[str] = Field(min_length=2)
    lon: float
    lat: float
    buffer_size_meters: float = Field(gt=0.0)
    north_aligned: bool = True


def create_app(
    *,
    settings: AppSettings | None = None,
    geo_diff_service: GeoDiffUseCase | None = None,
    comparison_service: ImageComparisonUseCase | None = None,
    tile_fetch_service: TileFetchService | None = None,
) -> FastAPI:
    app = FastAPI(title="geo-diff", version="0.1.0")
    app_settings = settings or load_settings()
    service = geo_diff_service or _build_geo_diff_service(
        settings=app_settings,
        comparison_service=comparison_service,
        tile_fetch_service=tile_fetch_service,
    )

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/compare-raw-images")
    async def compare_raw_images(payload: CompareImagesPayload) -> dict[str, object]:
        logger.info("compare_raw_images request")
        try:
            result = await service.compare_raw_images(
                image_a=payload.image_a,
                image_b=payload.image_b,
            )
        except (EmbeddingApiError, ValueError, KeyError, TypeError) as exc:
            logger.info("compare_raw_images failed", extra={"error": str(exc)})
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return asdict(result)

    @app.post("/compare-point")
    async def compare_point(payload: ComparePointPayload) -> dict[str, object]:
        logger.info(
            "compare_point request",
            extra={
                "image_ids_count": len(payload.image_ids),
                "lon": payload.lon,
                "lat": payload.lat,
                "buffer_size_meters": payload.buffer_size_meters,
                "north_aligned": payload.north_aligned,
            },
        )
        try:
            result = await service.compare_point(
                image_ids=payload.image_ids,
                lon=payload.lon,
                lat=payload.lat,
                buffer_size_meters=payload.buffer_size_meters,
                north_aligned=payload.north_aligned,
            )
        except (EmbeddingApiError, TileFetchError, ValueError, KeyError, TypeError) as exc:
            logger.info("compare_point failed", extra={"error": str(exc)})
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return asdict(result)

    return app


def create_app_from_env() -> FastAPI:
    return create_app()


def _build_geo_diff_service(
    *,
    settings: AppSettings,
    comparison_service: ImageComparisonUseCase | None = None,
    tile_fetch_service: TileFetchService | None = None,
) -> GeoDiffUseCase:
    return GeoDiffService(
        comparison_service=comparison_service or _build_image_comparison_service(settings),
        tile_fetch_service=tile_fetch_service or _build_tile_fetch_service(settings),
    )


def _build_image_comparison_service(settings: AppSettings) -> ImageComparisonService:
    embedding_service = ImageEmbeddingService(
        api_url=settings.api_url,
        sending_system=settings.sending_system,
        timeout_seconds=settings.timeout_seconds,
    )
    similarity_service = CosineSimilarityService()
    return ImageComparisonService(embedding_service, similarity_service)


def _build_tile_fetch_service(settings: AppSettings) -> TileFetchService:
    http_client = HttpxGetClient()
    return TileFetchService(
        image_provider=build_http_image_provider(
            api_base_url=settings.tile_api_base_url,
            light_path=settings.tile_image_provider_light_path,
            http_client=http_client,
        ),
        projection_mapper=build_http_projection_mapper(
            api_base_url=settings.tile_api_base_url,
            g2i_path=settings.tile_projection_mapper_g2i_path,
            http_client=http_client,
        ),
        timeout_seconds=settings.timeout_seconds,
    )
