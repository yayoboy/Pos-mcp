# syntax=docker/dockerfile:1.7

FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    POS_MCP_HEADLESS=1 \
    POS_MCP_PREVIEW_HOST=0.0.0.0 \
    POS_MCP_LOG_LEVEL=INFO

RUN apt-get update && apt-get install --no-install-recommends -y \
        graphviz \
        fontconfig \
        fonts-dejavu \
        fonts-noto-core \
        fonts-noto-mono \
        fonts-noto-cjk \
        fonts-noto-color-emoji \
        fonts-noto-extra \
        curl \
    && fc-cache -f \
    && rm -rf /var/lib/apt/lists/*

FROM base AS build

WORKDIR /build
COPY pyproject.toml ./
COPY src ./src
RUN pip install --upgrade pip build && python -m build --wheel --outdir /wheels

FROM base AS runtime

WORKDIR /app
COPY --from=build /wheels /wheels
RUN pip install /wheels/*.whl && rm -rf /wheels

COPY pos-mcp.json /app/pos-mcp.json

ENV POS_MCP_CONFIG=/app/pos-mcp.json

EXPOSE 7878
EXPOSE 3333

HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
    CMD curl -fsS "http://127.0.0.1:${POS_MCP_PREVIEW_PORT:-7878}/healthz" || exit 1

ENTRYPOINT ["python", "-m", "pos_mcp.server"]
