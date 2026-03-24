from __future__ import annotations

import logging
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from tile_fetcher import (
    TileFetchError,
    TileFetchService,
    build_http_image_provider,
    build_http_projection_mapper,
)
from tile_fetcher.http import HttpxGetClient
from tile_fetcher.settings import TileFetcherSettings, load_settings

logger = logging.getLogger(__name__)


class FetchTilesPayload(BaseModel):
    image_ids: list[str] = Field(min_length=1)
    lon: float
    lat: float
    buffer_size_meters: float = Field(gt=0.0)
    north_aligned: bool = True


class FetchTilesResponse(BaseModel):
    image_ids: list[str]
    images: list[str]


def create_app(
    *,
    settings: TileFetcherSettings | None = None,
    tile_fetch_service: TileFetchService | None = None,
) -> FastAPI:
    app = FastAPI(title="tile-fetcher", version="0.1.0")
    app_settings = settings or load_settings()
    service = tile_fetch_service or _build_tile_fetch_service(app_settings)

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/tiles/by-point")
    async def fetch_tiles(payload: FetchTilesPayload) -> dict[str, object]:
        logger.info(
            "fetch_tiles request",
            extra={
                "image_ids_count": len(payload.image_ids),
                "lon": payload.lon,
                "lat": payload.lat,
                "buffer_size_meters": payload.buffer_size_meters,
                "north_aligned": payload.north_aligned,
            },
        )
        try:
            result = await service.fetch_tiles_at_point_as_base64(
                image_ids=payload.image_ids,
                lon=payload.lon,
                lat=payload.lat,
                buffer_size_meters=payload.buffer_size_meters,
                north_aligned=payload.north_aligned,
            )
        except (TileFetchError, ValueError, KeyError, TypeError) as exc:
            logger.info("fetch_tiles request failed", extra={"error": str(exc)})
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        return FetchTilesResponse(image_ids=list(payload.image_ids), images=result).model_dump()

    return app


def create_app_from_env() -> FastAPI:
    return create_app()


def _build_tile_fetch_service(settings: TileFetcherSettings) -> TileFetchService:
    http_client = HttpxGetClient()
    return TileFetchService(
        image_provider=build_http_image_provider(
            api_base_url=settings.api_base_url,
            geo_path=settings.image_provider_geo_path,
            light_path=settings.image_provider_light_path,
            http_client=http_client,
        ),
        projection_mapper=build_http_projection_mapper(
            api_base_url=settings.api_base_url,
            g2i_path=settings.projection_mapper_g2i_path,
            i2g_path=settings.projection_mapper_i2g_path,
            http_client=http_client,
        ),
        timeout_seconds=settings.timeout_seconds,
        expand_factor=settings.expand_factor,
    )
