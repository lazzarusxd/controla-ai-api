FROM python:3.14-slim-bookworm AS builder

COPY --from=ghcr.io/astral-sh/uv:0.9.7 /uv /uvx /bin/

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    UV_PROJECT_ENVIRONMENT=/opt/venv

WORKDIR /build

RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-install-project --no-dev

FROM python:3.14-slim-bookworm AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH" \
    TZ=America/Sao_Paulo \
    APP_PORT=8000 \
    GUNICORN_WORKERS=4

RUN apt-get update && apt-get install -y --no-install-recommends \
        tesseract-ocr \
        tesseract-ocr-por \
        poppler-utils \
        libgl1 \
        libglib2.0-0 \
        curl \
    && rm -rf /var/lib/apt/lists/*

ARG APP_UID=1000
ARG APP_GID=1000

RUN groupadd --gid ${APP_GID} appuser \
    && useradd --uid ${APP_UID} --gid ${APP_GID} --create-home appuser

COPY --from=builder /opt/venv /opt/venv

WORKDIR /app
COPY --chown=${APP_UID}:${APP_GID} . .

RUN mkdir -p /var/lib/controlaai/receipts /var/lib/controlaai/exports \
    && chown -R ${APP_UID}:${APP_GID} /var/lib/controlaai

USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD curl -fsS http://localhost:8000/health/liveness \
        && curl -fsS http://localhost:8000/health/readiness || exit 1

CMD ["sh", "-c", "exec gunicorn main:app \
     --worker-class uvicorn_worker.UvicornWorker \
     --workers ${GUNICORN_WORKERS} \
     --bind 0.0.0.0:${APP_PORT:-8000} \
     --timeout 60 \
     --graceful-timeout 30 \
     --keep-alive 5 \
     --max-requests 1000 \
     --max-requests-jitter 100 \
     --access-logfile - \
     --error-logfile -"]
