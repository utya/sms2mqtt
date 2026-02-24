"""
Logic layer: validation, number normalization, no I/O.
Pure functions for unit testing; no MQTT or Gammu dependencies.
"""
import json
import logging
from typing import Optional, Tuple


def normalize_number(raw: str) -> str:
    """
    Normalize phone number to E.164-like form: optional leading +, then digits only.
    Strips spaces; multiple leading + collapsed to one.
    """
    if not raw:
        return ""
    s = raw.strip()
    if not s:
        return ""
    normalized = []
    if s.startswith("+"):
        normalized.append("+")
        s = s[1:].lstrip()
    normalized.append("".join(c for c in s if c.isdigit()))
    return "".join(normalized)


def validate_send_payload(
    payload_bytes: bytes,
    max_text_length: Optional[int] = None,
) -> Tuple[Optional[str], Optional[str], Optional[dict]]:
    """
    Parse and validate send payload. No I/O or globals — for unit testing.
    Returns (number, text, None) on success or (None, None, error_feedback) on error.
    error_feedback has keys "result" and "payload" (safe string for client).
    number is normalized (digits + optional leading +). If max_text_length is set,
    text longer than that returns an error.
    """
    try:
        payload_str = payload_bytes.decode("utf-8")
    except Exception as e:
        try:
            safe = payload_bytes.decode("utf-8", errors="replace")
        except Exception:
            safe = repr(payload_bytes)
        return (None, None, {"result": f"error : failed to decode JSON ({e})", "payload": safe})
    try:
        data = json.loads(payload_str, strict=False)
    except Exception as e:
        return (None, None, {"result": f"error : failed to decode JSON ({e})", "payload": payload_str})
    number = None
    text = None
    for key, value in data.items():
        if key.lower() == "number":
            number = value
        if key.lower() == "text":
            text = value
    if number is None or not isinstance(number, str) or not number.strip():
        return (None, None, {"result": "error : no number to send to", "payload": payload_str})
    if text is None or not isinstance(text, str):
        return (None, None, {"result": "error : no text body to send", "payload": payload_str})
    if max_text_length is not None and len(text) > max_text_length:
        return (
            None,
            None,
            {
                "result": f"error : text exceeds max length ({len(text)} > {max_text_length})",
                "payload": payload_str,
            },
        )
    parts = [p.strip() for p in number.split(";") if p.strip()]
    normalized_parts = [normalize_number(p) for p in parts]
    if any(not p for p in normalized_parts):
        return (None, None, {"result": "error : no number to send to", "payload": payload_str})
    number = ";".join(normalized_parts)
    return (number, text, None)


def parse_log_level(value) -> int:
    """Map LOG_LEVEL env string to logging constant; invalid values fall back to INFO."""
    if not value:
        return logging.INFO
    v = str(value).strip().upper()
    return {
        "DEBUG": logging.DEBUG,
        "INFO": logging.INFO,
        "WARNING": logging.WARNING,
        "WARN": logging.WARNING,
        "ERROR": logging.ERROR,
    }.get(v, logging.INFO)
