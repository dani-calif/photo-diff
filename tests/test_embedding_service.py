from __future__ import annotations

import unittest

from photo_diff.services.embedding import EmbeddingApiError, ImageEmbeddingService


class FakeResponse:
    def __init__(self, *, status_code: int, body: object, text: str = "") -> None:
        self.status_code = status_code
        self._body = body
        self.text = text

    def json(self) -> object:
        return self._body


class FakeTransport:
    def __init__(self, responses: list[FakeResponse]) -> None:
        self.responses = responses
        self.calls: list[dict[str, object]] = []

    async def post(
        self,
        url: str,
        *,
        json: dict[str, object],
        headers: dict[str, str],
        timeout: float,
    ) -> FakeResponse:
        self.calls.append(
            {
                "url": url,
                "json": json,
                "headers": headers,
                "timeout": timeout,
            }
        )
        if not self.responses:
            raise RuntimeError("No fake responses left.")
        return self.responses.pop(0)


class ImageEmbeddingServiceTests(unittest.IsolatedAsyncioTestCase):
    async def test_embed_images_builds_expected_request_and_parses_response(self) -> None:
        transport = FakeTransport(
            [
                FakeResponse(status_code=200, body={"embedding": [1, 2]}),
                FakeResponse(status_code=200, body={"embedding": [3, 4]}),
            ]
        )

        service = ImageEmbeddingService(
            api_url="https://api.example.com/embed/image",
            sending_system="unit-test",
            timeout_seconds=9.0,
            transport=transport,
        )

        embeddings = await service.embed_images(["b64-a", "b64-b"])

        self.assertEqual(embeddings, [[1.0, 2.0], [3.0, 4.0]])
        self.assertEqual(len(transport.calls), 2)

        first_call = transport.calls[0]
        self.assertEqual(first_call["url"], "https://api.example.com/embed/image")
        self.assertEqual(first_call["timeout"], 9.0)
        self.assertEqual(
            first_call["headers"],
            {"Content-Type": "application/json", "SendingSystem": "unit-test"},
        )
        self.assertEqual(first_call["json"], {"image": "b64-a"})

        second_call = transport.calls[1]
        self.assertEqual(second_call["json"], {"image": "b64-b"})

    async def test_embed_images_raises_for_http_error_payload(self) -> None:
        transport = FakeTransport(
            [FakeResponse(status_code=400, body={"error": "bad"}, text="bad request")]
        )

        service = ImageEmbeddingService(
            api_url="https://api.example.com/embed/image",
            sending_system="unit-test",
            transport=transport,
        )

        with self.assertRaisesRegex(EmbeddingApiError, "Embedding API error 400"):
            await service.embed_images(["b64-a"])


if __name__ == "__main__":
    unittest.main()
