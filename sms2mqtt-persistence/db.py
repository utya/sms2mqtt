"""
PostgreSQL connection helper for persistence.
"""

import logging
import os
from typing import Any

import psycopg2
from psycopg2 import extensions

logger = logging.getLogger(__name__)

_SCHEMA_PATH = os.path.join(os.path.dirname(__file__), "schema.sql")


def ensure_schema(db_config: dict[str, Any]) -> None:
    """
    Create tables and indexes if they do not exist (idempotent).
    Run on startup so DB is ready whether or not Postgres init script ran.
    """
    if not os.path.isfile(_SCHEMA_PATH):
        logger.warning("Schema file not found at %s, skipping ensure_schema", _SCHEMA_PATH)
        return
    try:
        with open(_SCHEMA_PATH, encoding="utf-8") as f:
            sql = f.read()
    except OSError as e:
        logger.error("Cannot read schema file: %s", e)
        return
    # Split into statements; drop comment-only lines from each, then skip empty
    statements = []
    for s in sql.split(";"):
        lines = [line for line in s.splitlines() if line.strip() and not line.strip().startswith("--")]
        stmt = " ".join(l for l in lines).strip()
        if stmt:
            statements.append(stmt)
    if not statements:
        return
    try:
        conn = psycopg2.connect(
            host=db_config["host"],
            port=db_config["port"],
            dbname=db_config["database"],
            user=db_config["user"],
            password=db_config["password"],
        )
        conn.autocommit = True
        try:
            with conn.cursor() as cur:
                for stmt in statements:
                    cur.execute(stmt)
            logger.info("Schema ensured (tables/indexes created if missing)")
        finally:
            conn.close()
    except Exception as e:
        logger.error("Schema ensure failed: %s", e)
        raise


def get_connection(db_config: dict[str, Any]) -> extensions.connection:
    """
    Return a new DB connection. Caller must close it.
    Logs ERROR on failure with message.
    """
    try:
        conn = psycopg2.connect(
            host=db_config["host"],
            port=db_config["port"],
            dbname=db_config["database"],
            user=db_config["user"],
            password=db_config["password"],
        )
        conn.autocommit = False
        logger.debug(
            "DB connection opened to %s@%s:%s/%s",
            db_config["user"],
            db_config["host"],
            db_config["port"],
            db_config["database"],
        )
        return conn
    except Exception as e:
        logger.error("DB connection failed: %s", e)
        raise


def get_or_create_user(
    conn: extensions.connection, external_id: str, email: str | None = None
) -> int:
    """
    Get user id by external_id, or insert and return. Caller must commit/rollback.
    """
    with conn.cursor() as cur:
        cur.execute("SELECT id FROM users WHERE external_id = %s", (external_id,))
        row = cur.fetchone()
        if row:
            return row[0]
        cur.execute(
            "INSERT INTO users (external_id, email) VALUES (%s, %s) RETURNING id",
            (external_id, email),
        )
        return cur.fetchone()[0]


def get_device_ids_for_user(conn: extensions.connection, user_id: int) -> list[str] | None:
    """
    Return list of device_id that this user may access (user_id = user or user_id IS NULL).
    If there are no device rows at all, return None meaning "all devices" (single-tenant).
    """
    with conn.cursor() as cur:
        cur.execute(
            "SELECT device_id FROM devices WHERE user_id = %s OR user_id IS NULL",
            (user_id,),
        )
        rows = cur.fetchall()
    if not rows:
        return None  # no devices table rows yet -> allow all
    return [r[0] for r in rows]


def get_user_ids_for_device(conn: extensions.connection, device_id: str) -> list[int]:
    """
    Return user ids to notify for this device. If device has user_id set, return those (distinct).
    If only user_id IS NULL or no rows for device_id, return all user ids (single-tenant shared device).
    """
    logger.debug("get_user_ids_for_device: device_id=%s", device_id)
    with conn.cursor() as cur:
        cur.execute(
            "SELECT DISTINCT user_id FROM devices WHERE device_id = %s",
            (device_id,),
        )
        rows = cur.fetchall()
    user_ids = [r[0] for r in rows if r[0] is not None]
    if user_ids:
        logger.debug("get_user_ids_for_device: found %d user_id(s)", len(user_ids))
        return user_ids
    # Single-tenant: device has no owner or device unknown -> notify all users
    with conn.cursor() as cur:
        cur.execute("SELECT id FROM users")
        rows = cur.fetchall()
    result = [r[0] for r in rows]
    logger.debug("get_user_ids_for_device: single-tenant, %d user(s)", len(result))
    return result


