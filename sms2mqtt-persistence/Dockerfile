# SMS2MQTT Persistence — MQTT listener to PostgreSQL (no Gammu). Uses uv (no pip).
FROM python:3.11-alpine

WORKDIR /app

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

COPY config.py db.py persist.py listener.py schema.sql ./

ENTRYPOINT ["python3", "listener.py"]

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD kill -0 1 || exit 1
