FROM python:3.11-alpine

RUN apk add --no-cache gammu-dev

RUN apk add --no-cache --virtual .build-deps gcc musl-dev \
     && pip install --no-cache-dir -r requirements.txt \
     && apk del .build-deps gcc musl-dev

WORKDIR /app

COPY requirements.txt .
COPY sms2mqtt.py .

ENTRYPOINT ["python", "/app/sms2mqtt.py"]

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 CMD kill -0 1 || exit 1
