from __future__ import annotations

from enum import StrEnum
from typing import Any, cast

from pydantic import Field
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
    host: str = "127.0.0.1"
    port: int = Field(default=8000, ge=1, le=65535)
    reload: bool = False


def load_settings() -> AppSettings:
    settings_factory = cast(Any, AppSettings)
    return settings_factory()
