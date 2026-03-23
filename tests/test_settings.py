from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from pydantic import ValidationError

from photo_diff.settings import AppSettings, load_settings


class SettingsTests(unittest.TestCase):
    def test_loads_values_from_environment(self) -> None:
        with patch.dict(
            os.environ,
            {
                "PHOTO_DIFF_API_URL": "https://api.example.com/embed/image",
                "PHOTO_DIFF_SENDING_SYSTEM": "photo-diff-tests",
                "PHOTO_DIFF_TIMEOUT_SECONDS": "12.5",
                "PHOTO_DIFF_TILE_API_BASE_URL": "https://imagery.example.com",
                "PHOTO_DIFF_TILE_EXPAND_FACTOR": "1.5",
                "PHOTO_DIFF_TILE_IMAGE_PROVIDER_GEO_PATH": "/custom/wms/geo",
                "PHOTO_DIFF_TILE_IMAGE_PROVIDER_LIGHT_PATH": "/custom/wms/light",
                "PHOTO_DIFF_TILE_PROJECTION_MAPPER_G2I_PATH": "/custom/g2i",
                "PHOTO_DIFF_TILE_PROJECTION_MAPPER_I2G_PATH": "/custom/i2g",
            },
            clear=True,
        ):
            settings = load_settings()

        self.assertEqual(settings.api_url, "https://api.example.com/embed/image")
        self.assertEqual(settings.sending_system, "photo-diff-tests")
        self.assertEqual(settings.timeout_seconds, 12.5)
        self.assertEqual(settings.tile_api_base_url, "https://imagery.example.com")
        self.assertEqual(settings.tile_expand_factor, 1.5)
        self.assertEqual(settings.tile_image_provider_geo_path, "/custom/wms/geo")
        self.assertEqual(settings.tile_image_provider_light_path, "/custom/wms/light")
        self.assertEqual(settings.tile_projection_mapper_g2i_path, "/custom/g2i")
        self.assertEqual(settings.tile_projection_mapper_i2g_path, "/custom/i2g")

    def test_overrides_take_precedence(self) -> None:
        with patch.dict(
            os.environ,
            {
                "PHOTO_DIFF_API_URL": "https://env.example.com/embed/image",
                "PHOTO_DIFF_SENDING_SYSTEM": "env-system",
            },
            clear=True,
        ):
            settings = AppSettings(
                api_url="https://cli.example.com/embed/image",
                sending_system="cli-system",
                timeout_seconds=42.0,
                tile_api_base_url="https://cli-imagery.example.com",
                tile_expand_factor=1.6,
                tile_image_provider_geo_path="/geo/path",
                tile_image_provider_light_path="/light/path",
                tile_projection_mapper_g2i_path="/g2i/path",
                tile_projection_mapper_i2g_path="/i2g/path",
            )

        self.assertEqual(settings.api_url, "https://cli.example.com/embed/image")
        self.assertEqual(settings.timeout_seconds, 42.0)
        self.assertEqual(settings.tile_api_base_url, "https://cli-imagery.example.com")
        self.assertEqual(settings.tile_expand_factor, 1.6)
        self.assertEqual(settings.tile_image_provider_geo_path, "/geo/path")
        self.assertEqual(settings.tile_image_provider_light_path, "/light/path")
        self.assertEqual(settings.tile_projection_mapper_g2i_path, "/g2i/path")
        self.assertEqual(settings.tile_projection_mapper_i2g_path, "/i2g/path")

    def test_api_url_is_required(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(ValidationError):
                load_settings()

    def test_environment_keys_are_case_insensitive(self) -> None:
        with patch.dict(
            os.environ,
            {
                "photo_diff_api_url": "https://api.example.com/embed/image",
                "photo_diff_sending_system": "photo-diff-tests",
                "photo_diff_tile_api_base_url": "https://imagery.example.com",
            },
            clear=True,
        ):
            settings = load_settings()
        self.assertEqual(settings.api_url, "https://api.example.com/embed/image")


if __name__ == "__main__":
    unittest.main()
