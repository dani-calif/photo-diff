# Geo Diff

`geo-diff` compares imagery using embedding similarity. It consumes `tile-fetcher` as a local Python package in this repository, so it can fetch tiles in-process without making extra HTTP calls.

## Project Structure

- `src/geo_diff/app.py`: FastAPI app and routes
- `src/geo_diff/services/`: comparison and orchestration logic
- `src/geo_diff/settings.py`: environment-based settings
- `src/geo_diff/demo/`: demo-only helpers
- `scripts/sentinel_cog_demo.py`: real Sentinel COG demo
- `tests/`: `geo_diff` and demo tests

## Configure

Settings use the `GEO_DIFF_` prefix:

- `GEO_DIFF_API_URL`
- `GEO_DIFF_SENDING_SYSTEM`
- `GEO_DIFF_EMBEDDER_BACKEND` (`http` or `internal`)
- `GEO_DIFF_TIMEOUT_SECONDS`
- `GEO_DIFF_HOST`
- `GEO_DIFF_PORT`
- `GEO_DIFF_RELOAD`

Example values are in [.env.example](/Users/nirbarel/Documents/Nir/IDF/clip_retriever/photo-diff/geo-diff/.env.example).

## Run

```bash
uv sync
uv run geo-diff
```

Because `tile-fetcher` is declared as a local path dependency, `uv sync` here also installs the sibling `tile-fetcher` package. If `internal/` exists, the default `internal` dependency group also installs `geo-diff-internal` from the local `internal` package.

If you need an internal embedder adapter, install the internal adapter package into the same
environment and set `GEO_DIFF_EMBEDDER_BACKEND=internal`.

## Test

```bash
uvx pyright -p pyrightconfig.json
uv run python -m unittest discover -s tests -p 'test_*.py'
```
