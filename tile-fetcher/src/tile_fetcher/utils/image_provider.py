from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Protocol

from pydantic import BaseModel, Field
from tile_fetcher.errors import TileFetchError
from tile_fetcher.http import HttpClient
from tile_fetcher.services.models import ProviderImage, XYXYBox

class FetchImageFn(Protocol):
    async def __call__(
        self,
        gid: str,
        pixel_bbox: XYXYBox,
        timeout_seconds: float,
    ) -> ProviderImage:
        ...


class FetchImageQuery(BaseModel):
    image_id: str
    bbox: str


class FetchedImagePayload(BaseModel):
    url: str = Field(min_length=1)


@dataclass(slots=True)
class ImageProviderClient:
    fetch_image: FetchImageFn


def build_http_image_provider(
    *,
    api_base_url: str,
    light_path: str,
    http_client: HttpClient,
) -> ImageProviderClient:
    base_url = api_base_url.rstrip("/")

    async def fetch_image(gid: str, pixel_bbox: XYXYBox, timeout_seconds: float) -> ProviderImage:
        try:
            response = await http_client.get(
                f"{base_url}{light_path}",
                timeout=timeout_seconds,
                params=_string_params(
                    FetchImageQuery(image_id=gid, bbox=pixel_bbox.to_string())
                ),
            )
            response.raise_for_status()
        except Exception as exc:
            raise TileFetchError(f"Failed to fetch source image for '{gid}': {exc}") from exc

        fetched_image = FetchedImagePayload.model_validate(
            _extract_first_object(response.json(), "wms/light response")
        )

        try:
            image_response = await http_client.get(fetched_image.url, timeout=timeout_seconds)
            image_response.raise_for_status()
        except Exception as exc:
            raise TileFetchError(f"Failed to download source image for '{gid}': {exc}") from exc

        return ProviderImage(
            image_bytes=image_response.content,
            pixel_bbox=pixel_bbox,
        )

    return ImageProviderClient(
        fetch_image=fetch_image,
    )


def extract_first_object(body: Any, context: str) -> Mapping[str, Any]:
    return _extract_first_object(body, context)


def _extract_first_object(body: Any, context: str) -> Mapping[str, Any]:
    if isinstance(body, Mapping):
        if "data" not in body:
            return body

        data = body["data"]
        if isinstance(data, Mapping):
            return data
        if isinstance(data, list):
            if not data:
                raise ValueError(f"{context} data list is empty.")
            first = data[0]
            if isinstance(first, Mapping):
                return first
            raise ValueError(f"{context} data item must be a JSON object.")
        raise ValueError(f"{context} data field must be object or list.")

    if isinstance(body, list):
        if not body:
            raise ValueError(f"{context} list is empty.")
        first = body[0]
        if isinstance(first, Mapping):
            return first
        raise ValueError(f"{context} list item must be a JSON object.")

    raise ValueError(f"{context} must be an object or list of objects.")


def _string_params(model: BaseModel) -> dict[str, str]:
    return {key: str(value) for key, value in model.model_dump().items()}
