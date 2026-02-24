-- SMS persistence table: one row per received or sent message.
-- Run once to create DB and table, e.g.: psql -f schema.sql (or init container).

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
COMMENT ON COLUMN sms.device_id IS 'Modem/bridge identifier (e.g. MQTT prefix).';