def get_fcm_tokens_for_user(conn: extensions.connection, user_id: int) -> list[str]:
    """Return list of FCM token strings for this user."""
    logger.debug("get_fcm_tokens_for_user: user_id=%s", user_id)
    with conn.cursor() as cur:
        cur.execute("SELECT token FROM fcm_tokens WHERE user_id = %s", (user_id,))
        rows = cur.fetchall()
    tokens = [r[0] for r in rows]
    logger.debug("get_fcm_tokens_for_user: user_id=%s count=%d", user_id, len(tokens))
    return tokens


def upsert_fcm_token(
    conn: extensions.connection,
    user_id: int,
    token: str,
    platform: str | None = None,
) -> None:
    """Insert or update FCM token for user. Caller must commit."""
    prefix = token[:8] + "..." if len(token) > 8 else token
    logger.debug("upsert_fcm_token: user_id=%s token_prefix=%s platform=%s", user_id, prefix, platform)
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO fcm_tokens (user_id, token, platform)
            VALUES (%s, %s, %s)
            ON CONFLICT (token) DO UPDATE SET
                user_id = EXCLUDED.user_id,
                platform = EXCLUDED.platform,
                updated_at = now()
            """,
            (user_id, token, platform),
        )
    logger.debug("upsert_fcm_token: done user_id=%s token_prefix=%s", user_id, prefix)


def delete_fcm_token(
    conn: extensions.connection, user_id: int, token: str
) -> int:
    """Delete FCM token for user. Caller must commit. Returns rowcount."""
    prefix = token[:8] + "..." if len(token) > 8 else token
    logger.debug("delete_fcm_token: user_id=%s token_prefix=%s", user_id, prefix)
    with conn.cursor() as cur:
        cur.execute(
            "DELETE FROM fcm_tokens WHERE user_id = %s AND token = %s",
            (user_id, token),
        )
        n = cur.rowcount
    logger.debug("delete_fcm_token: deleted %d row(s) user_id=%s token_prefix=%s", n, user_id, prefix)
    return n


def delete_fcm_token_by_token(conn: extensions.connection, token: str) -> int:
    """Delete FCM token by value (e.g. when FCM reports invalid/unregistered). Caller must commit. Returns rowcount."""
    prefix = token[:8] + "..." if len(token) > 8 else token
    logger.debug("delete_fcm_token_by_token: token_prefix=%s", prefix)
    with conn.cursor() as cur:
        cur.execute("DELETE FROM fcm_tokens WHERE token = %s", (token,))
        n = cur.rowcount
    if n:
        logger.warning("Removed invalid FCM token from DB: token_prefix=%s", prefix)
    return n


def list_sms(
    conn: extensions.connection,
    device_ids: list[str] | None,
    limit: int = 50,
    offset: int = 0,
    direction: str | None = None,
) -> tuple[list[dict[str, Any]], int]:
    """
    Return (items, total). items are dicts with id, direction, mqtt_datetime, remote_number, text, result, device_id, created_at.
    If device_ids is not None, filter by device_id IN (...). direction: 'received' | 'sent' | None for both.
    """
    conditions = []
    args: list[Any] = []
    if device_ids is not None:
        conditions.append("device_id = ANY(%s)")
        args.append(device_ids)
    if direction:
        conditions.append("direction = %s")
        args.append(direction)
    where_sql = (" WHERE " + " AND ".join(conditions)) if conditions else ""

    with conn.cursor() as cur:
        cur.execute(f"SELECT COUNT(*) FROM sms{where_sql}", args)
        total = cur.fetchone()[0]

        select_args = args + [limit, offset]
        cur.execute(
            f"""
            SELECT id, direction, mqtt_datetime, remote_number, text, result, device_id, created_at
            FROM sms
            {where_sql}
            ORDER BY created_at DESC
            LIMIT %s OFFSET %s
            """,
            select_args,
        )
        rows = cur.fetchall()

    keys = ("id", "direction", "mqtt_datetime", "remote_number", "text", "result", "device_id", "created_at")
    items = []
    for row in rows:
        d = dict(zip(keys, row))
        if d.get("created_at"):
            d["created_at"] = d["created_at"].isoformat()
        items.append(d)
    return items, total
