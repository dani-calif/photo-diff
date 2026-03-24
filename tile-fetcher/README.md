# Tile Fetcher

`tile-fetcher` is both:

- a reusable Python library for fetching and rectifying tiles
- a FastAPI service wrapper around that same library

The core logic lives in `src/tile_fetcher/`, and the FastAPI app in `src/tile_fetcher/app.py` is just wiring around that logic.

## Project Structure

- `src/tile_fetcher/services/`: tile fetch geometry and warp logic
- `src/tile_fetcher/utils/`: HTTP adapter clients
- `src/tile_fetcher/app.py`: FastAPI app
- `src/tile_fetcher/settings.py`: service settings
- `tests/`: tile fetch tests

## Configure

Settings use the `TILE_FETCHER_` prefix:

- `TILE_FETCHER_API_BASE_URL`
- `TILE_FETCHER_TIMEOUT_SECONDS`
- `TILE_FETCHER_IMAGE_PROVIDER_LIGHT_PATH`
- `TILE_FETCHER_PROJECTION_MAPPER_G2I_PATH`
- `TILE_FETCHER_HOST`
- `TILE_FETCHER_PORT`
- `TILE_FETCHER_RELOAD`

## Run

```bash
uv sync
uv run tile-fetcher
```

## Test

```bash
uvx pyright -p pyrightconfig.json
uv run python -m unittest discover -s tests -p 'test_*.py'
```
