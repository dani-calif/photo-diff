from __future__ import annotations

import asyncio
import base64
import binascii
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import Any, Mapping, Protocol, Sequence

import httpx
from PIL import Image

from photo_diff.constants import (
    DEFAULT_AERIAL_EXPAND_FACTOR,
    DEFAULT_AERIAL_TARGET_SIZE_RATIO,
    DEFAULT_ROTATION_SAFE_EXPAND_FACTOR,
    HTTP_SCHEME_HTTP,
    HTTP_SCHEME_HTTPS,
    KEY_AZIMUTH,
    KEY_BBOX,
    KEY_DATA,
    KEY_IMAGE_ID,
    KEY_LAT,
    KEY_LON,
    KEY_URL,
    KEY_X,
    KEY_Y,
)


class HttpGetResponse(Protocol):
    content: bytes

    def raise_for_status(self) -> None:
        ...

    def json(self) -> Any:
        ...


class HttpGetClient(Protocol):
    async def get(
        self, url: str, *, timeout: float, params: Mapping[str, str] | None = None
    ) -> HttpGetResponse:
        ...


class DefaultHttpGetClient:
    async def get(
        self, url: str, *, timeout: float, params: Mapping[str, str] | None = None
    ) -> httpx.Response:
        async with httpx.AsyncClient(timeout=timeout) as client:
            return await client.get(url, params=params)


@dataclass(slots=True)
class BBox:
    xmin: float
    ymin: float
    xmax: float
    ymax: float

    @classmethod
    def from_string(cls, raw: str) -> "BBox":
        parts = [part.strip() for part in raw.split(",")]
        if len(parts) != 4:
            raise ValueError(f"Invalid bbox '{raw}'. Expected 'xmin,ymin,xmax,ymax'.")
        xmin, ymin, xmax, ymax = (float(part) for part in parts)

        bbox = cls(xmin=xmin, ymin=ymin, xmax=xmax, ymax=ymax)
        if bbox.width <= 0 or bbox.height <= 0:
            raise ValueError(f"Invalid bbox '{raw}'. xmax/xmin and ymax/ymin must define area.")
        return bbox

    @property
    def width(self) -> float:
        return self.xmax - self.xmin

    @property
    def height(self) -> float:
        return self.ymax - self.ymin


@dataclass(slots=True)
class AerialTile:
    image_id: str
    bbox: BBox
    azimuth: float

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "AerialTile":
        image_id = str(value[KEY_IMAGE_ID]).strip()
        if not image_id:
            raise ValueError("wms/geo response must include non-empty 'image_id'.")
        bbox = BBox.from_string(str(value[KEY_BBOX]))
        azimuth = float(value[KEY_AZIMUTH])
        return cls(image_id=image_id, bbox=bbox, azimuth=azimuth)


@dataclass(slots=True)
class PixelPoint:
    x: float
    y: float

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "PixelPoint":
        return cls(x=float(value[KEY_X]), y=float(value[KEY_Y]))


@dataclass(slots=True)
class PixelBBox:
    xmin: float
    ymin: float
    xmax: float
    ymax: float

    @classmethod
    def around(cls, point: PixelPoint, *, half_span: float) -> "PixelBBox":
        if half_span <= 0.0:
            raise ValueError("pixel half span must be greater than 0.")
        return cls(
            xmin=point.x - half_span,
            ymin=point.y - half_span,
            xmax=point.x + half_span,
            ymax=point.y + half_span,
        )

    @property
    def width(self) -> float:
        return self.xmax - self.xmin

    @property
    def height(self) -> float:
        return self.ymax - self.ymin

    def expand(self, factor: float) -> "PixelBBox":
        if factor <= 1.0:
            raise ValueError("Aerial expand factor must be greater than 1.0.")
        center_x = (self.xmin + self.xmax) / 2.0
        center_y = (self.ymin + self.ymax) / 2.0
        half_width = self.width * factor / 2.0
        half_height = self.height * factor / 2.0
        return PixelBBox(
            xmin=center_x - half_width,
            ymin=center_y - half_height,
            xmax=center_x + half_width,
            ymax=center_y + half_height,
        )

    def to_string(self) -> str:
        return f"{self.xmin},{self.ymin},{self.xmax},{self.ymax}"


@dataclass(slots=True)
class WmsLightImage:
    image_bytes: bytes
    azimuth: float


class G2IClient(Protocol):
    async def geo_to_pixel(
        self, *, image_id: str, lon: float, lat: float, timeout_seconds: float
    ) -> PixelPoint:
        ...


class WmsLightClient(Protocol):
    async def fetch_image(
        self,
        *,
        image_id: str,
        pixel_bbox: PixelBBox,
        timeout_seconds: float,
    ) -> WmsLightImage:
        ...


