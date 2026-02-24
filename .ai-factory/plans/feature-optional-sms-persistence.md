# Implementation Plan: Optional SMS Persistence

Branch: feature/optional-sms-persistence (plan in plans/)
Created: 2025-02-24

## Settings
- Testing: yes (unit tests for payload parsing and DB row mapping; optional integration test with testcontainers or skip)
- Logging: verbose (DEBUG for each message received and DB insert; INFO for connect/subscribe/errors)
- Docs: yes — README in persistence folder + optional section in main README

## Scope

Add an **optional** SMS persistence service: MQTT listener that subscribes to `{prefix}/received` and `{prefix}/sent`, parses JSON and writes records to PostgreSQL. Separate directory, separate Docker image, optional service in Docker Compose (can be disabled). Addresses ROADMAP milestone **Optional: SMS persistence**.

## Payload Reference (from sms2mqtt.py)

- **received:** `{"datetime": "<str>", "number": "<str>", "text": "<str>"}` (Gammu DateTime string, Number, Text)
- **sent:** `{"result": "success" | "error : ...", "datetime": "<str>", "number": "<str>", "text": "<str>"}` (optional `"payload"` on decode errors)

Store: direction (received/sent), datetime, number, text, result (for sent), created_at (server time), optional id.

### Column semantics (multi-modem)

- **`remote_number`** — кому/от кого: для received = кто прислал, для sent = кому отправили (в payload это поле `number`).
- **`device_id`** — девайс (модем/мост), на который пришло или с которого ушло: из env `PREFIX` (один мост на инстанс) или парсить префикс из `msg.topic` при подписке на несколько префиксов.

## Approach

- **Location:** New directory `sms2mqtt-persistence/` at repo root (separate from main app).
- **Stack:** Python 3.11, paho-mqtt, psycopg2-binary (or asyncpg if preferred async), certifi for TLS. No Gammu.
- **DB:** Single table `sms` (id, direction, mqtt_datetime, remote_number, text, result, device_id, created_at). `remote_number` = кому/от кого; `device_id` = какой модем. Init via SQL script or one-off migration; no heavy migration framework.
- **Compose:** Optional `docker-compose.persistence.yml` (or profile) with services: postgres, sms2mqtt-persistence; main app can stay in existing/compose elsewhere — persistence only needs MQTT broker and Postgres.

## Tasks

### Phase 1: Layout and schema

- [x] **Task 1:** Create directory and Python project layout  
  - Create `sms2mqtt-persistence/` with `requirements.txt` (paho-mqtt, psycopg2-binary, certifi; versions pinned), `README.md` stub, and main entry script e.g. `listener.py`.  
  - **Logging:** Log startup with LOG_LEVEL; log each config load (MQTT host/prefix, DB host/db name) at DEBUG.  
  - Files: `sms2mqtt-persistence/requirements.txt`, `sms2mqtt-persistence/README.md`, `sms2mqtt-persistence/listener.py` (minimal: parse env, init logging, exit 0).

- [x] **Task 2:** Define DB schema and init script  
  - Add `sms2mqtt-persistence/schema.sql`: table `sms` with columns `id` (bigserial), `direction` (received|sent), `mqtt_datetime` (text or timestamp), `remote_number` (text — кому/от кого), `text` (text), `result` (text, nullable), `device_id` (text, nullable — какой модем), `created_at` (timestamptz default now()). Index on (direction, created_at), optional index on (device_id, created_at).  
  - Document in README that DB must be created and schema applied before first run (e.g. `psql -f schema.sql` or init container).  
  - **Logging:** N/A for schema file; listener will log "Schema applied" or "Table exists" when it checks/creates (if we add auto-init) in a later task.

- [x] **Task 3:** Config and DB connection helper  
  - In `listener.py` (or `config.py` + `db.py`): read env (MQTT: HOST, PORT, PREFIX, USER, PASSWORD, USETLS, CLIENTID; DB: PGHOST, PGPORT, PGDATABASE, PGUSER, PGPASSWORD; LOG_LEVEL). Validate required vars and exit with clear message if missing. Add a function that returns a DB connection (psycopg2).  
  - **Logging:** DEBUG for config values (mask passwords); INFO "Config loaded"; ERROR on connection failure with message.  
  - Files: `sms2mqtt-persistence/listener.py` and/or `sms2mqtt-persistence/config.py`, `sms2mqtt-persistence/db.py`.

