-- SMS persistence: users (for future multi-tenant), devices (modem per user), sms (messages).
-- Run once to create DB and tables, e.g.: psql -f schema.sql (or init container).

-- Users: for access control. Single-user mode = one row or none (then "any authenticated" sees all).
CREATE TABLE IF NOT EXISTS users (
    id          BIGSERIAL PRIMARY KEY,
    external_id TEXT NOT NULL UNIQUE,
    email       TEXT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

COMMENT ON COLUMN users.external_id IS 'External auth id (e.g. Google sub).';
COMMENT ON COLUMN users.email IS 'Display/contact email from provider.';

-- Devices: modem/bridge identifier, optionally bound to a user. For single-user, user_id can be NULL (all devices visible to the one authenticated user).
CREATE TABLE IF NOT EXISTS devices (
    id          BIGSERIAL PRIMARY KEY,
    device_id   TEXT NOT NULL UNIQUE,
    user_id     BIGINT REFERENCES users(id) ON DELETE SET NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_devices_user_id ON devices(user_id);

COMMENT ON COLUMN devices.device_id IS 'Modem/bridge identifier (e.g. MQTT prefix).';
COMMENT ON COLUMN devices.user_id IS 'Owner. NULL = single-tenant mode (any authenticated user can see).';

-- SMS: one row per received or sent message. device_id links to devices.device_id.
CREATE TABLE IF NOT EXISTS sms (
    id             BIGSERIAL PRIMARY KEY,
    direction      TEXT NOT NULL CHECK (direction IN ('received', 'sent')),
    mqtt_datetime  TEXT,
    remote_number  TEXT NOT NULL,
    text           TEXT NOT NULL DEFAULT '',
    result         TEXT,
    device_id      TEXT,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_sms_direction_created_at ON sms (direction, created_at);
CREATE INDEX IF NOT EXISTS idx_sms_device_id_created_at ON sms (device_id, created_at);

COMMENT ON COLUMN sms.remote_number IS 'For received: sender number. For sent: recipient number.';
COMMENT ON COLUMN sms.device_id IS 'Modem/bridge identifier (e.g. MQTT prefix). Links to devices.device_id for per-user filtering.';

-- Single-user: leave devices.user_id NULL (or create one user and assign devices to them). List SMS: all for authenticated user.
-- Multi-user: set devices.user_id for each modem. List SMS: only where device_id IN (SELECT device_id FROM devices WHERE user_id = current_user_id).
-- When a new device appears (first SMS from unknown device_id), insert INTO devices(device_id, user_id) VALUES (..., NULL) or assign to a user; ensure_schema does not create device rows, app or migration can.

-- FCM tokens: one row per device token per user. Used to send push notifications on new SMS.
CREATE TABLE IF NOT EXISTS fcm_tokens (
    id         BIGSERIAL PRIMARY KEY,
    user_id    BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token      TEXT NOT NULL UNIQUE,
    platform   TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_fcm_tokens_user_id ON fcm_tokens(user_id);

COMMENT ON TABLE fcm_tokens IS 'FCM device tokens for push notifications (one token per device per user).';
COMMENT ON COLUMN fcm_tokens.platform IS 'Optional: android, ios, web.';
COMMENT ON COLUMN fcm_tokens.updated_at IS 'Updated on re-registration (upsert) of the same token.';
