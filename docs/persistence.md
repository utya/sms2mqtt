[← Security](security.md) · [Back to README](../README.md) · [Development →](development.md)

# Optional: SMS persistence

To store received and sent SMS in PostgreSQL, use the optional **sms2mqtt-persistence** service. It subscribes to `{prefix}/received` and `{prefix}/sent` and writes rows to a database.

## Run with Docker Compose

```bash
docker compose -f docker-compose.persistence.yml --profile persistence up -d
```

This starts Postgres and the persistence listener. Configure MQTT and DB via environment variables (see [sms2mqtt-persistence/README.md](../sms2mqtt-persistence/README.md)).

## Details

- The main SMS-to-MQTT bridge is **not** included in that compose file; run it separately (e.g. `docker compose up -d` for the main app).
- Schema and table layout are in `sms2mqtt-persistence/schema.sql`.

## Deployment: image pull timeout

If `docker compose ... up` fails with **connection timed out** while pulling `postgres:17-alpine`, the host cannot reliably reach Docker Hub (slow or restricted network).

**Options:**

1. **Pre-pull with retries** (on the deploy host):
   ```bash
   docker pull postgres:17-alpine
   ```
   If it still times out, try a smaller or older tag, or pull from a machine with better connectivity and transfer the image (e.g. `docker save` / `docker load`).

2. **Use another Postgres image** via env (no code change):
   ```bash
   export POSTGRES_IMAGE=postgres:16-alpine
   docker compose -f docker-compose.persistence.yml --profile persistence up -d
   ```
   Or set `POSTGRES_IMAGE` in your `.env`. Any Postgres 15+ Alpine image is compatible.

3. **Use a registry mirror** if your environment provides one: configure Docker daemon to use the mirror, or set `POSTGRES_IMAGE` to the mirror URL of the same image.

4. **Increase timeouts** (Docker client): e.g. `export DOCKER_CLIENT_TIMEOUT=300` and `export COMPOSE_HTTP_TIMEOUT=300` before running compose (helps only if the connection is slow but not fully blocked).

## See Also

- [Getting Started](getting-started.md) — main bridge install
- [MQTT Topics](mqtt-topics.md) — received/sent payloads
- [sms2mqtt-persistence/README.md](../sms2mqtt-persistence/README.md) — persistence env vars and setup
