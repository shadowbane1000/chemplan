# backend

FastAPI wrapping AiZynthFinder.

## Setup

Requires `uv` (https://docs.astral.sh/uv/).

```sh
uv venv --python 3.11 .venv
uv pip install -e .
```

## Download the USPTO model

AiZynthFinder needs ~750MB of public data (USPTO-trained ONNX policy networks + ZINC stock).

```sh
.venv/bin/download_public_data data/
```

Outputs land in `data/` and are gitignored. The generated `data/config.yml` references absolute paths — if you move the directory, regenerate it.

## Run

```sh
.venv/bin/uvicorn app.main:app --reload --port 8123
```

- `GET /health` → liveness check.
- `POST /plan` with `{"smiles": "..."}` → top retrosynthesis route as JSON.

The first `/plan` call loads the policy networks (~5-8s). Subsequent calls are warm.
