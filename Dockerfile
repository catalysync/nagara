# syntax=docker/dockerfile:1.7

# Multi-stage Dockerfile.
# Stage 1: build a frozen virtualenv with uv using the locked deps.
# Stage 2: copy that venv into a minimal runtime image, run as a non-root user.

# ── Builder ─────────────────────────────────────────────────────────────────
FROM python:3.14-slim-bookworm AS builder

# uv is published as a tiny static binary — copy it from the official image
# rather than installing via pip (avoids wheel build + cache pollution).
COPY --from=ghcr.io/astral-sh/uv:0.11.7 /uv /uvx /usr/local/bin/

ENV UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1 \
    UV_PYTHON_DOWNLOADS=never \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

# Install dependencies first (cache layer survives source changes).
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-install-project --no-dev

# Now install the project itself.
COPY src ./src
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev

# ── Runtime ─────────────────────────────────────────────────────────────────
FROM python:3.14-slim-bookworm AS runtime

# tini reaps zombies + handles signals correctly under uvicorn.
RUN apt-get update \
 && apt-get install --no-install-recommends -y tini curl \
 && rm -rf /var/lib/apt/lists/*

# Non-root user. Pinned uid/gid so volume mounts behave on hosts that care.
RUN groupadd --system --gid 1001 nagara \
 && useradd  --system --uid 1001 --gid nagara --create-home --shell /sbin/nologin nagara

WORKDIR /app

# Copy the venv and source from the builder.
COPY --from=builder --chown=nagara:nagara /app/.venv /app/.venv
COPY --from=builder --chown=nagara:nagara /app/src   /app/src
COPY --chown=nagara:nagara pyproject.toml /app/pyproject.toml

ENV PATH="/app/.venv/bin:${PATH}" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=8000

USER nagara

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD curl --fail --silent http://127.0.0.1:${PORT}/health/live || exit 1

ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["uvicorn", "nagara.main:app", "--host", "0.0.0.0", "--port", "8000"]
