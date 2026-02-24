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

## See Also

- [Getting Started](getting-started.md) — install and verify
- [Configuration](configuration.md) — env vars and device
