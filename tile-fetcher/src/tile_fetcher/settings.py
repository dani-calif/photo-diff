from __future__ import annotations

from typing import Any, cast

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class TileFetcherSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="TILE_FETCHER_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    timeout_seconds: float = Field(default=30.0, gt=0.0)
    host: str = "127.0.0.1"
    port: int = Field(default=8010, ge=1, le=65535)
    reload: bool = False


def load_settings() -> TileFetcherSettings:
    settings_factory = cast(Any, TileFetcherSettings)
    return settings_factory()
