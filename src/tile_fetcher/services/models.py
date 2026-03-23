from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from tile_fetcher.constants import (
    KEY_AZIMUTH,
    KEY_BBOX,
    KEY_IMAGE_ID,
    KEY_LAT,
    KEY_LON,
    KEY_X,
    KEY_Y,
)


@dataclass(slots=True)
class GeoPoint:
    lon: float
    lat: float

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "GeoPoint":
        return cls(lon=float(value[KEY_LON]), lat=float(value[KEY_LAT]))


@dataclass(slots=True)
class GeoBBox:
    xmin: float
    ymin: float
    xmax: float
    ymax: float

    @classmethod
    def from_string(cls, raw: str) -> "GeoBBox":
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
class ImageTile:
    image_id: str
    bbox: GeoBBox
    azimuth: float

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "ImageTile":
        image_id = str(value[KEY_IMAGE_ID]).strip()
        if not image_id:
            raise ValueError("wms/geo response must include non-empty 'image_id'.")
        return cls(
            image_id=image_id,
            bbox=GeoBBox.from_string(str(value[KEY_BBOX])),
            azimuth=float(value[KEY_AZIMUTH]),
        )


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
    def around(
        cls,
        point: PixelPoint,
        *,
        half_width: float,
        half_height: float | None = None,
    ) -> "PixelBBox":
        resolved_half_height = half_width if half_height is None else half_height
        if half_width <= 0.0 or resolved_half_height <= 0.0:
            raise ValueError("pixel half spans must be greater than 0.")
        return cls(
            xmin=point.x - half_width,
            ymin=point.y - resolved_half_height,
            xmax=point.x + half_width,
            ymax=point.y + resolved_half_height,
        )

    @property
    def width(self) -> float:
        return self.xmax - self.xmin

    @property
    def height(self) -> float:
        return self.ymax - self.ymin

    def expand(self, factor: float) -> "PixelBBox":
        if factor <= 1.0:
            raise ValueError("tile expand factor must be greater than 1.0.")
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
class ProviderImage:
    image_bytes: bytes
    azimuth: float
