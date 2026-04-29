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

## Anthropic API key

The chat endpoint calls Claude. Copy `.env.example` to `.env` and fill in `ANTHROPIC_API_KEY`:

```sh
cp .env.example .env
$EDITOR .env
```

`/chat` will return an error message in the stream if the key is missing — `/plan` and `/health` work without it.

## Run

```sh
.venv/bin/uvicorn app.main:app --reload --port 8123
```

- `GET /health` → liveness check.
- `POST /plan` with `{"smiles": "..."}` → top retrosynthesis route as JSON.
- `POST /chat` with `{"history": [...], "canvas_smiles": "...", "plan": {...}}` → NDJSON stream of `{"type": "delta", "text": "..."}` lines, ending with `{"type": "done", "usage": ...}`. Errors stream as `{"type": "error", "message": "..."}`.

The first `/plan` call loads the policy networks (~5-8s). Subsequent calls are warm.
