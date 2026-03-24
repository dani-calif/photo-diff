# Geo Diff Monorepo

This repository now contains two separate Python projects:

- `geo-diff/`: the image comparison service and demo code
- `tile-fetcher/`: the reusable tile fetching library and FastAPI service

`geo-diff` depends on `tile-fetcher` as a local package. That keeps the integration in-process here, while preserving the option to deploy `tile-fetcher` separately or move it into its own repository later.

## Layout

- [geo-diff](/Users/nirbarel/Documents/Nir/IDF/clip_retriever/photo-diff/geo-diff)
- [tile-fetcher](/Users/nirbarel/Documents/Nir/IDF/clip_retriever/photo-diff/tile-fetcher)
- [patches](/Users/nirbarel/Documents/Nir/IDF/clip_retriever/photo-diff/patches)

## Common Commands

Sync dependencies:

```bash
(cd geo-diff && uv sync)
(cd tile-fetcher && uv sync)
```

Run the services:

```bash
(cd geo-diff && uv run geo-diff)
(cd tile-fetcher && uv run tile-fetcher)
```

Run checks:

```bash
(cd geo-diff && uvx pyright -p pyrightconfig.json --outputjson)
(cd geo-diff && uv run python -m unittest discover -s tests -p 'test_*.py')
(cd tile-fetcher && uvx pyright -p pyrightconfig.json --outputjson)
(cd tile-fetcher && uv run python -m unittest discover -s tests -p 'test_*.py')
```
