from __future__ import annotations

from typing import Any, cast

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from tile_fetcher.constants import (
    DEFAULT_IMAGE_PROVIDER_GEO_PATH,
    DEFAULT_IMAGE_PROVIDER_LIGHT_PATH,
    DEFAULT_PROJECTION_MAPPER_G2I_PATH,
    DEFAULT_PROJECTION_MAPPER_I2G_PATH,
    DEFAULT_TILE_EXPAND_FACTOR,
    DEFAULT_TIMEOUT_SECONDS,
    DEFAULT_UVICORN_HOST,
    DEFAULT_UVICORN_PORT,
    DEFAULT_UVICORN_RELOAD,
    DEFAULT_ROTATION_SAFE_EXPAND_FACTOR,
    SETTINGS_ENV_PREFIX,
)


class TileFetcherSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix=SETTINGS_ENV_PREFIX,
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    api_base_url: str
    timeout_seconds: float = Field(default=DEFAULT_TIMEOUT_SECONDS, gt=0.0)
    expand_factor: float = Field(
        default=DEFAULT_TILE_EXPAND_FACTOR,
        ge=DEFAULT_ROTATION_SAFE_EXPAND_FACTOR,
    )
    image_provider_geo_path: str = DEFAULT_IMAGE_PROVIDER_GEO_PATH
    image_provider_light_path: str = DEFAULT_IMAGE_PROVIDER_LIGHT_PATH
    projection_mapper_g2i_path: str = DEFAULT_PROJECTION_MAPPER_G2I_PATH
    projection_mapper_i2g_path: str = DEFAULT_PROJECTION_MAPPER_I2G_PATH
    host: str = DEFAULT_UVICORN_HOST
    port: int = Field(default=DEFAULT_UVICORN_PORT, ge=1, le=65535)
    reload: bool = DEFAULT_UVICORN_RELOAD

    @field_validator(
        "image_provider_geo_path",
        "image_provider_light_path",
        "projection_mapper_g2i_path",
        "projection_mapper_i2g_path",
    )
    @classmethod
    def _validate_slash_prefixed_path(cls, value: str) -> str:
        if not value.startswith("/"):
            raise ValueError("tile-fetcher route paths must start with '/'.")
        return value


def load_settings() -> TileFetcherSettings:
    settings_factory = cast(Any, TileFetcherSettings)
    return settings_factory()
