# Cloud Run（Web）／Compose の既定イメージ。ビルドはリポジトリルートをコンテキストにする:
#   docker build -f services/web/Dockerfile .
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:$PATH" \
    PYTHONPATH=/app/services/web:/app/services/shared

WORKDIR /app

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

COPY pyproject.toml uv.lock ./
COPY services ./services/
RUN uv sync --frozen --no-dev --no-install-project --extra cloud --package rss-aggregator-web

COPY feeds.json ./

EXPOSE 8080

CMD ["uvicorn", "web.main:app", "--host", "0.0.0.0", "--port", "8080"]
