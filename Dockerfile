# PrintFlow Dashboard — production Docker image
# Multi-stage: install deps with uv, run with slim Python

FROM python:3.12-slim AS builder

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

# Copy workspace files
COPY pyproject.toml uv.lock ./
COPY packages/common/pyproject.toml packages/common/pyproject.toml
COPY packages/dashboard/pyproject.toml packages/dashboard/pyproject.toml
COPY packages/agent/pyproject.toml packages/agent/pyproject.toml

# Create package source dirs so uv can resolve workspace
COPY packages/common/src packages/common/src
COPY packages/dashboard/src packages/dashboard/src
COPY packages/agent/src packages/agent/src

# Install production deps only (no dev group)
RUN uv sync --frozen --no-dev

# --- Runtime stage ---
FROM python:3.12-slim

WORKDIR /app

# Copy venv and source from builder
COPY --from=builder /app/.venv /app/.venv
COPY --from=builder /app/packages /app/packages

# Put venv on PATH
ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONUNBUFFERED=1

# Dashboard defaults
ENV DASHBOARD_HOST=0.0.0.0
ENV DASHBOARD_PORT=8000

EXPOSE 8000

HEALTHCHECK --interval=15s --timeout=5s --retries=3 --start-period=10s \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health')" || exit 1

CMD ["python", "-m", "dashboard", "--host", "0.0.0.0", "--port", "8000"]
