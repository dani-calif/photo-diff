from __future__ import annotations

import asyncio
import base64
import io
import json
import shutil
from pathlib import Path
from typing import Sequence

import rasterio
from rasterio.enums import Resampling
from rasterio.warp import transform
from PIL import Image, ImageChops, ImageDraw, ImageFont, ImageOps
from shapely.geometry import Point

from geo_diff.demo.demo_embedding import DemoImageEmbeddingService
from geo_diff.demo.raster_tile_fetcher import (
    DemoRasterScene,
    build_demo_rasterio_image_provider,
    build_demo_rasterio_projection_mapper,
)
from geo_diff.services.comparison import ImageComparisonService
from geo_diff.services.service import GeoDiffService
from tile_fetcher import TileFetchService

OUTPUT_DIR = Path(__file__).resolve().parents[1] / "demo_output" / "real_sentinel_cog"
FONT = ImageFont.load_default()
WGS84_CRS = "EPSG:4326"
SCENES = {
    "s2-2024-04-01": DemoRasterScene(
        gid="s2-2024-04-01",
        raster_ref=(
            "https://sentinel-cogs.s3.us-west-2.amazonaws.com/"
            "sentinel-s2-l2a-cogs/12/R/UU/2024/4/S2A_12RUU_20240401_0_L2A/TCI.tif"
        ),
        azimuth_degrees=17.0,
    ),
    "s2-2024-04-26": DemoRasterScene(
        gid="s2-2024-04-26",
        raster_ref=(
            "https://sentinel-cogs.s3.us-west-2.amazonaws.com/"
            "sentinel-s2-l2a-cogs/12/R/UU/2024/4/S2B_12RUU_20240426_0_L2A/TCI.tif"
        ),
        azimuth_degrees=-11.0,
    ),
}
BUFFER_SIZE_METERS = 600.0


