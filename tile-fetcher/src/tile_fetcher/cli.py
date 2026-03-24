from __future__ import annotations

import sys
from typing import TextIO

import uvicorn
from pydantic import ValidationError

from tile_fetcher.settings import load_settings


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
        settings = load_settings()
    except ValidationError as exc:
        print("Configuration error:", file=err)
        print(f"- {_first_validation_error(exc)}", file=err)
        return 2

    uvicorn.run(
        "tile_fetcher.app:create_app_from_env",
        host=settings.host,
        port=settings.port,
        reload=settings.reload,
        factory=True,
    )
    return 0


def _first_validation_error(exc: ValidationError) -> str:
    first = exc.errors()[0]
    location = ".".join(str(part) for part in first["loc"])
    return f"{location}: {first['msg']}"


if __name__ == "__main__":
    raise SystemExit(main())
