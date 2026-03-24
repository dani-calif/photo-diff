from __future__ import annotations

from dataclasses import dataclass

from shapely.geometry import Point


@dataclass(slots=True)
class XYXYBox:
    xmin: float
    ymin: float
    xmax: float
    ymax: float

    @classmethod
    def from_string(cls, raw: str) -> "XYXYBox":
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

    @classmethod
    def around_point(
        cls,
        point: Point,
        *,
        half_width: float,
        half_height: float | None = None,
    ) -> "XYXYBox":
        resolved_half_height = half_width if half_height is None else half_height
        if half_width <= 0.0 or resolved_half_height <= 0.0:
            raise ValueError("box half spans must be greater than 0.")
        return cls(
            xmin=point.x - half_width,
            ymin=point.y - resolved_half_height,
            xmax=point.x + half_width,
            ymax=point.y + resolved_half_height,
        )

    def expand(self, factor: float) -> "XYXYBox":
        if factor <= 1.0:
            raise ValueError("box expand factor must be greater than 1.0.")
        center_x = (self.xmin + self.xmax) / 2.0
        center_y = (self.ymin + self.ymax) / 2.0
        half_width = self.width * factor / 2.0
        half_height = self.height * factor / 2.0
        return XYXYBox(
            xmin=center_x - half_width,
            ymin=center_y - half_height,
            xmax=center_x + half_width,
            ymax=center_y + half_height,
        )

    def to_string(self) -> str:
        return f"{self.xmin},{self.ymin},{self.xmax},{self.ymax}"


@dataclass(slots=True)
class ResolvedImage:
    bounds: XYXYBox
    azimuth: float


@dataclass(slots=True)
class ProviderImage:
    image_bytes: bytes
    azimuth: float
