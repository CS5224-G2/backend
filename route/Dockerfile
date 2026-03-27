# ── Stage 1: Build ──────────────────────────────────────────────────
FROM python:3.13-slim AS builder

# Install uv for fast, deterministic dependency resolution
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

# Copy dependency manifests first for layer caching
COPY pyproject.toml uv.lock ./
COPY route/bike_route ./route/bike_route

# Install dependencies into a virtual-env inside the image
RUN uv sync --frozen --no-dev

# ── Stage 2: Runtime ────────────────────────────────────────────────
FROM python:3.13-slim AS runtime

WORKDIR /app

# Copy the pre-built virtual-env and source code
COPY --from=builder /app/.venv /app/.venv
COPY framework ./framework
COPY route ./route

# Put the venv on PATH so `uvicorn` is found directly
ENV PATH="/app/.venv/bin:$PATH"

EXPOSE 8000

# Health-check (ECS / ALB will also probe the target group)
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/docs')" || exit 1

CMD ["uvicorn", "route.server:app", "--host", "0.0.0.0", "--port", "8000"]
