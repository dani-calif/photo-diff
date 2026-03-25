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
            },
            clear=True,
        ):
            settings = _load_settings_without_dotenv()

        self.assertEqual(settings.api_url, "https://api.example.com/embed/image")
        self.assertEqual(settings.sending_system, "geo-diff-tests")
        self.assertEqual(settings.embedder_backend, EmbedderBackend.HTTP)
        self.assertEqual(settings.timeout_seconds, 12.5)

    def test_loads_optional_embedder_backend(self) -> None:
        with patch.dict(
            os.environ,
            {
                "GEO_DIFF_API_URL": "https://api.example.com/embed/image",
                "GEO_DIFF_SENDING_SYSTEM": "geo-diff-tests",
                "GEO_DIFF_EMBEDDER_BACKEND": "internal",
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
            )

        self.assertEqual(settings.api_url, "https://cli.example.com/embed/image")
        self.assertEqual(settings.timeout_seconds, 42.0)

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
            },
            clear=True,
        ):
            settings = _load_settings_without_dotenv()
        self.assertEqual(settings.api_url, "https://api.example.com/embed/image")


if __name__ == "__main__":
    unittest.main()
