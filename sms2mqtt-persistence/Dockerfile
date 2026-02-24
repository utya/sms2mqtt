# SMS2MQTT Persistence — MQTT listener to PostgreSQL (no Gammu). Uses uv (no pip).
# syntax=docker/dockerfile:1
FROM python:3.11-alpine

WORKDIR /app
RUN addgroup -g 1001 -S appuser && adduser -S -u 1001 -G appuser appuser

COPY --from=ghcr.io/astral-sh/uv:0.10 /uv /uvx /bin/
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev && chown -R appuser:appuser /app
COPY --chown=appuser:appuser config.py db.py persist.py listener.py schema.sql ./
ENV PATH="/app/.venv/bin:$PATH"
USER appuser

ENTRYPOINT ["python3", "listener.py"]
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD kill -0 1 || exit 1
