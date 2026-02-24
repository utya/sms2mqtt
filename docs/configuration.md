[← Getting Started](getting-started.md) · [Back to README](../README.md) · [MQTT Topics →](mqtt-topics.md)

# Configuration

## Device

The GSM modem device must be available inside the container. Default path inside the container is `/dev/mobile`.

- **Docker run:** map the host device, e.g. `--device=/dev/ttyUSB0:/dev/mobile`, and add the host's `dialout` group so the process can open it: `--group-add $(getent group dialout | cut -d: -f3)`.
- **Docker Compose:** in `compose.yml`, set `devices` (e.g. `"/dev/ttyUSB0:/dev/mobile"`) and `group_add` with your host's dialout GID (e.g. `getent group dialout | cut -d: -f3`). Without `group_add`, you may get "you don't have the required permission" (ERR_DEVICENOPERMISSION).

**Tip:** `/dev/ttyUSBx` can change after reboot. Prefer a stable path such as `/dev/serial/by-id/usb-HUAWEI_HUAWEI_Mobile-if00-port0` and map it to `/dev/mobile`.

You can override the in-container path with the `DEVICE` env var (default: `/dev/mobile`).

## Environment variables

| Variable | Required | Description | Default |
|----------|----------|-------------|---------|
| `HOST` | Yes | MQTT broker hostname or IP | — |
| `PORT` | No | MQTT broker port (use 8883 for TLS) | `1883` |
| `USER` | No | MQTT username | — |
| `PASSWORD` | No | MQTT password | — |
| `USETLS` | No | Enable TLS: `true`, `1`, or `yes` | off |
| `PREFIX` | No | Topic prefix for subscribe/publish | `sms2mqtt` |
| `CLIENTID` | No | MQTT client id | `sms2mqtt` |
| `DEVICE` | No | Path to modem inside container | `/dev/mobile` |
| `PIN` | No | SIM PIN | — |
| `GAMMUOPTION` | No | Extra Gammu config line (e.g. `atgen_setcnmi = 1,2,0,0`) | — |
| `MOREINFO` | No | Enable battery and network topics | — |
| `HEARTBEAT` | No | Enable datetime heartbeat topic | — |
| `LOG_LEVEL` | No | `DEBUG`, `INFO`, `WARNING`, `ERROR` | `INFO` |
| `DEVMODE` | No | Set to `1` to wait for Enter before main loop (debugger) | `0` |
| `SMS_MAX_TEXT_LENGTH` | No | Max length for send text; empty = no limit | — |

TLS uses the system CA bundle (certifi). For custom CAs or client certs, code changes would be required.

## See Also

- [Getting Started](getting-started.md) — install and first run
- [MQTT Topics](mqtt-topics.md) — topic list and payloads
- [Security](security.md) — TLS and secrets
