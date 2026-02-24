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

## Schema

Create the database and apply the schema before first run:

```bash
createdb sms2mqtt
psql -d sms2mqtt -f schema.sql
```

With Docker Compose (see below), connect to the postgres container once and run `schema.sql`, or use an init script.

## Run locally

```bash
pip install -r requirements.txt
export HOST=localhost PREFIX=sms2mqtt
export PGHOST=localhost PGDATABASE=sms2mqtt PGUSER=u PGPASSWORD=p
python3 listener.py
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
docker compose -f docker-compose.persistence.yml --profile persistence up -d
```

Set `MQTT_HOST`, `MQTT_PREFIX`, etc. (or use defaults). The main sms2mqtt bridge is not included in that compose — run it separately. Apply `schema.sql` to the postgres service before the listener will succeed (e.g. `docker compose -f docker-compose.persistence.yml exec postgres psql -U sms2mqtt -d sms2mqtt -f - < sms2mqtt-persistence/schema.sql` or run once from host).

## Tests

```bash
pip install -r requirements.txt
python3 -m pytest tests/ -v
```

---

See main repo [README](../README.md).
