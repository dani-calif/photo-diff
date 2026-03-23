from __future__ import annotations

from dataclasses import asdict

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from photo_diff.config import AppSettings
from photo_diff.constants import (
    APP_TITLE,
    APP_VERSION,
    DEFAULT_AERIAL_TARGET_SIZE_RATIO,
    DEFAULT_TIMEOUT_SECONDS,
    ROUTE_COMPARE_POINT,
    ROUTE_COMPARE_RAW_IMAGES,
    ROUTE_HEALTH,
)
from photo_diff.image_input import (
    AerialFetchConfig,
    load_aerial_images_by_ids_at_geopoint_as_base64,
    normalize_image_base64,
)
from photo_diff.services.comparison import (
    CompareImageMatrixRequest,
    CompareImagesRequest,
    ImageComparisonService,
)
from photo_diff.services.embedding import EmbeddingApiError, ImageEmbeddingService
from photo_diff.services.similarity import CosineSimilarityService


class CompareImagesPayload(BaseModel):
    image_a: str = Field(min_length=1)
    image_b: str = Field(min_length=1)


class CompareImageMatrixPayload(BaseModel):
    image_ids: list[str] = Field(min_length=2)
    lon: float
    lat: float


def create_app(
    *,
    settings: AppSettings | None = None,
    comparison_service: ImageComparisonService | None = None,
) -> FastAPI:
    app = FastAPI(title=APP_TITLE, version=APP_VERSION)
    app_settings = settings
    if app_settings is None and comparison_service is None:
        app_settings = AppSettings.from_overrides()

    service = comparison_service or _build_image_comparison_service(
        _require_settings(app_settings)
    )
    aerial_config = _build_aerial_config(app_settings)
    timeout_seconds = (
        app_settings.timeout_seconds if app_settings is not None else DEFAULT_TIMEOUT_SECONDS
    )
    target_size_ratio = (
        app_settings.aerial_target_size_ratio
        if app_settings is not None
        else DEFAULT_AERIAL_TARGET_SIZE_RATIO
    )

    @app.get(ROUTE_HEALTH)
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.post(ROUTE_COMPARE_RAW_IMAGES)
    async def compare_raw_images(payload: CompareImagesPayload) -> dict[str, object]:
        try:
            request = CompareImagesRequest(
                image_a=normalize_image_base64(payload.image_a),
                image_b=normalize_image_base64(payload.image_b),
            )
            result = await service.compare_images(request)
        except (EmbeddingApiError, ValueError, KeyError, TypeError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return asdict(result)

    @app.post(ROUTE_COMPARE_POINT)
    async def compare_point(payload: CompareImageMatrixPayload) -> dict[str, object]:
        try:
            images_base64 = await load_aerial_images_by_ids_at_geopoint_as_base64(
                image_ids=payload.image_ids,
                lon=payload.lon,
                lat=payload.lat,
                timeout_seconds=timeout_seconds,
                target_size_ratio=target_size_ratio,
                aerial_config=aerial_config,
            )
            result = await service.compare_image_matrix(
                CompareImageMatrixRequest(
                    image_ids=payload.image_ids,
                    images=images_base64,
                )
            )
        except (EmbeddingApiError, ValueError, KeyError, TypeError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return asdict(result)

    return app


def create_app_from_env() -> FastAPI:
    return create_app()


# Backward-compatible aliases.
def create_api_app(
    *,
    settings: AppSettings | None = None,
    comparison_app: ImageComparisonService | None = None,
) -> FastAPI:
    return create_app(settings=settings, comparison_service=comparison_app)


def create_api_app_from_env() -> FastAPI:
    return create_app_from_env()


def _build_image_comparison_service(settings: AppSettings) -> ImageComparisonService:
    embedding_service = ImageEmbeddingService(
        api_url=settings.api_url,
        api_key=settings.api_key,
        timeout_seconds=settings.timeout_seconds,
    )
    similarity_service = CosineSimilarityService()
    return ImageComparisonService(embedding_service, similarity_service)


def _build_aerial_config(settings: AppSettings | None) -> AerialFetchConfig | None:
    if settings is None:
        return None
    if not settings.aerial_api_url:
        return None

    return AerialFetchConfig(
        api_base_url=settings.aerial_api_url,
        expand_factor=settings.aerial_expand_factor,
        wms_geo_path=settings.aerial_wms_geo_path,
        wms_light_path=settings.aerial_wms_light_path,
        g2i_path=settings.aerial_g2i_path,
    )


def _require_settings(settings: AppSettings | None) -> AppSettings:
    if settings is None:
        raise ValueError("App settings are required to build the default comparison service.")
    return settings
