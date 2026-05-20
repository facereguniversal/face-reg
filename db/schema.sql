-- ==========================================================================
-- Face Recognition Service – PostgreSQL Schema
-- ==========================================================================
-- Run: psql -U faceuser -d facedb -f schema.sql
-- ==========================================================================

-- Enable UUID generation
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- (Optional) Enable pgvector for native vector similarity search
-- CREATE EXTENSION IF NOT EXISTS vector;

-- --------------------------------------------------------------------------
-- Users
-- --------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS users (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name        VARCHAR(255)    NOT NULL,
    email       VARCHAR(255)    NOT NULL UNIQUE,
    hashed_password VARCHAR(255),
    role        VARCHAR(50)     NOT NULL DEFAULT 'user',
    is_active   BOOLEAN         NOT NULL DEFAULT TRUE,
    extra_metadata JSONB,
    created_at  TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_users_email ON users (email);

-- --------------------------------------------------------------------------
-- Images
-- --------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS images (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id         UUID            NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    filepath        TEXT            NOT NULL,
    capture_time    TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    resolution      BIGINT,
    quality_score   FLOAT
);

CREATE INDEX idx_images_user ON images (user_id);

-- --------------------------------------------------------------------------
-- Face Templates (embeddings)
-- --------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS face_templates (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id         UUID            NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    embedding       JSONB,
    -- If using pgvector: embedding VECTOR(512),
    model           VARCHAR(100)    NOT NULL DEFAULT 'arcface_r100',
    quality_score   FLOAT,
    source_image_id UUID            REFERENCES images(id),
    created_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_face_templates_user ON face_templates (user_id);
-- If using pgvector:
-- CREATE INDEX idx_face_templates_embedding ON face_templates USING ivfflat (embedding vector_cosine_ops);

-- --------------------------------------------------------------------------
-- Check-ins
-- --------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS checkins (
    id                    UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id               UUID            REFERENCES users(id) ON DELETE SET NULL,
    checkin_time          TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    status                VARCHAR(50)     NOT NULL,
    device_or_location_id VARCHAR(255)    NOT NULL,
    confidence_score      FLOAT
);

CREATE INDEX idx_checkins_time   ON checkins (checkin_time DESC);
CREATE INDEX idx_checkins_user_time ON checkins (user_id, checkin_time DESC);
CREATE INDEX idx_checkins_status_time ON checkins (status, checkin_time DESC);
CREATE INDEX idx_checkins_device_time ON checkins (device_or_location_id, checkin_time DESC);

-- --------------------------------------------------------------------------
-- Audit Logs (append-only)
-- --------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS audit_logs (
    id          BIGSERIAL PRIMARY KEY,
    user_id     UUID            REFERENCES users(id),
    action      VARCHAR(100)    NOT NULL,
    details     JSONB,
    timestamp   TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    source_ip   VARCHAR(50)
);

CREATE INDEX idx_audit_logs_user   ON audit_logs (user_id);
CREATE INDEX idx_audit_logs_action ON audit_logs (action);
CREATE INDEX idx_audit_logs_ts     ON audit_logs (timestamp);

-- --------------------------------------------------------------------------
-- API Tokens (refresh / long-lived)
-- --------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS api_tokens (
    token       VARCHAR(512) PRIMARY KEY,
    user_id     UUID            NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    expires_at  TIMESTAMPTZ     NOT NULL,
    scopes      JSONB,
    revoked     BOOLEAN         NOT NULL DEFAULT FALSE
);
