# syntax=docker/dockerfile:1.7
# ---- Stage 1: builder ----
# Install production dependencies (ingestion dependency-group + local-rag
# extras) into an isolated venv via uv. This stage caches well: changes to
# src/ invalidate only the second uv sync (project install), not the
# dependency resolution layer.
FROM python:3.14-slim AS builder

ENV UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1 \
    UV_PYTHON_DOWNLOADS=never \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Build tools: scikit-network (a Ragas transitive dep) ships no wheel for
# Python 3.14 yet and needs a C++ compiler to build from source.
# Runtime stage does NOT inherit these; the final image only carries the
# built wheels inside the venv.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
        gcc \
        g++ \
    && rm -rf /var/lib/apt/lists/*

# uv is a static binary with no system dependencies. Installing it via pip
# here keeps the builder to a single base image and matches the host's
# pinned uv version.
RUN pip install --no-cache-dir uv

WORKDIR /app/backend

# Install prod dependencies first (cache-friendly: src/ changes do not
# invalidate this layer). `--no-install-project` skips building the
# editable install until src/ is in place.
COPY backend/pyproject.toml backend/uv.lock ./
RUN uv sync --frozen --no-install-project --no-dev --group ingestion --extra local-rag

# Now overlay the project itself (README + source). The second uv sync
# performs the editable install using the cached deps layer above.
COPY backend/README.md ./
COPY backend/src ./src
RUN uv sync --frozen --no-dev --group ingestion --extra local-rag

# ---- Stage 2: runtime ----
# Minimal image: python runtime + the prepared venv + source. No compilers,
# no pip caches, no build tools. The non-root user matches the host uid
# convention used by the local Docker setup.
FROM python:3.14-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PATH="/app/backend/.venv/bin:${PATH}"

# uv is required for the `uv run --no-sync` CMD below. Copy the static
# binary from the builder instead of re-running pip in this stage.
COPY --from=builder /usr/local/bin/uv /usr/local/bin/uv
COPY --from=builder /usr/local/bin/uvx /usr/local/bin/uvx

WORKDIR /app/backend

# Non-root user. Using a fixed uid/gid (1001) keeps file ownership stable
# when the host mounts volumes over /app/backend.
RUN groupadd --system --gid 1001 app \
    && useradd --system --uid 1001 --gid app --no-create-home --shell /usr/sbin/nologin app

# Copy the prepared venv and the source tree from the builder.
COPY --from=builder --chown=app:app /app/backend/.venv /app/backend/.venv
COPY --from=builder --chown=app:app /app/backend/README.md /app/backend/README.md
COPY --from=builder --chown=app:app /app/backend/src /app/backend/src

USER app
EXPOSE 8000

# `--no-sync` prevents the container from trying to mutate uv.lock at
# startup. Configuration is injected at runtime via env vars (or
# `--env-file ops/local.env`) — never baked into the image.
CMD ["uv", "run", "--no-sync", "uvicorn", "asgi_local:app", "--host", "0.0.0.0", "--port", "8000"]