### Phase 2: MQTT listener and persistence

- [x] **Task 4:** MQTT client: connect, subscribe, reconnect  
  - In listener: create paho client, set callbacks (on_connect, on_disconnect, on_message). Subscribe to `{PREFIX}/received` and `{PREFIX}/sent`. Implement reconnect with backoff (e.g. 2–30 s) on disconnect, same pattern as sms2mqtt.py. Optional TLS via certifi if USETLS=1.  
  - **Logging:** INFO on connect/disconnect; DEBUG "Subscribed to …"; WARNING on unexpected disconnect; ERROR on connect failure.  
  - Files: `sms2mqtt-persistence/listener.py`.

- [x] **Task 5:** Parse received/sent payloads and insert into PostgreSQL  
  - In `on_message`: decode UTF-8, parse JSON. Detect topic (suffix `received` vs `sent`). Map to row: direction, mqtt_datetime (from payload), remote_number (= payload "number"), text, result (sent only), device_id (from PREFIX or parsed from msg.topic). Insert into `sms`; commit. Handle duplicate/malformed messages: log and skip or store with result="parse_error".  
  - **Logging:** DEBUG "Persisted received/sent …" with number and id; ERROR on insert/parse failure with full context.  
  - Files: `sms2mqtt-persistence/listener.py` and/or `sms2mqtt-persistence/persist.py`.

- [x] **Task 6:** Unit tests for parsing and row mapping  
  - Tests: valid received payload → correct row dict (including remote_number, device_id); valid sent (success and error) → row dict; invalid JSON / missing fields → handled (no crash, optional error row or skip). Use pytest; no real MQTT/DB (mock or in-memory).  
  - **Logging:** Standard test output; no extra logging requirement.  
  - Files: `sms2mqtt-persistence/tests/` (e.g. `test_parse.py`, `test_persist.py`), optional `conftest.py` for fixtures.

### Phase 3: Docker and Compose

- [x] **Task 7:** Dockerfile for persistence service  
  - Add `sms2mqtt-persistence/Dockerfile`: Python 3.11 Alpine (or slim); no Gammu. Install deps from requirements.txt. Copy listener (+ config/db/persist if split). ENTRYPOINT run listener. HEALTHCHECK optional (e.g. check process or TCP to Postgres).  
  - **Logging:** N/A; app logging as above.  
  - File: `sms2mqtt-persistence/Dockerfile`.

- [x] **Task 8:** Docker Compose for optional persistence  
  - Add `docker-compose.persistence.yml` (or `compose-persistence.yml`) in repo root: service `postgres` (image postgres:15-alpine, env POSTGRES_DB/PASSWORD, volume for data), service `sms2mqtt-persistence` (build from sms2mqtt-persistence/, env from MQTT and PGHOST=postgres, PGPORT=5432, etc., depends_on postgres). Document that main sms2mqtt container is not included — user runs it separately or adds to same compose. Optionally use Compose profiles so `docker compose --profile persistence up` starts postgres + persistence.  
  - **Logging:** N/A.  
  - File: `docker-compose.persistence.yml` (or similar).

### Phase 4: Documentation

- [x] **Task 9:** README and main-repo mention  
  - Complete `sms2mqtt-persistence/README.md`: purpose, env vars (MQTT + DB), how to run (local and Docker), schema init, optional Compose. Add short "Optional: SMS persistence" section in main `README.md` with link to `sms2mqtt-persistence/` and one sentence on Compose.  
  - **Logging:** N/A.  
  - Files: `sms2mqtt-persistence/README.md`, `README.md`.

## Commit Plan

- **Commit 1** (after tasks 1–3): `feat(persistence): add project layout, schema, and config`
- **Commit 2** (after tasks 4–6): `feat(persistence): MQTT listener and DB insert with tests`
- **Commit 3** (after tasks 7–8): `feat(persistence): Dockerfile and optional Compose`
- **Commit 4** (after task 9): `docs: persistence README and main README mention`

## Verification

- Run listener locally with test MQTT broker and Postgres: publish sample JSON to `prefix/received` and `prefix/sent`, check rows in `sms`.
- `docker build -t sms2mqtt-persistence ./sms2mqtt-persistence` and run with env; then `docker compose -f docker-compose.persistence.yml up` (or with profile) and verify persistence service starts and writes to Postgres.
