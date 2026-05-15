# Cloud Run Job（RSS 収集）。ビルド: docker build -f services/collector/Dockerfile .
# リポジトリルートをコンテキストにし、uv workspace で collector のみ同期する。
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/workspace/.venv/bin:$PATH" \
    PYTHONPATH=/workspace/services/collector:/workspace/services/shared

WORKDIR /workspace

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

COPY pyproject.toml uv.lock ./
COPY services ./services/
RUN uv sync --frozen --no-dev --package rss-aggregator-collector --extra cloud --no-install-project

COPY feeds.json ./feeds.json

CMD ["python", "services/collector/run.py"]
