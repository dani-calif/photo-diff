from __future__ import annotations

import logging
from typing import Any, Protocol, Sequence

import httpx
from pydantic import BaseModel

logger = logging.getLogger(__name__)


class EmbeddingApiError(RuntimeError):
    """Raised when embedding API calls fail or return invalid payloads."""


class ImageEmbedder(Protocol):
    async def embed_images(self, images_base64: Sequence[str]) -> list[list[float]]:
        ...


class HttpResponse(Protocol):
    @property
    def status_code(self) -> int:
        ...

    @property
    def text(self) -> str:
        ...

    def json(self) -> Any:
        ...


class HttpTransport(Protocol):
    async def post(
        self,
        url: str,
        *,
        json: dict[str, Any],
        headers: dict[str, str],
        timeout: float,
    ) -> HttpResponse:
        ...


class HttpxTransport:
    async def post(
        self,
        url: str,
        *,
        json: dict[str, Any],
        headers: dict[str, str],
        timeout: float,
    ) -> httpx.Response:
        async with httpx.AsyncClient(timeout=timeout) as client:
            return await client.post(url, json=json, headers=headers)


class EmbedImageRequest(BaseModel):
    image: str

    def as_json(self) -> dict[str, str]:
        return self.model_dump()


class ImageEmbeddingService(ImageEmbedder):
    def __init__(
        self,
        api_url: str,
        *,
        sending_system: str,
        timeout_seconds: float = 30.0,
        transport: HttpTransport | None = None,
    ) -> None:
        self._api_url = api_url
        self._sending_system = sending_system.strip()
        if not self._sending_system:
            raise ValueError("sending_system cannot be empty.")
        self._timeout_seconds = timeout_seconds
        self._transport = transport or HttpxTransport()

    async def embed_images(self, images_base64: Sequence[str]) -> list[list[float]]:
        if not images_base64:
            raise ValueError("images_base64 cannot be empty.")

        logger.info(
            "embedding images",
            extra={"images_count": len(images_base64), "api_url": self._api_url},
        )
        headers = {
            "Content-Type": "application/json",
            "SendingSystem": self._sending_system,
        }

        output: list[list[float]] = []
        for image_b64 in images_base64:
            payload = EmbedImageRequest(image=image_b64).as_json()

            try:
                response = await self._transport.post(
                    self._api_url,
                    json=payload,
                    headers=headers,
                    timeout=self._timeout_seconds,
                )
            except httpx.HTTPError as exc:
                raise EmbeddingApiError(f"Failed to call embedding API: {exc}") from exc

            if response.status_code >= 400:
                logger.info(
                    "embedding api returned error",
                    extra={"status_code": response.status_code, "api_url": self._api_url},
                )
                raise EmbeddingApiError(
                    f"Embedding API error {response.status_code}: {response.text[:300]}"
                )

            try:
                body = response.json()
            except ValueError as exc:
                raise EmbeddingApiError("Embedding API returned non-JSON response.") from exc

            output.append(_parse_embedding_vector(body))

        return output


def _parse_embedding_vector(value: Any) -> list[float]:
    if not isinstance(value, list) or not value:
        raise EmbeddingApiError("Embedding API response must be a non-empty JSON list.")
    try:
        return [float(item) for item in value]
    except (TypeError, ValueError) as exc:
        raise EmbeddingApiError("Embedding list contains non-numeric items.") from exc
