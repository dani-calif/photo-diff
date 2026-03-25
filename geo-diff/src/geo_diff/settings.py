from __future__ import annotations

from enum import StrEnum
from typing import Any, cast

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

class EmbedderBackend(StrEnum):
    HTTP = "http"
    INTERNAL = "internal"


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
    embedder_backend: EmbedderBackend = EmbedderBackend.HTTP
    timeout_seconds: float = Field(default=30.0, gt=0.0)
    tile_api_base_url: str
    tile_image_provider_light_path: str = "/image/wms/light"
    tile_projection_mapper_g2i_path: str = "/image/g2i"
    host: str = "127.0.0.1"
    port: int = Field(default=8000, ge=1, le=65535)
    reload: bool = False

    @field_validator(
        "tile_image_provider_light_path",
        "tile_projection_mapper_g2i_path",
    )
    @classmethod
    def _validate_slash_prefixed_path(cls, value: str) -> str:
        if not value.startswith("/"):
            raise ValueError("tile route paths must start with '/'.")
        return value


def load_settings() -> AppSettings:
    settings_factory = cast(Any, AppSettings)
    return settings_factory()
