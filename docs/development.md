[← Persistence](persistence.md) · [Back to README](../README.md) · [Troubleshooting →](troubleshooting.md)

# Development

The project uses [uv](https://docs.astral.sh/uv/) for dependencies (no pip or requirements.txt). You can run tests and lint locally without a GSM modem or MQTT broker.

## Setup

1. Install [uv](https://docs.astral.sh/uv/) if needed.
2. Sync dependencies:
   ```bash
   uv sync --extra dev
   ```
   For the optional persistence service:
   ```bash
   cd sms2mqtt-persistence && uv sync --extra dev
   ```

## Tests

```bash
uv run pytest tests/ -v
cd sms2mqtt-persistence && uv run pytest tests/ -v
```

## Lint

```bash
uv run ruff check .
uv run ruff format --check .
```

## See Also

- [Getting Started](getting-started.md) — run with Docker
- [Troubleshooting](troubleshooting.md) — logs and updating
