from __future__ import annotations

import io
import os
import unittest
from unittest.mock import patch

from pydantic import ValidationError

from geo_diff.cli import main


class CliTests(unittest.TestCase):
    def test_main_runs_uvicorn_from_env(self) -> None:
        called: dict[str, object] = {}

        def fake_runner(app: str, **kwargs: object) -> None:
            called["app"] = app
            called["kwargs"] = kwargs

        err = io.StringIO()
        with patch.dict(
            os.environ,
            {
                "GEO_DIFF_API_URL": "https://api.example.com/embed/image",
                "GEO_DIFF_SENDING_SYSTEM": "geo-diff-tests",
                "GEO_DIFF_TILE_API_BASE_URL": "https://imagery.example.com",
                "GEO_DIFF_HOST": "0.0.0.0",
                "GEO_DIFF_PORT": "9000",
                "GEO_DIFF_RELOAD": "true",
            },
            clear=True,
        ):
            with patch("geo_diff.cli.uvicorn.run", side_effect=fake_runner):
                code = main(stderr=err)

        self.assertEqual(code, 0)
        self.assertEqual(err.getvalue(), "")
        self.assertEqual(called["app"], "geo_diff.app:create_app_from_env")
        self.assertEqual(
            called["kwargs"],
            {"host": "0.0.0.0", "port": 9000, "reload": True, "factory": True},
        )

    def test_main_rejects_cli_arguments(self) -> None:
        err = io.StringIO()
        code = main(["serve"], stderr=err)
        self.assertEqual(code, 2)
        self.assertIn("takes no arguments", err.getvalue())

    def test_main_returns_config_error_when_api_url_missing(self) -> None:
        err = io.StringIO()
        validation_error = ValidationError.from_exception_data(
            "AppSettings",
            [{"type": "missing", "loc": ("api_url",), "input": {}}],
        )
        with patch("geo_diff.cli.load_settings", side_effect=validation_error):
            code = main(stderr=err)

        self.assertEqual(code, 2)
        self.assertIn("Configuration error", err.getvalue())


if __name__ == "__main__":
    unittest.main()
