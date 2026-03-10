# sms2mqtt-persistence

Optional MQTT listener: subscribes to `{prefix}/received` and `{prefix}/sent`, persists SMS records to PostgreSQL. Useful for logging, search, or multi-modem setups (each row has `device_id` = MQTT prefix).

## Environment variables

**MQTT** (same broker as sms2mqtt bridge):

| Variable   | Required | Description                    |
|-----------|----------|--------------------------------|
| `HOST`    | yes      | MQTT broker host               |
| `PREFIX`  | yes      | Topic prefix (e.g. `sms2mqtt`) |
| `PORT`    | no       | MQTT port (default 1883)       |
| `USER`    | no       | MQTT username                  |
| `PASSWORD`| no       | MQTT password                  |
| `USETLS`  | no       | `true` / `1` for TLS           |
| `CLIENTID`| no       | Client ID (default sms2mqtt-persistence) |

**Database:**

| Variable    | Required | Description        |
|-------------|----------|--------------------|
| `PGHOST`    | yes      | PostgreSQL host    |
| `PGDATABASE`| yes      | Database name      |
| `PGUSER`    | yes      | Database user      |
| `PGPASSWORD`| yes      | Database password  |
| `PGPORT`    | no       | Port (default 5432)|

**Other:** `LOG_LEVEL` — `DEBUG`, `INFO`, `WARNING`, `ERROR` (default `INFO`).

**Optional REST API (Firebase Auth):**

| Variable                 | Required | Description                                      |
|---------------------------|----------|--------------------------------------------------|
| `API_PORT`                | no       | If set, enable HTTP API (e.g. `8080`)            |
| `FIREBASE_CREDENTIALS`    | if API   | Path to Firebase service account JSON file       |
| `GOOGLE_APPLICATION_CREDENTIALS` | no  | Alternative to `FIREBASE_CREDENTIALS`           |

When `API_PORT` is set, the service runs both the MQTT listener (background) and an HTTP server. **GET /sms** returns SMS for the authenticated user (Firebase ID token in `Authorization: Bearer <token>`). Query params: `limit` (default 50), `offset`, `direction` (`received` \| `sent`). Response: `{ "items": [...], "total": N }`.

## Schema

Create the database and apply the schema before first run:

```bash
createdb sms2mqtt
psql -d sms2mqtt -f schema.sql
```

With Docker Compose (see below), connect to the postgres container once and run `schema.sql`, or use an init script.

## Run locally

Uses [uv](https://docs.astral.sh/uv/) for dependencies. From this directory:

```bash
uv sync
export HOST=localhost PREFIX=sms2mqtt
export PGHOST=localhost PGDATABASE=sms2mqtt PGUSER=u PGPASSWORD=p
uv run python3 listener.py
```

## Run with Docker

```bash
docker build -t sms2mqtt-persistence .
docker run -d --name sms2mqtt-persistence \
  -e HOST=your-mqtt-host -e PREFIX=sms2mqtt \
  -e PGHOST=postgres -e PGDATABASE=sms2mqtt -e PGUSER=sms2mqtt -e PGPASSWORD=secret \
  sms2mqtt-persistence
```

## Optional Docker Compose

From the repo root you can start Postgres + this listener with:

```bash
docker compose -f docker-compose.persistence.yml up -d
```

Set `MQTT_HOST`, `MQTT_PREFIX`, etc. (or use defaults). The main sms2mqtt bridge is not included in that compose — run it separately. Schema is applied automatically on first start. To enable the REST API, set `API_PORT=8080` and `FIREBASE_CREDENTIALS=/path/in/container` (mount your Firebase service account JSON into the container).

## Tests

```bash
uv sync --extra dev
uv run pytest tests/ -v
```

---

See main repo [README](../README.md).
