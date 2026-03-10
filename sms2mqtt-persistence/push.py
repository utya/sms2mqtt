"""
FCM push notifications: send push after SMS insert. Uses Firebase Admin SDK (same app as auth).
"""

import logging
from typing import Any

from db import (
    delete_fcm_token_by_token,
    get_fcm_tokens_for_user,
    get_user_ids_for_device,
)

logger = logging.getLogger(__name__)

# FCM batch size limit
FCM_BATCH_SIZE = 500

# Error reasons that mean token is invalid and should be removed from DB
_INVALID_TOKEN_REASONS = (
    "invalid_argument",
    "invalid-argument",
    "unregistered",
    "registration-token-not-registered",
)


def _should_remove_token(exception: BaseException) -> bool:
    """Return True if this FCM error means the token should be removed from DB."""
    try:
        from firebase_admin import messaging
        if isinstance(exception, messaging.UnregisteredError):
            return True
    except ImportError:
        pass
    msg = (getattr(exception, "message", None) or str(exception)).lower()
    return any(r in msg for r in _INVALID_TOKEN_REASONS)


def send_sms_push(
    conn: Any,
    config: dict[str, Any],
    row: dict[str, Any],
    row_id: int,
) -> None:
    """
    Send FCM push to users associated with the SMS device. Best-effort: logs errors, does not raise.
    Skips if push_enabled is False, no firebase credentials, or direction is 'sent' and push_on_sent is False.
    """
    if not config.get("push_enabled", True):
        logger.debug("send_sms_push: skipped (push_enabled=false)")
        return
    if not config.get("firebase_credentials"):
        logger.debug("send_sms_push: skipped (no firebase_credentials)")
        return
    direction = row.get("direction") or "received"
    if direction == "sent" and not config.get("push_on_sent", False):
        logger.debug("send_sms_push: skipped (direction=sent, push_on_sent=false)")
        return

    device_id = row.get("device_id") or ""
    logger.debug(
        "send_sms_push: row_id=%s direction=%s device_id=%s",
        row_id,
        direction,
        device_id,
    )

    try:
        user_ids = get_user_ids_for_device(conn, device_id)
    except Exception as e:
        logger.error("send_sms_push: get_user_ids_for_device failed: %s", e, exc_info=True)
        return

    tokens_set: set[str] = set()
    for uid in user_ids:
        try:
            tokens_set.update(get_fcm_tokens_for_user(conn, uid))
        except Exception as e:
            logger.error("send_sms_push: get_fcm_tokens_for_user(uid=%s) failed: %s", uid, e, exc_info=True)

    tokens = list(tokens_set)
    logger.debug("send_sms_push: user_ids=%s token_count=%d", user_ids, len(tokens))

    if not tokens:
        logger.debug("send_sms_push: no tokens, skipping")
        return

    # Build notification and data (FCM data values must be strings)
    if direction == "received":
        notif_title = "SMS"
        text_preview = (row.get("text") or "")[:50]
        notif_body = f"From {row.get('remote_number', '')}: {text_preview}"
    else:
        notif_title = "Sent"
        notif_body = f"Sent to {row.get('remote_number', '')}"

    data_payload: dict[str, str] = {
        "type": "sms_received" if direction == "received" else "sms_sent",
        "sms_id": str(row_id),
        "device_id": device_id,
        "remote_number": row.get("remote_number") or "",
        "direction": direction,
    }
    text_preview = (row.get("text") or "")[:50]
    if text_preview:
        data_payload["text_preview"] = text_preview

    try:
        from firebase_admin import messaging

        notification = messaging.Notification(title=notif_title, body=notif_body)
    except ImportError as e:
        logger.error("send_sms_push: firebase_admin.messaging not available: %s", e)
        return

    # Send in batches of 500
    for i in range(0, len(tokens), FCM_BATCH_SIZE):
        batch_tokens = tokens[i : i + FCM_BATCH_SIZE]
        try:
            msg = messaging.MulticastMessage(
                tokens=batch_tokens,
                notification=notification,
                data=data_payload,
            )
            batch_response = messaging.send_each_for_multicast(msg)
        except Exception as e:
            logger.error(
                "send_sms_push: send_each_for_multicast failed (batch %d): %s",
                i // FCM_BATCH_SIZE + 1,
                e,
                exc_info=True,
            )
            continue

        logger.info(
            "send_sms_push: batch %d success=%d failures=%d",
            i // FCM_BATCH_SIZE + 1,
            batch_response.success_count,
            batch_response.failure_count,
        )

        # Remove invalid/unregistered tokens from DB
        for idx, send_resp in enumerate(batch_response.responses):
            if send_resp.success:
                continue
            exc = getattr(send_resp, "exception", None)
            if exc and _should_remove_token(exc):
                if idx < len(batch_tokens):
                    token = batch_tokens[idx]
                    try:
                        n = delete_fcm_token_by_token(conn, token)
                        if n:
                            conn.commit()
                            logger.warning(
                                "send_sms_push: removed invalid FCM token from DB token_prefix=%s",
                                token[:8] + "..." if len(token) > 8 else token,
                            )
                    except Exception as del_e:
                        logger.warning("send_sms_push: failed to delete token: %s", del_e)
                        conn.rollback()
