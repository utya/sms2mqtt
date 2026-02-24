# Project: sms2mqtt

## Overview

SMS-to-MQTT bridge: connects a GSM modem (via Gammu) to an MQTT broker. Sends and receives SMS over MQTT topics, supports long/unicode messages, multipart SMS, optional battery/network/heartbeat topics, and TLS.

## Core Features

- **Send SMS**: Publish JSON to `{prefix}/send`; confirmations to `{prefix}/sent`
- **Receive SMS**: Incoming SMS published to `{prefix}/received`
- **Control**: `{prefix}/control` for actions (e.g. `delete_stuck_sms`)
- **Status**: `{prefix}/connected`, `{prefix}/signal`; optional `{prefix}/battery`, `{prefix}/network`, `{prefix}/datetime`
- **Config**: Device, PIN, MQTT host/port/prefix/client id/user/password, TLS, Gammu options via env

## Tech Stack

- **Language:** Python 3 (3.11 in Dockerfile; `requirements.txt` for pinned deps)
- **Runtime:** Layered modules: `sms2mqtt.py` (entry), `logic.py`, `mqtt_layer.py`, `gammu_layer.py`
- **Key libs:** paho-mqtt, python-gammu, certifi
- **System:** Gammu (Alpine in Docker)
- **Deploy:** Docker, Docker Compose; GitHub Actions for multi-arch build/publish on release

## Architecture Notes

- Single-process: MQTT client callbacks + polling loop for Gammu (GetNextSMS, signal/battery/network/datetime).
- Config via env; Gammu config written at startup to `/app/gammurc`.
- No database in main app; state is modem + MQTT broker. Optional **sms2mqtt-persistence** (separate dir/image) subscribes to received/sent and writes to PostgreSQL.

## Architecture

See `.ai-factory/ARCHITECTURE.md` for detailed architecture guidelines.
Pattern: Layered (split modules). See `.ai-factory/ARCHITECTURE.md`.

## Non-Functional Requirements

- **Logging:** Python logging, configurable level (e.g. LOG_LEVEL if added).
- **Error handling:** Publish errors to `{prefix}/sent` or `{prefix}/control_response`; log and continue where appropriate.
- **Security:** PIN for SIM; MQTT auth; optional TLS (certifi). No secrets in repo.
