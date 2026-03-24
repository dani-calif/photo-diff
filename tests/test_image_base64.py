from __future__ import annotations

import base64
import tempfile
import unittest
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from geo_diff.image_base64 import load_image_ref_as_base64, normalize_image_base64


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
        self,
        url: str,
        *,
        timeout: float,
        params: Mapping[str, str] | None = None,
    ) -> _FakeResponse:
        del timeout
        self.calls.append((url, params))
        if not self._responses:
            raise RuntimeError("No fake responses left")
        return self._responses.pop(0)


class ImageBase64Tests(unittest.IsolatedAsyncioTestCase):
    async def test_load_image_ref_as_base64_reads_local_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            file_path = Path(tmp_dir) / "sample.bin"
            file_path.write_bytes(b"abc")

            encoded = await load_image_ref_as_base64(str(file_path))

        self.assertEqual(encoded, base64.b64encode(b"abc").decode("ascii"))

    async def test_load_image_ref_as_base64_reads_http_url(self) -> None:
        client = _FakeHttpClient(responses=[_FakeResponse(content=b"xyz")])

        encoded = await load_image_ref_as_base64(
            "https://example.com/image.png",
            timeout_seconds=5.0,
            http_client=client,
        )

        self.assertEqual(encoded, base64.b64encode(b"xyz").decode("ascii"))
        self.assertEqual(client.calls[0][0], "https://example.com/image.png")

    def test_normalize_image_base64_accepts_data_uri(self) -> None:
        normalized = normalize_image_base64("data:image/png;base64,YQ==")
        self.assertEqual(normalized, "YQ==")

    def test_normalize_image_base64_rejects_invalid_payload(self) -> None:
        with self.assertRaisesRegex(ValueError, "valid base64"):
            normalize_image_base64("bad-value")


if __name__ == "__main__":
    unittest.main()