@dataclass(slots=True)
class AerialFetchConfig:
    api_base_url: str
    expand_factor: float = DEFAULT_AERIAL_EXPAND_FACTOR
    wms_geo_path: str = "/image/wms/geo"
    wms_light_path: str = "/image/wms/light"
    g2i_path: str = "/image/g2i"

    def __post_init__(self) -> None:
        if not self.api_base_url:
            raise ValueError("aerial api base url is required.")
        if self.expand_factor <= 1.0:
            raise ValueError("aerial expand factor must be greater than 1.0.")
        if not self.wms_geo_path.startswith("/"):
            raise ValueError("wms_geo_path must start with '/'.")
        if not self.wms_light_path.startswith("/"):
            raise ValueError("wms_light_path must start with '/'.")
        if not self.g2i_path.startswith("/"):
            raise ValueError("g2i_path must start with '/'.")


class DefaultG2IClient:
    def __init__(
        self,
        *,
        api_base_url: str,
        g2i_path: str,
        http_client: HttpGetClient,
    ) -> None:
        self._api_base_url = api_base_url.rstrip("/")
        self._g2i_path = g2i_path
        self._http_client = http_client

    async def geo_to_pixel(
        self, *, image_id: str, lon: float, lat: float, timeout_seconds: float
    ) -> PixelPoint:
        response = await self._http_client.get(
            f"{self._api_base_url}{self._g2i_path}",
            timeout=timeout_seconds,
            params={
                KEY_IMAGE_ID: image_id,
                KEY_LON: str(lon),
                KEY_LAT: str(lat),
            },
        )
        response.raise_for_status()
        candidate = _extract_mapping_candidate(response.json(), "g2i response")
        return PixelPoint.from_mapping(candidate)


class DefaultWmsLightClient:
    def __init__(
        self,
        *,
        api_base_url: str,
        wms_light_path: str,
        http_client: HttpGetClient,
    ) -> None:
        self._api_base_url = api_base_url.rstrip("/")
        self._wms_light_path = wms_light_path
        self._http_client = http_client

    async def fetch_image(
        self,
        *,
        image_id: str,
        pixel_bbox: PixelBBox,
        timeout_seconds: float,
    ) -> WmsLightImage:
        response = await self._http_client.get(
            f"{self._api_base_url}{self._wms_light_path}",
            timeout=timeout_seconds,
            params={
                KEY_IMAGE_ID: image_id,
                KEY_BBOX: pixel_bbox.to_string(),
            },
        )
        response.raise_for_status()

        candidate = _extract_mapping_candidate(response.json(), "wms/light response")
        source_url = str(candidate[KEY_URL]).strip()
        if not source_url:
            raise ValueError("wms/light response must include non-empty 'url'.")

        image_response = await self._http_client.get(source_url, timeout=timeout_seconds)
        image_response.raise_for_status()
        return WmsLightImage(
            image_bytes=image_response.content,
            azimuth=float(candidate[KEY_AZIMUTH]),
        )


async def load_image_as_base64(
    image_ref: str,
    timeout_seconds: float = 30.0,
    http_client: HttpGetClient | None = None,
) -> str:
    """Load image bytes from URL/path and return base64 string."""
    client = http_client or DefaultHttpGetClient()

    if image_ref.startswith((HTTP_SCHEME_HTTP, HTTP_SCHEME_HTTPS)):
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


async def load_aerial_images_by_ids_at_geopoint_as_base64(
    *,
    image_ids: Sequence[str],
    lon: float,
    lat: float,
    timeout_seconds: float = 30.0,
    target_size_ratio: float = DEFAULT_AERIAL_TARGET_SIZE_RATIO,
    http_client: HttpGetClient | None = None,
    aerial_config: AerialFetchConfig | None = None,
    g2i_client: G2IClient | None = None,
    wms_light_client: WmsLightClient | None = None,
) -> list[str]:
    if not image_ids:
        raise ValueError("image_ids cannot be empty.")
    if aerial_config is None:
        raise ValueError(
            "Aerial image fetch requires aerial config. "
            "Set AERIAL_API_URL in environment."
        )
    if target_size_ratio <= 0.0 or target_size_ratio > 1.0:
        raise ValueError("target_size_ratio must be in the range (0, 1].")

    client = http_client or DefaultHttpGetClient()
    g2i = g2i_client or DefaultG2IClient(
        api_base_url=aerial_config.api_base_url,
        g2i_path=aerial_config.g2i_path,
        http_client=client,
    )
    wms_light = wms_light_client or DefaultWmsLightClient(
        api_base_url=aerial_config.api_base_url,
        wms_light_path=aerial_config.wms_light_path,
        http_client=client,
    )

    images_base64: list[str] = []
    for image_id in image_ids:
        normalized_id = image_id.strip()
        if not normalized_id:
            raise ValueError("image_ids must contain only non-empty strings.")

        strip_geo = await _fetch_strip_geo_context(
            api_base_url=aerial_config.api_base_url,
            wms_geo_path=aerial_config.wms_geo_path,
            image_id=normalized_id,
            lon=lon,
            lat=lat,
            timeout_seconds=timeout_seconds,
            http_client=client,
        )

        pixel_center = await g2i.geo_to_pixel(
            image_id=normalized_id,
            lon=lon,
            lat=lat,
            timeout_seconds=timeout_seconds,
        )

        strip_min_dimension = min(strip_geo.bbox.width, strip_geo.bbox.height)
        target_half_span = (strip_min_dimension * target_size_ratio) / 2.0
        target_pixel_bbox = PixelBBox.around(pixel_center, half_span=target_half_span)

        expand_factor = max(
            aerial_config.expand_factor,
            DEFAULT_ROTATION_SAFE_EXPAND_FACTOR,
        )
        expanded_pixel_bbox = target_pixel_bbox.expand(expand_factor)

        light_image = await wms_light.fetch_image(
            image_id=normalized_id,
            pixel_bbox=expanded_pixel_bbox,
            timeout_seconds=timeout_seconds,
        )

        aligned_bytes = await asyncio.to_thread(
            _north_align_and_crop_pixels,
            light_image.image_bytes,
            light_image.azimuth,
            target_pixel_bbox,
            expanded_pixel_bbox,
        )
        images_base64.append(base64.b64encode(aligned_bytes).decode("ascii"))

    return images_base64


