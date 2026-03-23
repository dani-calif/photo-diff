from __future__ import annotations

from typing import TypedDict

from pydantic import Field, ValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict

from photo_diff.constants import (
    DEFAULT_AERIAL_EXPAND_FACTOR,
    DEFAULT_AERIAL_TARGET_SIZE_RATIO,
    DEFAULT_ROTATION_SAFE_EXPAND_FACTOR,
    DEFAULT_TIMEOUT_SECONDS,
    DEFAULT_UVICORN_HOST,
    DEFAULT_UVICORN_PORT,
    DEFAULT_UVICORN_RELOAD,
    ENV_AERIAL_API_URL,
    ENV_AERIAL_EXPAND_FACTOR,
    ENV_AERIAL_G2I_PATH,
    ENV_AERIAL_TARGET_SIZE_RATIO,
    ENV_AERIAL_WMS_GEO_PATH,
    ENV_AERIAL_WMS_LIGHT_PATH,
    ENV_EMBEDDING_API_KEY,
    ENV_EMBEDDING_API_URL,
    ENV_EMBEDDING_TIMEOUT_SECONDS,
    ENV_UVICORN_HOST,
    ENV_UVICORN_PORT,
    ENV_UVICORN_RELOAD,
)


class _AppSettingsOverrides(TypedDict, total=False):
    EMBEDDING_API_URL: str  # via ENV_EMBEDDING_API_URL
    EMBEDDING_API_KEY: str  # via ENV_EMBEDDING_API_KEY
    EMBEDDING_TIMEOUT_SECONDS: float  # via ENV_EMBEDDING_TIMEOUT_SECONDS
    AERIAL_API_URL: str  # via ENV_AERIAL_API_URL
    AERIAL_EXPAND_FACTOR: float  # via ENV_AERIAL_EXPAND_FACTOR
    AERIAL_TARGET_SIZE_RATIO: float  # via ENV_AERIAL_TARGET_SIZE_RATIO
    AERIAL_WMS_GEO_PATH: str  # via ENV_AERIAL_WMS_GEO_PATH
    AERIAL_WMS_LIGHT_PATH: str  # via ENV_AERIAL_WMS_LIGHT_PATH
    AERIAL_G2I_PATH: str  # via ENV_AERIAL_G2I_PATH
    UVICORN_HOST: str  # via ENV_UVICORN_HOST
    UVICORN_PORT: int  # via ENV_UVICORN_PORT
    UVICORN_RELOAD: bool  # via ENV_UVICORN_RELOAD


class AppSettings(BaseSettings):
    api_url: str = Field(alias=ENV_EMBEDDING_API_URL)
    api_key: str | None = Field(default=None, alias=ENV_EMBEDDING_API_KEY)
    timeout_seconds: float = Field(
        default=DEFAULT_TIMEOUT_SECONDS,
        gt=0,
        alias=ENV_EMBEDDING_TIMEOUT_SECONDS,
    )
    aerial_api_url: str | None = Field(default=None, alias=ENV_AERIAL_API_URL)
    aerial_expand_factor: float = Field(
        default=DEFAULT_AERIAL_EXPAND_FACTOR,
        ge=DEFAULT_ROTATION_SAFE_EXPAND_FACTOR,
        alias=ENV_AERIAL_EXPAND_FACTOR,
    )
    aerial_target_size_ratio: float = Field(
        default=DEFAULT_AERIAL_TARGET_SIZE_RATIO,
        gt=0.0,
        le=1.0,
        alias=ENV_AERIAL_TARGET_SIZE_RATIO,
    )
    aerial_wms_geo_path: str = Field(default="/image/wms/geo", alias=ENV_AERIAL_WMS_GEO_PATH)
    aerial_wms_light_path: str = Field(
        default="/image/wms/light",
        alias=ENV_AERIAL_WMS_LIGHT_PATH,
    )
    aerial_g2i_path: str = Field(default="/image/g2i", alias=ENV_AERIAL_G2I_PATH)
    host: str = Field(default=DEFAULT_UVICORN_HOST, alias=ENV_UVICORN_HOST)
    port: int = Field(default=DEFAULT_UVICORN_PORT, ge=1, le=65535, alias=ENV_UVICORN_PORT)
    reload: bool = Field(default=DEFAULT_UVICORN_RELOAD, alias=ENV_UVICORN_RELOAD)

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
    )

    @classmethod
    def from_overrides(
        cls,
        *,
        api_url: str | None = None,
        api_key: str | None = None,
        timeout_seconds: float | None = None,
        aerial_api_url: str | None = None,
        aerial_expand_factor: float | None = None,
        aerial_target_size_ratio: float | None = None,
        aerial_wms_geo_path: str | None = None,
        aerial_wms_light_path: str | None = None,
        aerial_g2i_path: str | None = None,
        host: str | None = None,
        port: int | None = None,
        reload: bool | None = None,
    ) -> "AppSettings":
        data: _AppSettingsOverrides = {}
        if api_url is not None:
            data[ENV_EMBEDDING_API_URL] = api_url
        if api_key is not None:
            data[ENV_EMBEDDING_API_KEY] = api_key
        if timeout_seconds is not None:
            data[ENV_EMBEDDING_TIMEOUT_SECONDS] = timeout_seconds
        if aerial_api_url is not None:
            data[ENV_AERIAL_API_URL] = aerial_api_url
        if aerial_expand_factor is not None:
            data[ENV_AERIAL_EXPAND_FACTOR] = aerial_expand_factor
        if aerial_target_size_ratio is not None:
            data[ENV_AERIAL_TARGET_SIZE_RATIO] = aerial_target_size_ratio
        if aerial_wms_geo_path is not None:
            data[ENV_AERIAL_WMS_GEO_PATH] = aerial_wms_geo_path
        if aerial_wms_light_path is not None:
            data[ENV_AERIAL_WMS_LIGHT_PATH] = aerial_wms_light_path
        if aerial_g2i_path is not None:
            data[ENV_AERIAL_G2I_PATH] = aerial_g2i_path
        if host is not None:
            data[ENV_UVICORN_HOST] = host
        if port is not None:
            data[ENV_UVICORN_PORT] = port
        if reload is not None:
            data[ENV_UVICORN_RELOAD] = reload

        try:
            settings = cls(**data)
        except ValidationError as exc:
            issues = exc.errors()
            if issues:
                first = issues[0]
                loc = tuple(str(part) for part in first["loc"])
                if ENV_EMBEDDING_API_URL in loc and first["type"] == "missing":
                    raise ValueError(f"{ENV_EMBEDDING_API_URL} is required") from exc
                raise ValueError(str(first["msg"])) from exc
            raise ValueError("Invalid settings") from exc

        if not settings.aerial_wms_geo_path.startswith("/"):
            raise ValueError("aerial_wms_geo_path must start with '/'.")
        if not settings.aerial_wms_light_path.startswith("/"):
            raise ValueError("aerial_wms_light_path must start with '/'.")
        if not settings.aerial_g2i_path.startswith("/"):
            raise ValueError("aerial_g2i_path must start with '/'.")
        return settings
