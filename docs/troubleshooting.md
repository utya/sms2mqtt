[← Development](development.md) · [Back to README](../README.md)

# Troubleshooting

## Logs

View container logs:

```bash
docker logs sms2mqtt
```

With Compose:

```bash
docker compose logs -f sms2mqtt
```

## Updating the Docker image

To update to the latest image:

```bash
docker stop sms2mqtt
docker rm sms2mqtt
docker rmi domochip/sms2mqtt
# Run the container again; Docker will pull the latest image.
```

With Compose (using pre-built image):

```bash
docker compose pull
docker compose up -d
```

If you build locally (`docker compose up -d` with `build:`), rebuild and recreate:

```bash
docker compose build --pull
docker compose up -d
```

## Finding the right modem port

If you have several `/dev/ttyUSB*` ports and get **ERR_NOSIM** or **ERR_TIMEOUT**, run on the host (with gammu installed):

```bash
./scripts/check-modem-ports.sh
```

Or with sudo if you see "permission denied":

```bash
sudo ./scripts/check-modem-ports.sh
```

The script tests each port and reports which one sees the modem (and SIM). Use that port in `compose.yml` under `devices`.

For full modem diagnostics (signal, operator, network type, USB power) on the host, use:

```bash
./scripts/modem-stat.sh /dev/ttyUSB0
```

(Replace with the port that worked in `check-modem-ports.sh`.)

## See Also

- [Getting Started](getting-started.md) — install and verify
- [Configuration](configuration.md) — env vars and device
