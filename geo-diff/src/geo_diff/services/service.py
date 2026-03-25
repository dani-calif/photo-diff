from __future__ import annotations

import logging
from typing import Sequence

from geo_diff.image_base64 import normalize_image_base64
from geo_diff.services.comparison import (
    CompareImageMatrixRequest,
    CompareImageMatrixResult,
    CompareImagesRequest,
    CompareImagesResult,
    ImageComparisonService,
)
from tile_fetcher import TileFetchService

logger = logging.getLogger(__name__)


class GeoDiffService:
    def __init__(
        self,
        *,
        comparison_service: ImageComparisonService,
        tile_fetch_service: TileFetchService,
    ) -> None:
        self._comparison_service = comparison_service
        self._tile_fetch_service = tile_fetch_service

    async def compare_raw_images(
        self,
        *,
        image_a: str,
        image_b: str,
    ) -> CompareImagesResult:
        logger.info("comparing raw images")
        request = CompareImagesRequest(
            image_a=normalize_image_base64(image_a),
            image_b=normalize_image_base64(image_b),
        )
        return await self._comparison_service.compare_images(request)

    async def compare_point(
        self,
        *,
        image_ids: Sequence[str],
        lon: float,
        lat: float,
        buffer_size_meters: float,
        north_aligned: bool = True,
    ) -> CompareImageMatrixResult:
        normalized_ids = [image_id.strip() for image_id in image_ids]
        logger.info(
            "comparing point",
            extra={
                "image_ids_count": len(normalized_ids),
                "lon": lon,
                "lat": lat,
                "buffer_size_meters": buffer_size_meters,
                "north_aligned": north_aligned,
            },
        )
        images_base64 = await self._tile_fetch_service.fetch_tiles_at_point_as_base64(
            image_ids=normalized_ids,
            lon=lon,
            lat=lat,
            buffer_size_meters=buffer_size_meters,
            north_aligned=north_aligned,
        )

        return await self._comparison_service.compare_image_matrix(
            CompareImageMatrixRequest(
                image_ids=normalized_ids,
                images=images_base64,
            )
        )
