# AGENTS.md

> Project map for AI agents. Keep this file up-to-date as the project evolves.

## Project Overview

SMS-to-MQTT bridge: GSM modem (Gammu) ↔ MQTT broker for sending and receiving SMS via MQTT topics.

## Tech Stack

- **Language:** Python 3
- **Key libs:** paho-mqtt, python-gammu, certifi
- **Runtime:** Single script, no framework
- **Deploy:** Docker (Alpine), GitHub Actions

## Project Structure

```
sms2mqtt/
├── sms2mqtt.py               # Main application (MQTT + Gammu loop)
├── Dockerfile                # Main image: Python 3.11 Alpine + gammu, pip deps
├── README.md                 # Usage, env vars, topics, troubleshooting
├── diagram.svg               # Architecture diagram
├── sms2mqtt.drawio           # Diagram source
├── docker-compose.persistence.yml  # Optional: postgres + sms2mqtt-persistence (profile)
├── sms2mqtt-persistence/     # Optional MQTT→PostgreSQL persistence service
│   ├── listener.py          # Entry point (MQTT subscribe + DB insert)
│   ├── config.py, db.py, persist.py
│   ├── schema.sql            # Table sms (direction, remote_number, device_id, …)
│   ├── Dockerfile            # Separate image (no Gammu)
│   ├── requirements.txt
│   └── tests/                # Unit tests (parse, row mapping)
├── .github/
│   ├── workflows/            # CI: docker-publish-release.yml
│   └── dependabot.yml
├── .ai-factory/
│   ├── DESCRIPTION.md        # Project spec and tech stack
│   └── ARCHITECTURE.md       # Architecture guidelines
└── .cursor/skills/           # AI Factory skills (aif-*)
```

## Key Entry Points

| File | Purpose |
|------|---------|
| sms2mqtt.py | Main entry; MQTT client, Gammu init, receive/send/status loop |
| Dockerfile | Main image; gammu, python-gammu, paho-mqtt, certifi |
| sms2mqtt-persistence/listener.py | Optional persistence entry; MQTT→PostgreSQL |
| docker-compose.persistence.yml | Optional Compose: postgres + sms2mqtt-persistence (profile) |
| .github/workflows/docker-publish-release.yml | Build and push main image on release (multi-arch) |

## Documentation

| Document | Path | Description |
|----------|------|-------------|
| README | README.md | Install (Docker/Compose), env vars, topics, troubleshoot, update |

## AI Context Files

| File | Purpose |
|------|---------|
| AGENTS.md | This file — project structure map |
| .ai-factory/DESCRIPTION.md | Project specification and tech stack |
| .ai-factory/ARCHITECTURE.md | Architecture decisions and guidelines (layered, single-script) |
| .ai-factory/ROADMAP.md | Strategic roadmap and milestones (from RECOMMENDATIONS-PLAN) |
| .ai-factory/RECOMMENDATIONS-PLAN.md | Detailed improvement recommendations and priorities |
