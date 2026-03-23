from __future__ import annotations

import io
import os
import unittest
from unittest.mock import patch

from photo_diff.cli import main


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
                "PHOTO_DIFF_API_URL": "https://api.example.com/embed/image",
                "PHOTO_DIFF_SENDING_SYSTEM": "photo-diff-tests",
                "PHOTO_DIFF_TILE_API_BASE_URL": "https://imagery.example.com",
                "PHOTO_DIFF_HOST": "0.0.0.0",
                "PHOTO_DIFF_PORT": "9000",
                "PHOTO_DIFF_RELOAD": "true",
            },
            clear=True,
        ):
            with patch("photo_diff.cli.uvicorn.run", side_effect=fake_runner):
                code = main(stderr=err)

        self.assertEqual(code, 0)
        self.assertEqual(err.getvalue(), "")
        self.assertEqual(called["app"], "photo_diff.app:create_app_from_env")
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
        with patch.dict(os.environ, {}, clear=True):
            code = main(stderr=err)

        self.assertEqual(code, 2)
        self.assertIn("Configuration error", err.getvalue())


if __name__ == "__main__":
    unittest.main()
