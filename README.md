## Photo Diff

Async FastAPI service for image similarity via embedding cosine similarity.

### Design goals

- `FastAPI + service` split with dependency injection.
- SOLID-oriented structure:
  - `Single responsibility`: API layer handles HTTP, app orchestrates use case, embedding adapter handles outbound HTTP.
  - `Open/closed`: keep service boundaries simple and replaceable.
- Full type hints.
- BaseSettings (`pydantic-settings`) from environment.
- Async end-to-end path.
- Unit-testable components with mock-friendly seams.

### Project structure

- `src/photo_diff/cli.py`: CLI entrypoint to run uvicorn server.
- `src/photo_diff/app.py`: FastAPI app and route definitions only.
- `src/photo_diff/settings.py`: `AppSettings` BaseSettings + env loading.
- `src/photo_diff/image_input.py`: raw image input normalization/loading helpers.
- `src/photo_diff/services/comparison.py`: comparison service orchestration.
- `src/photo_diff/services/service.py`: API-facing orchestration service.
- `src/photo_diff/services/embedding.py`: HTTP embedding adapter.
- `src/photo_diff/services/similarity.py`: cosine similarity function.
- `src/tile_fetcher/app.py`: standalone FastAPI tile fetch service.
- `src/tile_fetcher/services/provider.py`: image provider integration (`wms/geo`, `wms/light`).
- `src/tile_fetcher/services/projection.py`: projection mapper integration (`g2i`, `i2g`).
- `src/tile_fetcher/services/service.py`: tile fetch service class with optional north alignment.
- `tests/`: unit tests (including mock transport/provider usage).

### Install

```bash
uv sync
```

Or with `venv` + `pip`:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

### Configure

Set values in environment or `.env`:

All settings use `PHOTO_DIFF_` env prefix (`case_sensitive=False`, `.env`, UTF-8).

- `PHOTO_DIFF_API_URL` (required)
- `PHOTO_DIFF_SENDING_SYSTEM` (required, sent as `SendingSystem` header)
- `PHOTO_DIFF_TIMEOUT_SECONDS` (optional, default `30`)
- `PHOTO_DIFF_TILE_API_BASE_URL` (required)
- `PHOTO_DIFF_TILE_EXPAND_FACTOR` (optional, default `sqrt(2)`)
- `PHOTO_DIFF_TILE_IMAGE_PROVIDER_GEO_PATH` (optional, default `/image/wms/geo`)
- `PHOTO_DIFF_TILE_IMAGE_PROVIDER_LIGHT_PATH` (optional, default `/image/wms/light`)
- `PHOTO_DIFF_TILE_PROJECTION_MAPPER_G2I_PATH` (optional, default `/image/g2i`)
- `PHOTO_DIFF_TILE_PROJECTION_MAPPER_I2G_PATH` (optional, default `/image/i2g`)
- `PHOTO_DIFF_HOST` (optional, default `127.0.0.1`)
- `PHOTO_DIFF_PORT` (optional, default `8000`)
- `PHOTO_DIFF_RELOAD` (optional, default `false`)

### Run server

```bash
uv run photo-diff
```

### Run tile fetcher as a separate service

All tile-fetcher settings use the `TILE_FETCHER_` prefix:

- `TILE_FETCHER_API_BASE_URL` (required)
- `TILE_FETCHER_EXPAND_FACTOR`
- `TILE_FETCHER_IMAGE_PROVIDER_GEO_PATH`
- `TILE_FETCHER_IMAGE_PROVIDER_LIGHT_PATH`
- `TILE_FETCHER_PROJECTION_MAPPER_G2I_PATH`
- `TILE_FETCHER_PROJECTION_MAPPER_I2G_PATH`
- `TILE_FETCHER_HOST`
- `TILE_FETCHER_PORT`
- `TILE_FETCHER_RELOAD`

Run it with:

```bash
uv run tile-fetcher
```

### API usage

POST `/compare-raw-images`:

```bash
curl -X POST http://127.0.0.1:8000/compare-raw-images \
  -H "content-type: application/json" \
  -d '{"image_a":"<base64-image-a>","image_b":"<base64-image-b>"}'
```

POST `/compare-point`:

```bash
curl -X POST http://127.0.0.1:8000/compare-point \
  -H "content-type: application/json" \
  -d '{"image_ids":["img-1","img-2","img-3"],"lon":34.78,"lat":32.08,"buffer_size_meters":12.5,"north_aligned":true}'
```

`buffer_size_meters` is the per-side buffer around the center point. A value of `12.5` means the crop is built from `12.5m` in each direction before any safety expansion for rotation.

`/compare-point` flow:

- Calls `GET /image/wms/geo?image_id=<id>&lon=<lon>&lat=<lat>` to resolve strip geo context
- Calls `GET /image/g2i?image_id=<id>&lon=<lon>&lat=<lat>` to convert geopoint to strip pixel coordinates
- Calls `GET /image/i2g?image_id=<id>&x=<x+1>&y=<y>` and `GET /image/i2g?image_id=<id>&x=<x>&y=<y+1>` to estimate local pixel resolution in meters
- Builds a target pixel envelope from `buffer_size_meters`
- Expands the target envelope by `PHOTO_DIFF_TILE_EXPAND_FACTOR` (and enforces `sqrt(2)` minimum when `north_aligned=true`)
- Calls `GET /image/wms/light?image_id=<id>&bbox=<pixel_bbox>` to fetch the light strip image
- Optionally rotates by `-azimuth` when `north_aligned=true`, then center-crops back from expanded bbox to target bbox
- Sends each aligned crop to embedding API and returns an `N x N` cosine similarity matrix

Standalone tile fetcher API:

```bash
curl -X POST http://127.0.0.1:8010/tiles/by-point \
  -H "content-type: application/json" \
  -d '{"image_ids":["img-1","img-2"],"lon":34.78,"lat":32.08,"buffer_size_meters":12.5,"north_aligned":true}'
```

### API contract

Request body sent to the embedding endpoint:

```json
{
  "image": "<base64-image-content>"
}
```

Supported embedding response shapes:

- `{"embedding": [...]}`
- `{"vector": [...]}`
- `{"data": [{"embedding": [...]}]}`
- `{"data": [{"vector": [...]}]}`

Notes:

- No additional preprocessing metadata is sent.
- Each image is posted individually using the same endpoint.
- `/compare-raw-images` always expects image content (base64 or base64 data URI), not file paths/URLs.

### Run tests

```bash
uv run python -m unittest discover -s tests -p 'test_*.py'
```