async def main() -> None:
    _reset_output_dir(OUTPUT_DIR)
    points = _demo_points(next(iter(SCENES.values())))

    tile_fetch_service = TileFetchService(
        image_provider=build_demo_rasterio_image_provider(SCENES),
        projection_mapper=build_demo_rasterio_projection_mapper(SCENES),
        timeout_seconds=30.0,
        expand_factor=1.6,
    )
    comparison_service = ImageComparisonService(DemoImageEmbeddingService())
    geo_diff_service = GeoDiffService(
        comparison_service=comparison_service,
        tile_fetch_service=tile_fetch_service,
    )

    summary = {
        "buffer_size_meters": BUFFER_SIZE_METERS,
        "scenes": {gid: scene.raster_ref for gid, scene in SCENES.items()},
        "scene_azimuths": {gid: scene.azimuth_degrees for gid, scene in SCENES.items()},
        "points": {},
    }
    for label, point in points.items():
        rows: list[tuple[str, Image.Image, Image.Image, Image.Image]] = []
        north_images: dict[str, Image.Image] = {}
        for gid, scene in SCENES.items():
            preview = _render_source_preview(scene.raster_ref, point)
            raw_crop = _decode_image(
                (
                    await tile_fetch_service.fetch_tiles_at_point_as_base64(
                        image_ids=[gid],
                        lon=point.x,
                        lat=point.y,
                        buffer_size_meters=BUFFER_SIZE_METERS,
                        north_aligned=False,
                    )
                )[0]
            )
            north_crop = _decode_image(
                (
                    await tile_fetch_service.fetch_tiles_at_point_as_base64(
                        image_ids=[gid],
                        lon=point.x,
                        lat=point.y,
                        buffer_size_meters=BUFFER_SIZE_METERS,
                        north_aligned=True,
                    )
                )[0]
            )
            preview.save(OUTPUT_DIR / f"{label}_{gid}_preview.png")
            raw_crop.save(OUTPUT_DIR / f"{label}_{gid}_crop_raw.png")
            north_crop.save(OUTPUT_DIR / f"{label}_{gid}_crop_north.png")
            rows.append((gid, preview, raw_crop, north_crop))
            north_images[gid] = north_crop

        _build_overview(rows).save(OUTPUT_DIR / f"{label}_overview.png")
        ImageChops.difference(
            north_images["s2-2024-04-01"],
            north_images["s2-2024-04-26"],
        ).save(OUTPUT_DIR / f"{label}_difference.png")

        comparison = await geo_diff_service.compare_point(
            image_ids=list(SCENES),
            lon=point.x,
            lat=point.y,
            buffer_size_meters=BUFFER_SIZE_METERS,
            north_aligned=True,
        )
        _build_matrix_image(comparison.image_ids, comparison.cosine_similarity_matrix).save(
            OUTPUT_DIR / f"{label}_matrix.png"
        )
        summary["points"][label] = {
            "lon": point.x,
            "lat": point.y,
            "comparison_matrix": comparison.cosine_similarity_matrix,
        }

    (OUTPUT_DIR / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(f"Real Sentinel COG demo written to {OUTPUT_DIR}")


def _demo_points(scene: DemoRasterScene) -> dict[str, Point]:
    with rasterio.open(scene.raster_ref) as dataset:
        left, bottom, right, top = dataset.bounds
        if str(dataset.crs) != WGS84_CRS:
            xs, ys = _transform_xy(dataset.crs, WGS84_CRS, [left, right], [bottom, top])
            left, right = min(xs), max(xs)
            bottom, top = min(ys), max(ys)
    return {
        "center": Point((left + right) / 2.0, (bottom + top) / 2.0),
        "northwest": Point(
            left + ((right - left) * 0.30),
            bottom + ((top - bottom) * 0.70),
        ),
        "southeast": Point(
            left + ((right - left) * 0.70),
            bottom + ((top - bottom) * 0.30),
        ),
    }


def _reset_output_dir(output_dir: Path) -> None:
    if output_dir.exists():
        for path in output_dir.iterdir():
            if path.is_dir():
                shutil.rmtree(path)
            else:
                path.unlink()
    output_dir.mkdir(parents=True, exist_ok=True)


def _render_source_preview(raster_ref: str, point: Point) -> Image.Image:
    with rasterio.open(raster_ref) as dataset:
        data = dataset.read(
            indexes=[1, 2, 3],
            out_shape=(3, 512, 512),
            resampling=Resampling.bilinear,
        )
        if str(dataset.crs) == WGS84_CRS:
            x, y = point.x, point.y
        else:
            xs, ys = _transform_xy(WGS84_CRS, dataset.crs, [point.x], [point.y])
            x, y = xs[0], ys[0]
        row, col = dataset.index(x, y)
        scaled_x = int(round((col / dataset.width) * 512.0))
        scaled_y = int(round((row / dataset.height) * 512.0))
    preview = Image.fromarray(data.transpose(1, 2, 0).astype("uint8"), mode="RGB")
    draw = ImageDraw.Draw(preview)
    draw.ellipse(
        (scaled_x - 8, scaled_y - 8, scaled_x + 8, scaled_y + 8),
        fill=(255, 80, 80),
        outline=(255, 255, 255),
        width=2,
    )
    return preview


def _decode_image(image_b64: str) -> Image.Image:
    return Image.open(io.BytesIO(base64.b64decode(image_b64))).convert("RGB")


def _build_overview(rows: list[tuple[str, Image.Image, Image.Image, Image.Image]]) -> Image.Image:
    cards = []
    for gid, preview, raw_crop, north_crop in rows:
        cards.append(
            _stack_horizontally(
                [
                    _build_text_card([gid], (180, 390)),
                    _build_labeled_card("preview", preview, (320, 320)),
                    _build_labeled_card("raw crop", raw_crop, (320, 320)),
                    _build_labeled_card("northened crop", north_crop, (320, 320)),
                ]
            )
        )
    return _stack_vertically(cards)


def _build_matrix_image(labels: list[str], matrix: list[list[float]]) -> Image.Image:
    cell = 180
    margin = 190
    size = margin + cell * len(labels)
    image = Image.new("RGB", (size, size), color=(255, 255, 255))
    draw = ImageDraw.Draw(image)
    for index, label in enumerate(labels):
        draw.text((16, margin + index * cell + 70), label, fill=(20, 20, 20), font=FONT)
        draw.text((margin + index * cell + 24, 20), label, fill=(20, 20, 20), font=FONT)
    for row_index, row in enumerate(matrix):
        for col_index, value in enumerate(row):
            x0 = margin + col_index * cell
            y0 = margin + row_index * cell
            draw.rectangle((x0, y0, x0 + cell, y0 + cell), fill=_matrix_color(value))
            draw.text((x0 + 46, y0 + 80), f"{value:.3f}", fill=(0, 0, 0), font=FONT)
    return image


def _build_labeled_card(label: str, image: Image.Image, thumb_size: tuple[int, int]) -> Image.Image:
    card = Image.new("RGB", (thumb_size[0] + 24, thumb_size[1] + 52), color=(255, 255, 255))
    draw = ImageDraw.Draw(card)
    draw.text((12, 12), label, fill=(20, 20, 20), font=FONT)
    thumb = ImageOps.contain(image, thumb_size)
    card.paste(thumb, (12 + (thumb_size[0] - thumb.width) // 2, 38 + (thumb_size[1] - thumb.height) // 2))
    return card


def _build_text_card(lines: list[str], size: tuple[int, int]) -> Image.Image:
    image = Image.new("RGB", size, color=(255, 255, 255))
    draw = ImageDraw.Draw(image)
    y = 18
    for line in lines:
        draw.text((18, y), line, fill=(20, 20, 20), font=FONT)
        y += 20
    return image


def _stack_horizontally(images: list[Image.Image]) -> Image.Image:
    width = sum(image.width for image in images) + 12 * (len(images) - 1)
    height = max(image.height for image in images)
    canvas = Image.new("RGB", (width, height), color=(242, 245, 248))
    x = 0
    for image in images:
        canvas.paste(image, (x, 0))
        x += image.width + 12
    return canvas


def _stack_vertically(images: list[Image.Image]) -> Image.Image:
    width = max(image.width for image in images)
    height = sum(image.height for image in images) + 12 * (len(images) - 1)
    canvas = Image.new("RGB", (width, height), color=(242, 245, 248))
    y = 0
    for image in images:
        canvas.paste(image, (0, y))
        y += image.height + 12
    return canvas


def _matrix_color(value: float) -> tuple[int, int, int]:
    clamped = max(-1.0, min(1.0, value))
    red = int(230 - (clamped * 60))
    green = int(180 + (clamped * 60))
    blue = int(230 - (clamped * 120))
    return red, green, blue


def _transform_xy(
    source_crs: object,
    target_crs: object,
    xs: Sequence[float],
    ys: Sequence[float],
) -> tuple[list[float], list[float]]:
    transformed = transform(source_crs, target_crs, list(xs), list(ys))
    if len(transformed) < 2:
        raise ValueError("Coordinate transform must return x/y sequences.")
    return transformed[0], transformed[1]


if __name__ == "__main__":
    asyncio.run(main())
