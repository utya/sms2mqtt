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

## See Also

- [Getting Started](getting-started.md) — main bridge install
- [MQTT Topics](mqtt-topics.md) — received/sent payloads
- [sms2mqtt-persistence/README.md](../sms2mqtt-persistence/README.md) — persistence env vars and setup
