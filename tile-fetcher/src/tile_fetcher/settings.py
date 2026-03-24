from __future__ import annotations

from typing import Any, cast

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class TileFetcherSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="TILE_FETCHER_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    api_base_url: str
    timeout_seconds: float = Field(default=30.0, gt=0.0)
    image_provider_light_path: str = "/image/wms/light"
    projection_mapper_g2i_path: str = "/image/g2i"
    host: str = "127.0.0.1"
    port: int = Field(default=8010, ge=1, le=65535)
    reload: bool = False

    @field_validator(
        "image_provider_light_path",
        "projection_mapper_g2i_path",
    )
    @classmethod
    def _validate_slash_prefixed_path(cls, value: str) -> str:
        if not value.startswith("/"):
            raise ValueError("tile-fetcher route paths must start with '/'.")
        return value


def load_settings() -> TileFetcherSettings:
    settings_factory = cast(Any, TileFetcherSettings)
    return settings_factory()
