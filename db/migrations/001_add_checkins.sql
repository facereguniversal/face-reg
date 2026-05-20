-- Add stateful kiosk check-in tracking.
-- Run against existing PostgreSQL databases that were initialized before
-- checkins existed in db/schema.sql.

CREATE TABLE IF NOT EXISTS checkins (
    id                    UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id               UUID            REFERENCES users(id) ON DELETE SET NULL,
    checkin_time          TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    status                VARCHAR(50)     NOT NULL,
    device_or_location_id VARCHAR(255)    NOT NULL,
    confidence_score      FLOAT
);

CREATE INDEX IF NOT EXISTS idx_checkins_time
    ON checkins (checkin_time DESC);
CREATE INDEX IF NOT EXISTS idx_checkins_user_time
    ON checkins (user_id, checkin_time DESC);
CREATE INDEX IF NOT EXISTS idx_checkins_status_time
    ON checkins (status, checkin_time DESC);
CREATE INDEX IF NOT EXISTS idx_checkins_device_time
    ON checkins (device_or_location_id, checkin_time DESC);
