# Implementation Plan: FCM Push Notifications (sms2mqtt-persistence)

Branch: none (fast mode)
Created: 2025-03-10

## Settings
- Testing: include tests (unit for db/push logic where practical)
- Logging: verbose (DEBUG for push flow, INFO for send counts, WARN/ERROR for failures)
- Docs: update docs/persistence.md with push config and API endpoints

## Overview
Implement FCM push notifications per `docs/push-design.md`: notify users when new SMS is received (and optionally sent). Uses existing Firebase Admin SDK; new table `fcm_tokens`, API for token registration, and `push.py` called from listener after `insert_sms()`.

## Commit Plan
- **Commit 1** (after tasks 1–2): `feat(persistence): add fcm_tokens schema and db helpers`
- **Commit 2** (after tasks 3–4): `feat(persistence): add push module and wire into listener`
- **Commit 3** (after tasks 5–6): `feat(persistence): add FCM token API and config`

---

## Tasks

### Phase 1: Schema and DB

- [x] **Task 1: Add `fcm_tokens` table to schema**
  - **File:** `sms2mqtt-persistence/schema.sql`
  - Add table `fcm_tokens` (id BIGSERIAL, user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE, token TEXT NOT NULL UNIQUE, platform TEXT, created_at TIMESTAMPTZ DEFAULT now(), updated_at TIMESTAMPTZ DEFAULT now()).
  - Add index `idx_fcm_tokens_user_id` on `fcm_tokens(user_id)`.
  - Add brief COMMENT on table/columns if needed.
  - **Logging:** N/A (schema only).

- [x] **Task 2: DB helpers for FCM and device→users**
  - **Files:** `sms2mqtt-persistence/db.py`
  - Implement:
    - `get_user_ids_for_device(conn, device_id: str) -> list[int]`: select `user_id` from `devices` where `device_id = %s`. If any row has `user_id IS NOT NULL`, return list of those (distinct) user ids. If only `user_id IS NULL` or no rows, return all user ids from `users` (single-tenant: shared device).
    - `get_fcm_tokens_for_user(conn, user_id: int) -> list[str]`: select `token` from `fcm_tokens` where `user_id = %s`; return list of token strings.
    - `upsert_fcm_token(conn, user_id: int, token: str, platform: str | None = None) -> None`: INSERT (user_id, token, platform) ON CONFLICT (token) DO UPDATE SET user_id = EXCLUDED.user_id, platform = EXCLUDED.platform, updated_at = now(). Caller commits.
    - `delete_fcm_token(conn, user_id: int, token: str) -> int`: DELETE FROM fcm_tokens WHERE user_id = %s AND token = %s; return rowcount. Caller commits.
    - `delete_fcm_token_by_token(conn, token: str) -> int`: DELETE FROM fcm_tokens WHERE token = %s; return rowcount. Used by push module when FCM reports invalid/unregistered token (no user_id in response). Caller commits.
  - **Logging:** DEBUG on entry/exit for get_* (e.g. device_id/user_id, count of ids/tokens); DEBUG for upsert/delete with user_id and token prefix (first 8 chars) for privacy.

### Phase 2: Push module and listener integration

