# Cloud Run Job（採点）。ビルド: docker build -f services/classifier/Dockerfile .
# リポジトリルートをコンテキストにし、uv workspace で classifier のみ同期する。
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/workspace/.venv/bin:$PATH" \
    PYTHONPATH=/workspace/services/classifier:/workspace/services/shared

WORKDIR /workspace

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

COPY pyproject.toml uv.lock ./
COPY services ./services/
RUN uv sync --frozen --no-dev --package rss-aggregator-classifier --extra cloud --no-install-project

CMD ["python", "services/classifier/run.py"]
