from __future__ import annotations

from typing import Any, cast

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from photo_diff.constants import (
    DEFAULT_IMAGE_PROVIDER_GEO_PATH,
    DEFAULT_IMAGE_PROVIDER_LIGHT_PATH,
    DEFAULT_PROJECTION_MAPPER_G2I_PATH,
    DEFAULT_PROJECTION_MAPPER_I2G_PATH,
    DEFAULT_TILE_EXPAND_FACTOR,
    DEFAULT_ROTATION_SAFE_EXPAND_FACTOR,
    DEFAULT_TIMEOUT_SECONDS,
    DEFAULT_UVICORN_HOST,
    DEFAULT_UVICORN_PORT,
    DEFAULT_UVICORN_RELOAD,
    SETTINGS_ENV_PREFIX,
)


class AppSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix=SETTINGS_ENV_PREFIX,
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    api_url: str
    sending_system: str
    timeout_seconds: float = Field(default=DEFAULT_TIMEOUT_SECONDS, gt=0.0)
    tile_api_base_url: str
    tile_expand_factor: float = Field(
        default=DEFAULT_TILE_EXPAND_FACTOR,
        ge=DEFAULT_ROTATION_SAFE_EXPAND_FACTOR,
    )
    tile_image_provider_geo_path: str = DEFAULT_IMAGE_PROVIDER_GEO_PATH
    tile_image_provider_light_path: str = DEFAULT_IMAGE_PROVIDER_LIGHT_PATH
    tile_projection_mapper_g2i_path: str = DEFAULT_PROJECTION_MAPPER_G2I_PATH
    tile_projection_mapper_i2g_path: str = DEFAULT_PROJECTION_MAPPER_I2G_PATH
    host: str = DEFAULT_UVICORN_HOST
    port: int = Field(default=DEFAULT_UVICORN_PORT, ge=1, le=65535)
    reload: bool = DEFAULT_UVICORN_RELOAD

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
