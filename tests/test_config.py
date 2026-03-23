from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from photo_diff.config import AppSettings


class AppSettingsTests(unittest.TestCase):
    def test_loads_values_from_environment(self) -> None:
        with patch.dict(
            os.environ,
            {
                "EMBEDDING_API_URL": "https://api.example.com/embed/image",
                "EMBEDDING_API_KEY": "test-key",
                "EMBEDDING_TIMEOUT_SECONDS": "12.5",
                "AERIAL_API_URL": "https://aerial.example.com",
                "AERIAL_EXPAND_FACTOR": "1.5",
                "AERIAL_TARGET_SIZE_RATIO": "0.2",
                "AERIAL_WMS_GEO_PATH": "/custom/wms/geo",
                "AERIAL_WMS_LIGHT_PATH": "/custom/wms/light",
                "AERIAL_G2I_PATH": "/custom/g2i",
            },
            clear=True,
        ):
            settings = AppSettings.from_overrides()

        self.assertEqual(settings.api_url, "https://api.example.com/embed/image")
        self.assertEqual(settings.api_key, "test-key")
        self.assertEqual(settings.timeout_seconds, 12.5)
        self.assertEqual(settings.aerial_api_url, "https://aerial.example.com")
        self.assertEqual(settings.aerial_expand_factor, 1.5)
        self.assertEqual(settings.aerial_target_size_ratio, 0.2)
        self.assertEqual(settings.aerial_wms_geo_path, "/custom/wms/geo")
        self.assertEqual(settings.aerial_wms_light_path, "/custom/wms/light")
        self.assertEqual(settings.aerial_g2i_path, "/custom/g2i")

    def test_overrides_take_precedence(self) -> None:
        with patch.dict(
            os.environ,
            {"EMBEDDING_API_URL": "https://env.example.com/embed/image"},
            clear=True,
        ):
            settings = AppSettings.from_overrides(
                api_url="https://cli.example.com/embed/image",
                timeout_seconds=42.0,
                aerial_api_url="https://cli-aerial.example.com",
                aerial_expand_factor=1.6,
                aerial_target_size_ratio=0.25,
                aerial_wms_geo_path="/geo/path",
                aerial_wms_light_path="/light/path",
                aerial_g2i_path="/g2i/path",
            )

        self.assertEqual(settings.api_url, "https://cli.example.com/embed/image")
        self.assertEqual(settings.timeout_seconds, 42.0)
        self.assertEqual(settings.aerial_api_url, "https://cli-aerial.example.com")
        self.assertEqual(settings.aerial_expand_factor, 1.6)
        self.assertEqual(settings.aerial_target_size_ratio, 0.25)
        self.assertEqual(settings.aerial_wms_geo_path, "/geo/path")
        self.assertEqual(settings.aerial_wms_light_path, "/light/path")
        self.assertEqual(settings.aerial_g2i_path, "/g2i/path")

    def test_api_url_is_required(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(ValueError, "EMBEDDING_API_URL is required"):
                AppSettings.from_overrides()


if __name__ == "__main__":
    unittest.main()
