"""
REST API: GET /sms with Firebase Auth. Requires API_PORT and FIREBASE_CREDENTIALS.
"""

import logging
from typing import Any

from fastapi import Body, Depends, FastAPI, HTTPException, Query, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from pydantic import BaseModel, Field

from auth_firebase import init_firebase, verify_token
from db import (
    delete_fcm_token,
    get_connection,
    get_device_ids_for_user,
    get_or_create_user,
    list_sms,
    upsert_fcm_token,
)

logger = logging.getLogger(__name__)
security = HTTPBearer(auto_error=False)


class FCMTokenRegister(BaseModel):
    """Body for POST /fcm-token. platform is optional (android, ios, web)."""

    token: str = Field(..., min_length=1)
    platform: str | None = None


class FCMTokenDelete(BaseModel):
    """Body for DELETE /fcm-token (optional)."""

    token: str = Field(..., min_length=1)


def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
) -> dict[str, Any]:
    """Verify Firebase ID token and return user dict (id, external_id, email)."""
    if not credentials:
        raise HTTPException(status_code=401, detail="Missing Authorization Bearer token")
    token = credentials.credentials

    config = getattr(request.app.state, "config", None)
    if not config:
        raise HTTPException(status_code=500, detail="Config not available")
    creds_path = config.get("firebase_credentials")
    if not creds_path:
        raise HTTPException(status_code=503, detail="Firebase not configured")

    init_firebase(creds_path)
    try:
        claims = verify_token(token)
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e)) from e

    uid = claims.get("uid") or claims.get("sub")
    if not uid:
        raise HTTPException(status_code=401, detail="Token missing uid")
    email = claims.get("email")

    conn = get_connection(config["db"])
    try:
        user_id = get_or_create_user(conn, uid, email)
        conn.commit()
        return {"id": user_id, "external_id": uid, "email": email}
    finally:
        conn.close()


def create_app(config: dict[str, Any]) -> FastAPI:
    """Build FastAPI app with config in state."""
    app = FastAPI(title="SMS2MQTT Persistence API", version="0.1.0")
    app.state.config = config

    @app.get("/sms")
    def get_sms(
        request: Request,
        limit: int = Query(50, ge=1, le=200),
        offset: int = Query(0, ge=0),
        direction: str | None = Query(None, pattern="^(received|sent)$"),
        user: dict[str, Any] = Depends(get_current_user),
    ) -> dict[str, Any]:
        """List SMS for the authenticated user (filtered by user's devices)."""
        cfg = request.app.state.config
        conn = get_connection(cfg["db"])
        try:
            device_ids = get_device_ids_for_user(conn, user["id"])
            items, total = list_sms(conn, device_ids, limit=limit, offset=offset, direction=direction)
            return {"items": items, "total": total}
        finally:
            conn.close()

    @app.post("/fcm-token")
    def register_fcm_token(
        request: Request,
        body: FCMTokenRegister,
        user: dict[str, Any] = Depends(get_current_user),
    ) -> dict[str, Any]:
        """Register or update FCM token for the current user (upsert)."""
        token = (body.token or "").strip()
        if not token:
            logger.warning("POST /fcm-token: empty token rejected")
            raise HTTPException(status_code=400, detail="token is required and must be non-empty")
        cfg = request.app.state.config
        conn = get_connection(cfg["db"])
        try:
            upsert_fcm_token(conn, user["id"], token, body.platform)
            conn.commit()
            prefix = token[:8] + "..." if len(token) > 8 else token
            logger.info("FCM token registered user_id=%s token_prefix=%s", user["id"], prefix)
            return {"registered": True}
        finally:
            conn.close()

    @app.delete("/fcm-token")
    def delete_fcm_token_endpoint(
        request: Request,
        user: dict[str, Any] = Depends(get_current_user),
        token_query: str | None = Query(None, alias="token"),
        body: FCMTokenDelete | None = Body(None),
    ) -> dict[str, Any]:
        """Remove FCM token for the current user (e.g. on logout). Token from query or body."""
        token = (token_query or (body.token if body else None) or "").strip()
        if not token:
            logger.warning("DELETE /fcm-token: missing token (query or body)")
            raise HTTPException(status_code=400, detail="token is required (query token=... or body)")
        cfg = request.app.state.config
        conn = get_connection(cfg["db"])
        try:
            n = delete_fcm_token(conn, user["id"], token)
            conn.commit()
            prefix = token[:8] + "..." if len(token) > 8 else token
            logger.info("FCM token deleted user_id=%s token_prefix=%s deleted=%d", user["id"], prefix, n)
            return {"deleted": True}
        finally:
            conn.close()

    return app
