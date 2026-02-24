# SMS2MQTT Persistence — MQTT listener to PostgreSQL (no Gammu)
FROM python:3.11-alpine

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY config.py db.py persist.py listener.py schema.sql ./

ENTRYPOINT ["python3", "listener.py"]

# Optional: check process is alive (PID 1)
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD kill -0 1 || exit 1
