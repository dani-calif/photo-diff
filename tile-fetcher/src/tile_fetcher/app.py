from __future__ import annotations

from io import BytesIO
import logging
from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field
from starlette.responses import StreamingResponse

from tile_fetcher import TileFetchError, TileFetchService
from tile_fetcher.services.factory import build_tile_fetch_service
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

    @app.get("/strip/pixel_bbox")
    async def strip_pixel_bbox(
        gid: str,
        x_min: int,
        y_min: int,
        x_max: int,
        y_max: int,
    ) -> str:
        try:
            return await service.strip_pixel_bbox(
                gid=gid,
                x_min=x_min,
                y_min=y_min,
                x_max=x_max,
                y_max=y_max,
            )
        except (TileFetchError, ValueError, KeyError, TypeError, NotImplementedError) as exc:
            logger.info("strip_pixel_bbox request failed", extra={"error": str(exc)})
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/strip/rotation_by_view_angle_pixel")
    async def strip_rotation_by_view_angle_pixel(
        gid: str,
        x_center_pixel: int,
        y_center_pixel: float,
        tile_size_pixels: float = Query(gt=0.0),
        max_output_width: int = Query(gt=0),
        max_output_height: int = Query(gt=0),
    ) -> StreamingResponse:
        try:
            image_bytes = await service.strip_rotation_by_view_angle_pixel(
                gid=gid,
                x_center_pixel=x_center_pixel,
                y_center_pixel=y_center_pixel,
                tile_size_pixels=tile_size_pixels,
                max_output_width=max_output_width,
                max_output_height=max_output_height,
            )
        except (TileFetchError, ValueError, KeyError, TypeError, NotImplementedError) as exc:
            logger.info(
                "strip_rotation_by_view_angle_pixel request failed",
                extra={"error": str(exc)},
            )
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return StreamingResponse(BytesIO(image_bytes), media_type="image/png")

    @app.get("/strip/rotation_by_view_angle_geo")
    async def strip_rotation_by_view_angle_geo(
        gid: str,
        x_center_geo: float,
        y_center_geo: float,
        tile_size_meters: int = Query(gt=0),
        max_output_width: int = Query(gt=0),
        max_output_height: int = Query(gt=0),
    ) -> StreamingResponse:
        try:
            image_bytes = await service.strip_rotation_by_view_angle_geo(
                gid=gid,
                x_center_geo=x_center_geo,
                y_center_geo=y_center_geo,
                tile_size_meters=tile_size_meters,
                max_output_width=max_output_width,
                max_output_height=max_output_height,
            )
        except (TileFetchError, ValueError, KeyError, TypeError, NotImplementedError) as exc:
            logger.info(
                "strip_rotation_by_view_angle_geo request failed",
                extra={"error": str(exc)},
            )
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return StreamingResponse(BytesIO(image_bytes), media_type="image/png")

    return app


def create_app_from_env() -> FastAPI:
    return create_app()


def _build_tile_fetch_service(settings: TileFetcherSettings) -> TileFetchService:
    return build_tile_fetch_service(settings)
