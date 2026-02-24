"""
Parse MQTT payloads (received/sent) and insert SMS rows into PostgreSQL.
"""

import json
import logging
from typing import Any

logger = logging.getLogger(__name__)


def parse_received(payload: dict) -> dict[str, Any] | None:
    """Build row dict for received topic. Returns None if payload invalid."""
    try:
        dt = payload.get("datetime")
        number = payload.get("number")
        text = payload.get("text")
        if number is None or not isinstance(number, str):
            return None
        return {
            "direction": "received",
            "mqtt_datetime": str(dt) if dt is not None else None,
            "remote_number": number.strip(),
            "text": str(text) if text is not None else "",
            "result": None,
        }
    except Exception:
        return None


def parse_sent(payload: dict) -> dict[str, Any] | None:
    """Build row dict for sent topic. Returns None if payload invalid."""
    try:
        result = payload.get("result")
        dt = payload.get("datetime")
        number = payload.get("number")
        text = payload.get("text")
        if number is None or not isinstance(number, str):
            return None
        return {
            "direction": "sent",
            "mqtt_datetime": str(dt) if dt is not None else None,
            "remote_number": number.strip(),
            "text": str(text) if text is not None else "",
            "result": str(result) if result is not None else None,
        }
    except Exception:
        return None


def payload_to_row(
    topic: str, payload_bytes: bytes, device_id: str | None
) -> dict[str, Any] | None:
    """
    Decode UTF-8, parse JSON, detect direction from topic suffix, return row dict or None.
    On parse error returns None (caller may log and optionally insert with result='parse_error').
    """
    try:
        raw = payload_bytes.decode("utf-8")
    except Exception as e:
        logger.debug("Payload decode failed: %s", e)
        return None
    try:
        data = json.loads(raw, strict=False)
    except Exception as e:
        logger.debug("Payload JSON parse failed: %s", e)
        return None

    if topic.endswith("/received"):
        row = parse_received(data)
    elif topic.endswith("/sent"):
        row = parse_sent(data)
    else:
        return None

    if row is None:
        return None
    row["device_id"] = device_id
    return row


def insert_sms(conn: Any, row: dict[str, Any]) -> int | None:
    """Insert one SMS row; commit. Returns inserted id or None on error."""
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO sms (direction, mqtt_datetime, remote_number, text, result, device_id)
                VALUES (%s, %s, %s, %s, %s, %s)
                RETURNING id
                """,
                (
                    row["direction"],
                    row.get("mqtt_datetime"),
                    row["remote_number"],
                    row.get("text", ""),
                    row.get("result"),
                    row.get("device_id"),
                ),
            )
            row_id = cur.fetchone()[0]
        conn.commit()
        return row_id
    except Exception as e:
        logger.error("Insert failed: %s", e)
        conn.rollback()
        return None
