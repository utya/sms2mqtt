[← MQTT Topics](mqtt-topics.md) · [Back to README](../README.md) · [Persistence →](persistence.md)

# Security

## TLS

For production, use MQTT over TLS:

- Set `USETLS=true` (or `1` / `yes`) and `PORT=8883`.
- The app uses the system CA bundle (certifi) to verify the broker.
- Custom CAs or client certificates would require code changes.

## Secrets

Do not put real SIM PIN codes or MQTT passwords in examples or in files committed to the repo.

- Use environment variables, Docker secrets, or a `.env` file that is **not** in version control.
- See the note in [Getting Started](getting-started.md#install).

## ACL (access control)

There is no application-level auth. Who can send SMS or run control actions is determined **only** by the MQTT broker’s ACL:

- Restrict **publish** access to `{prefix}/send` and `{prefix}/control` to trusted clients.
- Restrict who can subscribe to `{prefix}/received` and `{prefix}/sent` if the payloads are sensitive.

## See Also

- [Configuration](configuration.md) — USETLS and env vars
- [Getting Started](getting-started.md) — safe install examples
- [Persistence](persistence.md) — DB credentials for optional storage
