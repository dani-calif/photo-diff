from __future__ import annotations

import os
import unittest
from typing import Any, cast
from unittest.mock import patch

from pydantic import ValidationError

from geo_diff.settings import AppSettings, EmbedderBackend


def _load_settings_without_dotenv() -> AppSettings:
    settings_factory = cast(Any, AppSettings)
    return settings_factory(_env_file=None)


class SettingsTests(unittest.TestCase):
    def test_loads_values_from_environment(self) -> None:
        with patch.dict(
            os.environ,
            {
                "GEO_DIFF_API_URL": "https://api.example.com/embed/image",
                "GEO_DIFF_SENDING_SYSTEM": "geo-diff-tests",
                "GEO_DIFF_TIMEOUT_SECONDS": "12.5",
                "GEO_DIFF_TILE_API_BASE_URL": "https://imagery.example.com",
                "GEO_DIFF_TILE_IMAGE_PROVIDER_LIGHT_PATH": "/custom/wms/light",
                "GEO_DIFF_TILE_PROJECTION_MAPPER_G2I_PATH": "/custom/g2i",
            },
            clear=True,
        ):
            settings = _load_settings_without_dotenv()

        self.assertEqual(settings.api_url, "https://api.example.com/embed/image")
        self.assertEqual(settings.sending_system, "geo-diff-tests")
        self.assertEqual(settings.embedder_backend, EmbedderBackend.HTTP)
        self.assertEqual(settings.timeout_seconds, 12.5)
        self.assertEqual(settings.tile_api_base_url, "https://imagery.example.com")
        self.assertEqual(settings.tile_image_provider_light_path, "/custom/wms/light")
        self.assertEqual(settings.tile_projection_mapper_g2i_path, "/custom/g2i")

    def test_loads_optional_embedder_backend(self) -> None:
        with patch.dict(
            os.environ,
            {
                "GEO_DIFF_API_URL": "https://api.example.com/embed/image",
                "GEO_DIFF_SENDING_SYSTEM": "geo-diff-tests",
                "GEO_DIFF_EMBEDDER_BACKEND": "internal",
                "GEO_DIFF_TILE_API_BASE_URL": "https://imagery.example.com",
            },
            clear=True,
        ):
            settings = _load_settings_without_dotenv()

        self.assertEqual(settings.embedder_backend, EmbedderBackend.INTERNAL)

    def test_overrides_take_precedence(self) -> None:
        with patch.dict(
            os.environ,
            {
                "GEO_DIFF_API_URL": "https://env.example.com/embed/image",
                "GEO_DIFF_SENDING_SYSTEM": "env-system",
            },
            clear=True,
        ):
            settings = AppSettings(
                api_url="https://cli.example.com/embed/image",
                sending_system="cli-system",
                timeout_seconds=42.0,
                tile_api_base_url="https://cli-imagery.example.com",
                tile_image_provider_light_path="/light/path",
                tile_projection_mapper_g2i_path="/g2i/path",
            )

        self.assertEqual(settings.api_url, "https://cli.example.com/embed/image")
        self.assertEqual(settings.timeout_seconds, 42.0)
        self.assertEqual(settings.tile_api_base_url, "https://cli-imagery.example.com")
        self.assertEqual(settings.tile_image_provider_light_path, "/light/path")
        self.assertEqual(settings.tile_projection_mapper_g2i_path, "/g2i/path")

    def test_api_url_is_required(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(ValidationError):
                _load_settings_without_dotenv()

    def test_environment_keys_are_case_insensitive(self) -> None:
        with patch.dict(
            os.environ,
            {
                "geo_diff_api_url": "https://api.example.com/embed/image",
                "geo_diff_sending_system": "geo-diff-tests",
                "geo_diff_tile_api_base_url": "https://imagery.example.com",
            },
            clear=True,
        ):
            settings = _load_settings_without_dotenv()
        self.assertEqual(settings.api_url, "https://api.example.com/embed/image")


if __name__ == "__main__":
    unittest.main()
