"""
Configuration from environment. Required: MQTT (HOST, PREFIX) and DB (PGHOST, PGDATABASE, PGUSER, PGPASSWORD).
"""
import os
from typing import Any


def get_env(key: str, default: str = "") -> str:
    return os.getenv(key, default).strip()


def load_config() -> dict[str, Any]:
    """Load and validate config from env. Exits with clear message if required vars missing."""
    mqtt_host = get_env("HOST", "localhost")
    mqtt_port = int(get_env("PORT", "1883") or "1883")
    mqtt_prefix = get_env("PREFIX", "sms2mqtt")
    mqtt_user = get_env("USER")
    mqtt_password = get_env("PASSWORD")
    mqtt_use_tls = get_env("USETLS", "").lower() in ("true", "1", "yes")
    mqtt_client_id = get_env("CLIENTID", "sms2mqtt-persistence")

    pg_host = get_env("PGHOST")
    pg_port = int(get_env("PGPORT", "5432") or "5432")
    pg_database = get_env("PGDATABASE")
    pg_user = get_env("PGUSER")
    pg_password = get_env("PGPASSWORD")

    missing = []
    if not mqtt_host:
        missing.append("HOST")
    if not mqtt_prefix:
        missing.append("PREFIX")
    if not pg_host:
        missing.append("PGHOST")
    if not pg_database:
        missing.append("PGDATABASE")
    if not pg_user:
        missing.append("PGUSER")
    if not pg_password:
        missing.append("PGPASSWORD")

    if missing:
        raise SystemExit(
            f"Missing required env: {', '.join(missing)}. "
            "Set MQTT (HOST, PREFIX) and DB (PGHOST, PGDATABASE, PGUSER, PGPASSWORD)."
        )

    return {
        "mqtt": {
            "host": mqtt_host,
            "port": mqtt_port,
            "prefix": mqtt_prefix,
            "user": mqtt_user or None,
            "password": mqtt_password or None,
            "use_tls": mqtt_use_tls,
            "client_id": mqtt_client_id,
        },
        "db": {
            "host": pg_host,
            "port": pg_port,
            "database": pg_database,
            "user": pg_user,
            "password": pg_password,
        },
        "log_level": get_env("LOG_LEVEL", "INFO"),
    }


def mask_password(s: str | None) -> str:
    if not s:
        return ""
    if len(s) <= 2:
        return "**"
    return s[:1] + "*" * (len(s) - 2) + s[-1:]
