from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Mapping, Protocol

import httpx


class HttpResponseLike(Protocol):
    @property
    def content(self) -> bytes:
        ...

    def raise_for_status(self) -> object:
        ...

    def json(self) -> Any:
        ...


class HttpClient(ABC):
    @abstractmethod
    async def get(
        self, url: str, *, timeout: float, params: Mapping[str, str] | None = None
    ) -> HttpResponseLike:
        ...


class HttpxGetClient(HttpClient):
    async def get(
        self, url: str, *, timeout: float, params: Mapping[str, str] | None = None
    ) -> HttpResponseLike:
        async with httpx.AsyncClient(timeout=timeout) as client:
            return await client.get(url, params=params)
