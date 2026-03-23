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
- `src/photo_diff/app.py`: FastAPI app and HTTP routes.
- `src/photo_diff/config.py`: `AppSettings` BaseSettings + env loading.
- `src/photo_diff/services/comparison.py`: comparison service orchestration.
- `src/photo_diff/services/embedding.py`: HTTP embedding adapter.
- `src/photo_diff/services/similarity.py`: cosine similarity function.
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

- `EMBEDDING_API_URL` (required)
- `EMBEDDING_API_KEY` (optional)
- `EMBEDDING_TIMEOUT_SECONDS` (optional, default `30`)
- `AERIAL_API_URL` (required for `/compare-point`)
- `AERIAL_EXPAND_FACTOR` (optional, default `sqrt(2)`)
- `AERIAL_TARGET_SIZE_RATIO` (optional, default `0.15`)
- `AERIAL_WMS_GEO_PATH` (optional, default `/image/wms/geo`)
- `AERIAL_WMS_LIGHT_PATH` (optional, default `/image/wms/light`)
- `AERIAL_G2I_PATH` (optional, default `/image/g2i`)
- `UVICORN_HOST` (optional, default `127.0.0.1`)
- `UVICORN_PORT` (optional, default `8000`)
- `UVICORN_RELOAD` (optional, default `false`)

### Run server

```bash
uv run photo-diff
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
  -d '{"image_ids":["img-1","img-2","img-3"],"lon":34.78,"lat":32.08}'
```

`/compare-point` aerial fetch flow:

- Calls `GET /image/wms/geo?image_id=<id>&lon=<lon>&lat=<lat>` to resolve strip geo context
- Calls `GET /image/g2i?image_id=<id>&lon=<lon>&lat=<lat>` to convert geopoint to strip pixel coordinates
- Builds a target pixel envelope around `(x, y)` using `AERIAL_TARGET_SIZE_RATIO` of strip size (relative, not absolute pixels)
- Expands the target envelope by `max(AERIAL_EXPAND_FACTOR, sqrt(2))` to reduce black padding risk after rotation
- Calls `GET /image/wms/light?image_id=<id>&bbox=<pixel_bbox>` to fetch the light strip image
- Rotates by `-azimuth`, then center-crops back from expanded bbox to target bbox
- Sends each aligned crop to embedding API and returns an `N x N` cosine similarity matrix

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
