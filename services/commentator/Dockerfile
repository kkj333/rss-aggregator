# Cloud Run Job（コメント生成）。ビルド: docker build -f services/commentator/Dockerfile .
# リポジトリルートをコンテキストにし、uv workspace で commentator のみ同期する。
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/workspace/.venv/bin:$PATH" \
    PYTHONPATH=/workspace/services/commentator:/workspace/services/shared

WORKDIR /workspace

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

COPY pyproject.toml uv.lock ./
COPY services ./services/
RUN uv sync --frozen --no-dev --package rss-aggregator-commentator --extra cloud --no-install-project

CMD ["python", "services/commentator/run.py"]
