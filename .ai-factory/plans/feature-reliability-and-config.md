# Implementation Plan: Reliability and config

Branch: feature/reliability-and-config  
Created: 2025-02-23

## Settings

- **Testing:** yes
- **Logging:** via env variable `LOG_LEVEL`, default INFO
- **Docs:** yes (README)

## Overview

Implement ROADMAP milestone "Reliability and config": (1) MQTT reconnection with backoff instead of `exit()` on disconnect; (2) configurable log level via `LOG_LEVEL` env (default INFO). Follow paho-mqtt best practice: connection flag, reconnect from main thread with exponential backoff.

## Tasks

### Phase 1: Configurable logging

- [x] **Task 1: Add LOG_LEVEL from environment**  
  Read `LOG_LEVEL` at startup (default `INFO`). Map to `logging.DEBUG`/`INFO`/`WARNING`/`ERROR`; invalid values fallback to INFO. Set level via `logging.basicConfig(..., level=...)` before any other log calls. Log at INFO the effective level at startup (e.g. "Log level: INFO").  
  **Files:** `sms2mqtt.py`  
  **Logging:** INFO at startup with chosen level; no new log points inside existing code for this task.

### Phase 2: MQTT reconnection

- [x] **Task 2: Replace exit() with reconnection and backoff**  
  - In `on_mqtt_disconnect`: remove `exit()`; set a global (or shared) flag `mqtt_connected = False`. Optionally log disconnect reason if `rc != 0`.  
  - In `on_mqtt_connect`: set `mqtt_connected = True` on successful connect.  
  - In main loop: if not `mqtt_connected`, call `client.reconnect()` after a delay; use exponential backoff (e.g. start 2 s, max 60 s); on success reset backoff; on connection error log (WARN/ERROR) and sleep before next attempt. Only attempt reconnect when delay elapsed (track last attempt time).  
  **Files:** `sms2mqtt.py`  
  **Logging:** DEBUG for each reconnect attempt (e.g. "Reconnecting to MQTT (attempt N)"); INFO when reconnected; WARN/ERROR on reconnect failure with reason. Keep existing disconnect/connect logs.

### Phase 3: Tests

- [x] **Task 3: Unit tests for LOG_LEVEL and disconnect behaviour**  
  - Add a small test module (e.g. `tests/test_config_and_mqtt.py` or `test_sms2mqtt_config.py` at repo root).  
  - Test LOG_LEVEL: set `os.environ["LOG_LEVEL"]` to DEBUG/INFO/WARNING/ERROR and (via import-time or a tested helper) assert the resolved level is correct; test invalid value falls back to INFO.  
  - Test disconnect callback: ensure `on_mqtt_disconnect` does not call `exit` (e.g. mock `exit` and call `on_mqtt_disconnect`, assert exit was not called).  
  Use standard library `unittest`; no paho/gammu in tests.  
  **Files:** new test file(s), optionally minimal helper in `sms2mqtt.py` for level parsing if needed for testability.  
  **Logging:** no specific logging inside tests.

### Phase 4: Documentation

- [x] **Task 4: Update README (LOG_LEVEL and reconnection)**  
  - In "Environment variables" add `LOG_LEVEL`: optional, values DEBUG/INFO/WARNING/ERROR, default INFO.  
  - Add a short note (e.g. under "How does it work" or "Configure") that on MQTT disconnect the service automatically reconnects with backoff instead of exiting.  
  **Files:** `README.md`

## Commit Plan

- **Commit 1** (after tasks 1–2): `feat: add LOG_LEVEL env and MQTT reconnect with backoff`
- **Commit 2** (after tasks 3–4): `test: add config and disconnect tests; docs: README LOG_LEVEL and reconnection`

## Notes

- Reconnection runs in the same thread as `client.loop()` (main loop); no thread-safety changes.
- Optional: use `client.reconnect_delay_set(min_delay, max_delay)` if paho-mqtt version supports it; otherwise implement backoff in main loop.
- ROADMAP: after this, mark "Reliability and config" as completed.
