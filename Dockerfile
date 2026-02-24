# Main image: SMS-to-MQTT bridge. Uses uv for dependencies (no pip/requirements.txt).
FROM python:3.11-alpine

RUN apk add --no-cache gammu-dev

# Install uv (binary from official image)
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN apk add --no-cache --virtual .build-deps gcc musl-dev \
     && uv sync --frozen --no-dev --extra run \
     && apk del .build-deps gcc musl-dev

COPY logic.py mqtt_layer.py gammu_layer.py sms2mqtt.py ./

ENTRYPOINT ["python", "/app/sms2mqtt.py"]

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 CMD kill -0 1 || exit 1