async def _fetch_strip_geo_context(
    *,
    api_base_url: str,
    wms_geo_path: str,
    image_id: str,
    lon: float,
    lat: float,
    timeout_seconds: float,
    http_client: HttpGetClient,
) -> AerialTile:
    response = await http_client.get(
        f"{api_base_url.rstrip('/')}{wms_geo_path}",
        timeout=timeout_seconds,
        params={
            KEY_IMAGE_ID: image_id,
            KEY_LON: str(lon),
            KEY_LAT: str(lat),
        },
    )
    response.raise_for_status()
    candidates = _extract_tile_candidates(response.json())

    for candidate in candidates:
        if str(candidate[KEY_IMAGE_ID]) == image_id:
            return AerialTile.from_mapping(candidate)

    raise ValueError(f"No wms/geo tile found for image_id '{image_id}'.")


def _extract_mapping_candidate(body: Any, context: str) -> Mapping[str, Any]:
    if isinstance(body, Mapping):
        if KEY_DATA in body:
            data = body[KEY_DATA]
            if isinstance(data, list):
                if not data:
                    raise ValueError(f"{context} data list is empty.")
                candidate = data[0]
                if not isinstance(candidate, Mapping):
                    raise ValueError(f"{context} data item must be a JSON object.")
                return candidate
            if isinstance(data, Mapping):
                return data
            raise ValueError(f"{context} data field must be object or list.")
        return body

    if isinstance(body, list):
        if not body:
            raise ValueError(f"{context} list is empty.")
        candidate = body[0]
        if not isinstance(candidate, Mapping):
            raise ValueError(f"{context} list item must be a JSON object.")
        return candidate

    raise ValueError(f"{context} must be an object or list of objects.")


def _extract_tile_candidates(body: Any) -> list[Mapping[str, Any]]:
    if isinstance(body, list):
        candidates = body
    elif isinstance(body, Mapping):
        if KEY_DATA in body and isinstance(body[KEY_DATA], list):
            candidates = body[KEY_DATA]
        else:
            candidates = [body]
    else:
        raise ValueError("wms/geo response must be an object or list.")

    filtered = [item for item in candidates if isinstance(item, Mapping)]
    if not filtered:
        raise ValueError("wms/geo response does not contain tile candidates.")
    return filtered


def _north_align_and_crop_pixels(
    source_image_bytes: bytes,
    azimuth_degrees: float,
    target_bbox: PixelBBox,
    expanded_bbox: PixelBBox,
) -> bytes:
    return _north_align_and_crop_with_ratios(
        source_image_bytes=source_image_bytes,
        azimuth_degrees=azimuth_degrees,
        width_ratio=target_bbox.width / expanded_bbox.width,
        height_ratio=target_bbox.height / expanded_bbox.height,
    )


def _north_align_and_crop_with_ratios(
    *,
    source_image_bytes: bytes,
    azimuth_degrees: float,
    width_ratio: float,
    height_ratio: float,
) -> bytes:
    source = Image.open(BytesIO(source_image_bytes)).convert("RGB")
    rotated = source.rotate(
        -azimuth_degrees,
        resample=Image.Resampling.BICUBIC,
        expand=True,
    )

    crop_width = max(1, int(round(rotated.width * width_ratio)))
    crop_height = max(1, int(round(rotated.height * height_ratio)))
    crop_width = min(crop_width, rotated.width)
    crop_height = min(crop_height, rotated.height)

    center_x = rotated.width / 2.0
    center_y = rotated.height / 2.0
    left = int(round(center_x - crop_width / 2.0))
    top = int(round(center_y - crop_height / 2.0))
    left = max(0, min(left, rotated.width - crop_width))
    top = max(0, min(top, rotated.height - crop_height))

    cropped = rotated.crop((left, top, left + crop_width, top + crop_height))
    out = BytesIO()
    cropped.save(out, format="PNG")
    return out.getvalue()
