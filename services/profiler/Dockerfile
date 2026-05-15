# Cloud Run Job（ブログプロファイル生成）。ビルド: docker build -f services/profiler/Dockerfile .
# リポジトリルートをコンテキストにし、uv workspace で profiler のみ同期する。
FROM ghcr.io/astral-sh/uv:python3.12-trixie-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PATH="/workspace/.venv/bin:$PATH" \
    PYTHONPATH=/workspace/services/profiler:/workspace/services/shared

WORKDIR /workspace

COPY pyproject.toml uv.lock ./
COPY services ./services/
RUN uv sync --frozen --no-dev --package rss-aggregator-profiler --extra cloud --no-install-project

COPY feeds.json ./feeds.json

CMD ["python", "services/profiler/run.py"]
