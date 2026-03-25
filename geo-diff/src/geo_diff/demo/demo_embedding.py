from __future__ import annotations

import base64
import io
from typing import Sequence

from PIL import Image, ImageFilter, ImageStat
from geo_diff.services.embedding import ImageEmbedder


class DemoImageEmbeddingService(ImageEmbedder):
    async def embed_images(self, images_base64: Sequence[str]) -> list[list[float]]:
        return [_embed_image(image_b64) for image_b64 in images_base64]


def _embed_image(image_b64: str) -> list[float]:
    image_bytes = base64.b64decode(image_b64)
    with Image.open(io.BytesIO(image_bytes)) as image:
        rgb = image.convert("RGB").resize((128, 128))
        edge_image = rgb.filter(ImageFilter.FIND_EDGES).convert("L")

    histogram = rgb.histogram()
    stats = ImageStat.Stat(rgb)
    edge_stats = ImageStat.Stat(edge_image)

    embedding: list[float] = []
    pixels = float(rgb.width * rgb.height)
    for channel in range(3):
        start = channel * 256
        channel_histogram = histogram[start : start + 256]
        for bucket in range(16):
            bucket_start = bucket * 16
            bucket_end = bucket_start + 16
            embedding.append(sum(channel_histogram[bucket_start:bucket_end]) / pixels)

    embedding.extend(value / 255.0 for value in stats.mean)
    embedding.extend(value / 255.0 for value in stats.stddev)
    embedding.append(edge_stats.mean[0] / 255.0)
    return embedding
