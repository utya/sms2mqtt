# sms2mqtt

> SMS-to-MQTT bridge: connect a GSM modem (Gammu) to an MQTT broker. Send and receive SMS over MQTT topics.

A single service that links your GSM dongle to MQTT: publish to a topic to send SMS, subscribe to topics for incoming SMS and status. Supports long/unicode messages, multipart SMS, optional battery/network/heartbeat, and TLS.

## Quick start

```bash
# With Docker Compose (recommended): copy .env.example to .env, set HOST/PORT/USER/PASSWORD,
# uncomment and set devices in compose.yml, then:
docker compose up -d

# Or with plain Docker:
docker run -d --name sms2mqtt --restart=unless-stopped \
  --device=/dev/ttyUSB0:/dev/mobile \
  -e HOST=your-broker -e PORT=1883 -e PREFIX=sms2mqtt \
  domochip/sms2mqtt
```

Use real credentials via `.env` or env vars; do not commit secrets.

## Key features

- **Send SMS** — Publish JSON to `{prefix}/send`; confirmations on `{prefix}/sent`
- **Receive SMS** — Incoming SMS published to `{prefix}/received`
- **Status** — `{prefix}/connected`, `{prefix}/signal`; optional battery/network/datetime
- **Control** — `{prefix}/control` (e.g. `delete_stuck_sms`)
- **Config** — Device, PIN, MQTT host/port/prefix/client id/user/password, TLS via env

## Example

Publish to `sms2mqtt/send`:

```json
{"number": "+33612345678", "text": "Hello from MQTT 👌"}
```

A confirmation is published to `sms2mqtt/sent`. Incoming SMS appear on `sms2mqtt/received`.

![Diagram](https://raw.githubusercontent.com/Domochip/sms2mqtt/master/diagram.svg)

---

## Documentation

| Guide | Description |
|-------|-------------|
| [Getting Started](docs/getting-started.md) | Prerequisites, install (Docker / Compose), verify |
| [Configuration](docs/configuration.md) | Device mapping and environment variables |
| [MQTT Topics](docs/mqtt-topics.md) | Send, receive, status, and control topics |
| [Security](docs/security.md) | TLS, secrets, and MQTT ACL |
| [Persistence](docs/persistence.md) | Optional PostgreSQL storage for SMS |
| [Development](docs/development.md) | uv, tests, lint |
| [Troubleshooting](docs/troubleshooting.md) | Logs and updating |

## Ref / Thanks

Inspired by:

- [sms-gammu-gateway](https://github.com/pajikos/sms-gammu-gateway)
- [mqtt2sms](https://github.com/pkropf/mqtt2sms)

---

Documentation in Russian: [README.ru.md](README.ru.md).
