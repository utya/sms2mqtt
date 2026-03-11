"""
Firebase Auth: initialize from service account path and verify ID tokens.
"""

import logging
import os
from typing import Any

logger = logging.getLogger(__name__)

_firebase_initialized = False


def init_firebase(credentials_path: str | None) -> None:
    """Initialize Firebase Admin SDK with service account file. Idempotent."""
    global _firebase_initialized
    if _firebase_initialized or not credentials_path:
        return
    if not os.path.isfile(credentials_path):
        if os.path.isdir(credentials_path):
            raise FileNotFoundError(
                f"Firebase credentials path is a directory, not a file: {credentials_path}. "
                "On the host, ensure FIREBASE_CREDENTIALS_FILE points to an existing JSON file; "
                "if the file was missing, Docker created a directory at that mount path."
            )
        raise FileNotFoundError(
            f"Firebase credentials file not found: {credentials_path}. "
            "Set FIREBASE_CREDENTIALS_FILE on the host to the path of your Firebase service account JSON."
        )
    try:
        import firebase_admin
        from firebase_admin import credentials

        cred = credentials.Certificate(credentials_path)
        firebase_admin.initialize_app(cred)
        _firebase_initialized = True
        logger.info("Firebase Admin SDK initialized from %s", credentials_path)
    except Exception as e:
        logger.error("Firebase init failed: %s", e)
        raise


def verify_token(id_token: str) -> dict[str, Any]:
    """
    Verify Firebase ID token; return decoded claims (uid, email, ...).
    Raises ValueError on invalid/expired token.
    """
    try:
        from firebase_admin import auth
    except ImportError as e:
        raise RuntimeError("Firebase Admin SDK not available") from e

    try:
        decoded = auth.verify_id_token(id_token)
        return dict(decoded)
    except Exception as e:
        logger.debug("Token verification failed: %s", e)
        raise ValueError("Invalid or expired token") from e
