from __future__ import annotations

import math
from typing import Any, cast

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

ROTATION_SAFE_EXPAND_FACTOR = math.sqrt(2.0)


class AppSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="GEO_DIFF_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    api_url: str
    sending_system: str
    timeout_seconds: float = Field(default=30.0, gt=0.0)
    tile_api_base_url: str
    tile_expand_factor: float = Field(
        default=ROTATION_SAFE_EXPAND_FACTOR,
        ge=ROTATION_SAFE_EXPAND_FACTOR,
    )
    tile_image_provider_geo_path: str = "/image/wms/geo"
    tile_image_provider_light_path: str = "/image/wms/light"
    tile_projection_mapper_g2i_path: str = "/image/g2i"
    tile_projection_mapper_i2g_path: str = "/image/i2g"
    host: str = "127.0.0.1"
    port: int = Field(default=8000, ge=1, le=65535)
    reload: bool = False

    @field_validator(
        "tile_image_provider_geo_path",
        "tile_image_provider_light_path",
        "tile_projection_mapper_g2i_path",
        "tile_projection_mapper_i2g_path",
    )
    @classmethod
    def _validate_slash_prefixed_path(cls, value: str) -> str:
        if not value.startswith("/"):
            raise ValueError("tile route paths must start with '/'.")
        return value


def load_settings() -> AppSettings:
    settings_factory = cast(Any, AppSettings)
    return settings_factory()
