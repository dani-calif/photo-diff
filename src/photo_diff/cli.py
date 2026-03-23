from __future__ import annotations

import sys
from typing import TextIO

import uvicorn

from photo_diff.config import AppSettings
from photo_diff.constants import UVICORN_APP_FACTORY


def main(
    argv: list[str] | None = None,
    *,
    stderr: TextIO | None = None,
) -> int:
    err = stderr or sys.stderr
    args = argv or []
    if args:
        print("This command takes no arguments. Configure via environment variables.", file=err)
        return 2

    try:
        settings = AppSettings.from_overrides()
    except ValueError as exc:
        print("Configuration error:", file=err)
        print(f"- {exc}", file=err)
        return 2

    uvicorn.run(
        UVICORN_APP_FACTORY,
        host=settings.host,
        port=settings.port,
        reload=settings.reload,
        factory=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
