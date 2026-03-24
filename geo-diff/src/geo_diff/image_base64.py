from __future__ import annotations

import asyncio
import base64
import binascii
from pathlib import Path
from typing import Any, Mapping, Protocol

import httpx


class ImageFetchResponse(Protocol):
    @property
    def content(self) -> bytes:
        ...

    def raise_for_status(self) -> object:
        ...

    def json(self) -> Any:
        ...


class ImageFetchHttpClient(Protocol):
    async def get(
        self,
        url: str,
        *,
        timeout: float,
        params: Mapping[str, str] | None = None,
    ) -> ImageFetchResponse:
        ...


class HttpxImageFetchClient:
    async def get(
        self,
        url: str,
        *,
        timeout: float,
        params: Mapping[str, str] | None = None,
    ) -> ImageFetchResponse:
        async with httpx.AsyncClient(timeout=timeout) as client:
            return await client.get(url, params=params)


async def load_image_ref_as_base64(
    image_ref: str,
    timeout_seconds: float = 30.0,
    http_client: ImageFetchHttpClient | None = None,
) -> str:
    client: ImageFetchHttpClient = (
        http_client if http_client is not None else HttpxImageFetchClient()
    )

    if image_ref.startswith(("http://", "https://")):
        response = await client.get(image_ref, timeout=timeout_seconds)
        response.raise_for_status()
        return base64.b64encode(response.content).decode("ascii")

    path = Path(image_ref).expanduser()
    if not path.is_file():
        raise FileNotFoundError(f"Image path does not exist or is not a file: {image_ref}")

    image_bytes = await asyncio.to_thread(path.read_bytes)
    return base64.b64encode(image_bytes).decode("ascii")


def normalize_image_base64(value: str) -> str:
    candidate = value.strip()
    if not candidate:
        raise ValueError("Image payload is empty.")

    if candidate.startswith("data:"):
        prefix, separator, payload = candidate.partition(",")
        if not separator:
            raise ValueError("Data URI image payload must include a comma separator.")
        if ";base64" not in prefix:
            raise ValueError("Data URI image payload must be base64 encoded.")
        candidate = payload.strip()

    compact = "".join(candidate.split())
    if not compact:
        raise ValueError("Image payload is empty.")

    try:
        base64.b64decode(compact, validate=True)
    except (ValueError, binascii.Error) as exc:
        raise ValueError("Image payload must be valid base64.") from exc

    return compact
