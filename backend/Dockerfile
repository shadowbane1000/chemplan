# Multi-stage Python build for chemplan backend.
#
# Build context is the repository root (matches docker build -f backend/Dockerfile .)
# so we can pull both backend/ and docker/ in one image.
#
# Uses python:3.11-slim (glibc) — alpine breaks RDKit / onnxruntime wheels.
# AiZynthFinder model data (~750MB) is NOT baked into the image; it's
# bind-mounted from /opt/chemplan/data on the host. The entrypoint
# auto-downloads on first run if the volume is empty.

FROM python:3.11-slim AS builder

ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN apt-get update && apt-get install -y --no-install-recommends \
      build-essential \
      libhdf5-dev \
      curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /src
COPY backend/pyproject.toml ./
COPY backend/app ./app
RUN pip install --prefix=/install -e . \
    && find /install -type d -name __pycache__ -exec rm -rf {} +

# ---------- Runtime ----------------------------------------------------------

FROM python:3.11-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/install/bin:${PATH}" \
    PYTHONPATH="/install/lib/python3.11/site-packages:${PYTHONPATH}"

# libgomp + libxrender for RDKit; curl for in-network healthcheck.
RUN apt-get update && apt-get install -y --no-install-recommends \
      libgomp1 \
      libxrender1 \
      libxext6 \
      curl \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /install /install

WORKDIR /app
COPY backend/app ./app
COPY backend/pyproject.toml ./
COPY docker/backend-entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/entrypoint.sh

RUN mkdir -p /app/data
VOLUME ["/app/data"]

EXPOSE 8123

ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8123"]