- [x] **Task 3: Implement `push.py`**
  - **File:** `sms2mqtt-persistence/push.py` (new)
  - Dependencies: reuse Firebase app from `auth_firebase` (same default app); use `firebase_admin.messaging` for `Message`, `MulticastMessage`, `send_each_for_multicast`.
  - Implement:
    - `send_sms_push(conn, config, row: dict, row_id: int) -> None`. row has direction, device_id, remote_number, text, etc. If `config.get("push_enabled")` is false or no `config.get("firebase_credentials")`, return immediately. If direction is `sent` and not `config.get("push_on_sent")`, return. Get user_ids via `get_user_ids_for_device(conn, row["device_id"])`; for each user get tokens via `get_fcm_tokens_for_user`; collect unique tokens (set). If no tokens, return. Build notification title/body from design (e.g. "SMS" / "От +7900…: превью"); data payload: type (sms_received|sms_sent), sms_id (str), device_id, remote_number, direction, optional text_preview (first 50 chars). FCM data values must be strings. Send in batches of 500 via `send_each_for_multicast`. On response: for each BatchResponse.success_count log INFO; for failures with code in (invalid_argument, unregistered, registration-token-not-registered), call `delete_fcm_token_by_token(conn, token)` and log WARNING.
  - **Logging:** DEBUG: entry (row_id, direction, device_id); DEBUG: user_ids and token count; INFO: "Push sent to N tokens" or "Push batch k: success M, failures F"; WARN: invalid token removed (token prefix); ERROR: exception during send with traceback.

- [x] **Task 4: Wire push into listener and config**
  - **Files:** `sms2mqtt-persistence/listener.py`, `sms2mqtt-persistence/config.py`
  - **config.py:** Add `push_enabled` (default True: `get_env("PUSH_ENABLED", "true").lower() in ("true", "1", "yes")`), `push_on_sent` (default False: same pattern for `PUSH_ON_SENT`). Include in returned config dict.
  - **listener.py:** After successful `insert_sms(conn, row)` when `row_id is not None`, if `config.get("api_port")` and `config.get("firebase_credentials")` and `config.get("push_enabled", True)`, call `send_sms_push(conn, config, row, row_id)` (same conn still open). Catch exceptions from `send_sms_push` and log ERROR without failing the message processing (push is best-effort).
  - **Logging:** DEBUG in listener when push is skipped (no api/firebase/push_enabled) or when calling push; ERROR with message when push raises.

### Phase 3: API and docs

- [x] **Task 5: FCM token API**
  - **File:** `sms2mqtt-persistence/api.py`
  - Add `POST /fcm-token`: body `{"token": "<string>", "platform": "android"|"ios"|"web"}` (platform optional). Auth: `Depends(get_current_user)`. Validate token non-empty string; 400 if invalid. Get DB connection from config, `upsert_fcm_token(conn, user["id"], token, body.get("platform"))`, commit, return `{"registered": true}`.
  - Add `DELETE /fcm-token`: accept body `{"token": "<string>"}` or query `token=...`. Auth: `Depends(get_current_user)`. Resolve token from body or query; 400 if missing. `delete_fcm_token(conn, user["id"], token)`, commit, return 204 or 200 with `{"deleted": true}`.
  - **Logging:** INFO on successful register/delete (user_id, token prefix); DEBUG request body/query; WARN on 400 (missing/invalid token).

- [x] **Task 6: Document push in persistence.md**
  - **File:** `docs/persistence.md`
  - Add section on Push (FCM): env vars `PUSH_ENABLED`, `PUSH_ON_SENT`; when push runs (after insert, only if API + Firebase enabled); API endpoints `POST /fcm-token`, `DELETE /fcm-token` and request/response; note that FCM uses existing Firebase project/credentials.

---

## Dependencies and order
- Task 2 depends on Task 1 (table must exist).
- Task 3 depends on Task 2 (db helpers).
- Task 4 depends on Task 3 (push module) and config from Task 4 (config.py can be done in same task as listener).
- Task 5 depends on Task 2 (upsert/delete token).
- Task 6 can be done after 5 (documents full feature).

## Edge cases (from design)
- Single-tenant: `devices.user_id IS NULL` for device → notify all users (get_user_ids_for_device returns all user ids when device has no owner).
- Batch FCM: up to 500 tokens per `send_each_for_multicast`; chunk token list if longer.
- Invalid/unregistered tokens: remove from `fcm_tokens` so we do not retry.
- Push is best-effort: do not block or fail DB insert; log and continue on push errors.

## Out of scope (design)
- Throttling (N pushes per user per minute) — later iteration.
- Async/thread/queue for push — first version synchronous after insert.
