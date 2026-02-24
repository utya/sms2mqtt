[Back to README](../README.md) · [Configuration →](configuration.md)

# Getting Started

## Prerequisites

- A GSM modem/dongle compatible with [Gammu](https://wammu.eu/phones/). Many unlisted dongles work as well.
- An MQTT broker (Mosquitto, EMQX, etc.) reachable from the host running the bridge.
- Docker (and optionally Docker Compose).

## How it works

The bridge connects your GSM modem to an MQTT broker: it subscribes to topics to **send** SMS and publishes **received** SMS and status to MQTT. If the broker connection is lost, the service reconnects with exponential backoff instead of exiting.

![Architecture diagram](https://raw.githubusercontent.com/Domochip/sms2mqtt/master/diagram.svg)

## Install

**Security:** Examples use placeholders (`1234`, `pass`). Do not use real SIM PINs or MQTT passwords in committed files. Use `.env` (gitignored) or Docker secrets in production.

### Option 1: Docker Run

```bash
docker run -d --name sms2mqtt --restart=unless-stopped \
  --device=/dev/ttyUSB0:/dev/mobile \
  -e PIN=1234 \
  -e HOST=192.168.1.x \
  -e PORT=8883 \
  -e PREFIX=sms2mqtt \
  -e USER=usr \
  -e PASSWORD=pass \
  -e USETLS=true \
  domochip/sms2mqtt
```

Replace `/dev/ttyUSB0` with your modem device (e.g. `/dev/serial/by-id/usb-...` for a stable path across reboots).

### Option 2: Docker Compose

1. Copy `.env.example` to `.env` and set `HOST`, `PORT`, `USER`, `PASSWORD`, etc.
2. In `compose.yml`, uncomment and set the `devices` mapping for your modem.
3. Start:

```bash
docker compose up -d
```

The image includes a HEALTHCHECK so orchestrators can detect an unhealthy container.

## Verify

- Check logs: `docker logs sms2mqtt` (or `docker compose logs -f sms2mqtt`).
- Publish a test SMS via MQTT to `{prefix}/send` (see [MQTT topics](mqtt-topics.md)).
- Confirm a reply on `{prefix}/sent`.

## Next steps

- [Configuration](configuration.md) — device path and all environment variables
- [MQTT topics](mqtt-topics.md) — send, receive, and status topics

## See Also

- [Configuration](configuration.md) — env vars and device mapping
- [Security](security.md) — TLS, secrets, ACL
