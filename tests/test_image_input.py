from __future__ import annotations

import base64
import tempfile
import unittest
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import Any, Mapping

from PIL import Image, ImageDraw

from photo_diff.image_input import (
    AerialFetchConfig,
    PixelBBox,
    PixelPoint,
    WmsLightImage,
    load_aerial_images_by_ids_at_geopoint_as_base64,
    load_image_as_base64,
    normalize_image_base64,
)


@dataclass(slots=True)
class _FakeResponse:
    body: Any | None = None
    content: bytes = b""
    status_code: int = 200

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def json(self) -> Any:
        if self.body is None:
            raise ValueError("No JSON body")
        return self.body


class _FakeHttpClient:
    def __init__(self, responses: list[_FakeResponse]) -> None:
        self._responses = responses
        self.calls: list[tuple[str, Mapping[str, str] | None]] = []

    async def get(
        self, url: str, *, timeout: float, params: Mapping[str, str] | None = None
    ) -> _FakeResponse:
        del timeout
        self.calls.append((url, params))
        if not self._responses:
            raise RuntimeError("No fake responses left")
        return self._responses.pop(0)


class _FakeG2IClient:
    def __init__(self, points: dict[str, PixelPoint]) -> None:
        self._points = points
        self.calls: list[tuple[str, float, float, float]] = []

    async def geo_to_pixel(
        self, *, image_id: str, lon: float, lat: float, timeout_seconds: float
    ) -> PixelPoint:
        self.calls.append((image_id, lon, lat, timeout_seconds))
        return self._points[image_id]


class _FakeWmsLightClient:
    def __init__(self, image_bytes: bytes, azimuth: float) -> None:
        self._image_bytes = image_bytes
        self._azimuth = azimuth
        self.calls: list[tuple[str, str, float]] = []

    async def fetch_image(
        self,
        *,
        image_id: str,
        pixel_bbox: PixelBBox,
        timeout_seconds: float,
    ) -> WmsLightImage:
        self.calls.append((image_id, pixel_bbox.to_string(), timeout_seconds))
        return WmsLightImage(image_bytes=self._image_bytes, azimuth=self._azimuth)


class ImageInputTests(unittest.IsolatedAsyncioTestCase):
    async def test_load_image_as_base64_reads_local_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            file_path = Path(tmp_dir) / "sample.bin"
            file_path.write_bytes(b"abc")

            encoded = await load_image_as_base64(str(file_path))

        self.assertEqual(encoded, base64.b64encode(b"abc").decode("ascii"))

    async def test_load_image_as_base64_reads_http_url(self) -> None:
        client = _FakeHttpClient(responses=[_FakeResponse(content=b"xyz")])

        encoded = await load_image_as_base64(
            "https://example.com/image.png",
            timeout_seconds=5.0,
            http_client=client,
        )

        self.assertEqual(encoded, base64.b64encode(b"xyz").decode("ascii"))
        self.assertEqual(client.calls[0][0], "https://example.com/image.png")

    async def test_load_aerial_images_by_ids_at_geopoint_as_base64(self) -> None:
        source_bytes = _make_split_color_image()
        client = _FakeHttpClient(
            responses=[
                _FakeResponse(
                    body={"image_id": "img-1", "bbox": "0,0,20,20", "azimuth": 15.0}
                ),
                _FakeResponse(
                    body={"image_id": "img-2", "bbox": "0,0,20,20", "azimuth": 30.0}
                ),
            ]
        )
        g2i = _FakeG2IClient(
            points={
                "img-1": PixelPoint(x=100.0, y=120.0),
                "img-2": PixelPoint(x=150.0, y=160.0),
            }
        )
        wms_light = _FakeWmsLightClient(image_bytes=source_bytes, azimuth=90.0)
        config = AerialFetchConfig(
            api_base_url="https://aerial.example.com",
            expand_factor=2.0,
            wms_geo_path="/image/wms/geo",
            wms_light_path="/image/wms/light",
            g2i_path="/image/g2i",
        )

        encoded = await load_aerial_images_by_ids_at_geopoint_as_base64(
            image_ids=["img-1", "img-2"],
            lon=10.0,
            lat=10.0,
            target_size_ratio=0.5,
            timeout_seconds=10.0,
            http_client=client,
            aerial_config=config,
            g2i_client=g2i,
            wms_light_client=wms_light,
        )

        self.assertEqual(len(encoded), 2)
        self.assertTrue(all(isinstance(item, str) and item for item in encoded))
        self.assertEqual(
            client.calls[0],
            (
                "https://aerial.example.com/image/wms/geo",
                {"image_id": "img-1", "lon": "10.0", "lat": "10.0"},
            ),
        )
        self.assertEqual(
            client.calls[1],
            (
                "https://aerial.example.com/image/wms/geo",
                {"image_id": "img-2", "lon": "10.0", "lat": "10.0"},
            ),
        )
        self.assertEqual(
            g2i.calls,
            [
                ("img-1", 10.0, 10.0, 10.0),
                ("img-2", 10.0, 10.0, 10.0),
            ],
        )
        self.assertEqual(len(wms_light.calls), 2)

    def test_normalize_image_base64_accepts_data_uri(self) -> None:
        normalized = normalize_image_base64("data:image/png;base64,YQ==")
        self.assertEqual(normalized, "YQ==")

    def test_normalize_image_base64_rejects_invalid_payload(self) -> None:
        with self.assertRaisesRegex(ValueError, "valid base64"):
            normalize_image_base64("bad-value")


def _make_split_color_image() -> bytes:
    image = Image.new("RGB", (400, 400), color=(0, 0, 0))
    draw = ImageDraw.Draw(image)
    draw.rectangle((0, 0, 199, 399), fill=(255, 0, 0))
    draw.rectangle((200, 0, 399, 399), fill=(0, 0, 255))

    out = BytesIO()
    image.save(out, format="PNG")
    return out.getvalue()


if __name__ == "__main__":
    unittest.main()
