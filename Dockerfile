# syntax=docker/dockerfile:1
# Main image: SMS-to-MQTT bridge. Uses uv for dependencies (no pip/requirements.txt).
# Multi-stage: deps + production. Non-root user in final stage.

# --- Dependencies (prod only) ---
FROM python:3.11-alpine AS deps
WORKDIR /app
RUN apk add --no-cache gammu-dev
COPY --from=ghcr.io/astral-sh/uv:0.10 /uv /uvx /bin/
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    apk add --no-cache --virtual .build-deps gcc musl-dev \
    && uv sync --frozen --no-dev --extra run \
    && apk del .build-deps gcc musl-dev

# --- Production ---
FROM python:3.11-alpine AS production
RUN apk add --no-cache gammu-dev
WORKDIR /app
RUN addgroup -g 1001 -S appuser && adduser -S -u 1001 -G appuser appuser
COPY --from=deps /app/.venv /app/.venv
COPY --from=deps /app/pyproject.toml /app/uv.lock /app/
COPY --chown=appuser:appuser logic.py mqtt_layer.py gammu_layer.py sms2mqtt.py ./
ENV PATH="/app/.venv/bin:$PATH"
USER appuser
ENTRYPOINT ["python", "/app/sms2mqtt.py"]
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 CMD kill -0 1 || exit 1
