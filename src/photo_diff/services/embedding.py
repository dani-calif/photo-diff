from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Mapping, Protocol, Sequence

import httpx

from photo_diff.constants import (
    HTTP_CONTENT_TYPE_JSON,
    HTTP_HEADER_CONTENT_TYPE,
    HTTP_HEADER_SENDING_SYSTEM,
    KEY_DATA,
    KEY_EMBEDDING,
    KEY_IMAGE,
    KEY_VECTOR,
)

logger = logging.getLogger("photo-diff.embedding")


class EmbeddingApiError(RuntimeError):
    """Raised when embedding API calls fail or return invalid payloads."""


class HttpResponse(Protocol):
    status_code: int
    text: str

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


@dataclass(slots=True)
class EmbedImageRequest:
    image: str

    def as_json(self) -> dict[str, str]:
        return {KEY_IMAGE: self.image}


@dataclass(slots=True)
class EmbeddingCandidate:
    embedding: list[float] | None = None
    vector: list[float] | None = None

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "EmbeddingCandidate":
        return cls(
            embedding=(
                _to_float_list_or_none(value[KEY_EMBEDDING])
                if KEY_EMBEDDING in value
                else None
            ),
            vector=(
                _to_float_list_or_none(value[KEY_VECTOR]) if KEY_VECTOR in value else None
            ),
        )

    def resolved(self) -> list[float] | None:
        return self.embedding or self.vector


@dataclass(slots=True)
class EmbeddingApiResponse:
    root: EmbeddingCandidate
    data: list[EmbeddingCandidate]

    @classmethod
    def from_body(cls, body: Any) -> "EmbeddingApiResponse":
        if not isinstance(body, Mapping):
            raise EmbeddingApiError("Embedding API response must be a JSON object.")

        root = EmbeddingCandidate.from_mapping(body)

        data: list[EmbeddingCandidate] = []
        if KEY_DATA in body:
            data_raw = body[KEY_DATA]
            if not isinstance(data_raw, list):
                raise EmbeddingApiError("'data' field must be a list when present.")
            for item in data_raw:
                if not isinstance(item, Mapping):
                    raise EmbeddingApiError("'data' items must be JSON objects.")
                data.append(EmbeddingCandidate.from_mapping(item))
        return cls(root=root, data=data)

    def extract_embedding(self) -> list[float]:
        candidates: list[EmbeddingCandidate] = [self.root, *self.data]
        for candidate in candidates:
            vector = candidate.resolved()
            if vector is not None:
                return vector

        raise EmbeddingApiError(
            "Could not find embedding in API response. "
            "Supported keys: embedding, vector, data[0].embedding, data[0].vector."
        )


class ImageEmbeddingService:
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
            HTTP_HEADER_CONTENT_TYPE: HTTP_CONTENT_TYPE_JSON,
            HTTP_HEADER_SENDING_SYSTEM: self._sending_system,
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

            parsed = EmbeddingApiResponse.from_body(body)
            output.append(parsed.extract_embedding())

        return output


def _to_float_list_or_none(value: Any) -> list[float] | None:
    if value is None:
        return None
    if not isinstance(value, list) or not value:
        raise EmbeddingApiError("Embedding is missing or not a non-empty list.")
    try:
        return [float(item) for item in value]
    except (TypeError, ValueError) as exc:
        raise EmbeddingApiError("Embedding list contains non-numeric items.") from exc
