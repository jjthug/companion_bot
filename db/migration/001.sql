-- ============================================================
-- Migration: 001_initial_schema
-- Description: Initial schema for voice chatbot application
-- Created: 2026-06-06
-- ============================================================

BEGIN;

-- ============================================================
-- EXTENSIONS
-- ============================================================

CREATE EXTENSION IF NOT EXISTS "pgcrypto";   -- gen_random_uuid()
CREATE EXTENSION IF NOT EXISTS "vector";     -- pgvector: embeddings & similarity search


-- ============================================================
-- PLANS
-- (no FK deps, must come first)
-- ============================================================

CREATE TYPE plan_slug AS ENUM ('free', 'starter', 'standard', 'heavy');

CREATE TABLE plans (
    id               UUID          PRIMARY KEY DEFAULT gen_random_uuid(),
    slug             plan_slug     NOT NULL UNIQUE,
    tier             SMALLINT      NOT NULL CHECK (tier > 0),
    daily_cost_limit NUMERIC(10,6) NOT NULL CHECK (daily_cost_limit >= 0),
    monthly_cost     NUMERIC(10,2) NOT NULL CHECK (monthly_cost >= 0),
    created_at       TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
    updated_at       TIMESTAMPTZ   NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE  plans                  IS 'Subscription plans available to users.';
COMMENT ON COLUMN plans.tier             IS 'Numeric rank: higher = more capable plan.';
COMMENT ON COLUMN plans.daily_cost_limit IS 'Maximum LLM/TTS spend (USD) allowed per day for this plan.';
COMMENT ON COLUMN plans.monthly_cost     IS 'Billing price (USD) charged to users per month.';


-- ============================================================
-- USERS
-- ============================================================

CREATE TABLE users (
    id               UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    full_name        TEXT        NOT NULL,
    email            TEXT        NOT NULL UNIQUE,
    password_hash    TEXT,                        -- NULL for pure-OAuth accounts
    oauth_provider   TEXT,
    oauth_id         TEXT,
    profile          JSONB       NOT NULL DEFAULT '{}',
    plan_id          UUID        NOT NULL REFERENCES plans (id) ON UPDATE CASCADE,
    plan_cycle_day   SMALLINT    NOT NULL DEFAULT 1
                                 CHECK (plan_cycle_day BETWEEN 1 AND 28),
    created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Either a password OR an OAuth identity must be present
    CONSTRAINT users_auth_method_check
        CHECK (
            password_hash IS NOT NULL
            OR (oauth_provider IS NOT NULL AND oauth_id IS NOT NULL)
        ),

    -- One OAuth identity per provider
    CONSTRAINT users_oauth_unique
        UNIQUE (oauth_provider, oauth_id)
);

CREATE INDEX idx_users_plan_id      ON users (plan_id);
CREATE INDEX idx_users_email        ON users (email);
CREATE INDEX idx_users_oauth        ON users (oauth_provider, oauth_id)
    WHERE oauth_provider IS NOT NULL;
CREATE INDEX idx_users_profile_gin  ON users USING GIN (profile);

COMMENT ON TABLE  users                  IS 'Registered users of the voice chatbot.';
COMMENT ON COLUMN users.password_hash    IS 'Bcrypt / argon2 hash. NULL for OAuth-only accounts.';
COMMENT ON COLUMN users.profile          IS 'Arbitrary user preferences / metadata stored as JSONB.';
COMMENT ON COLUMN users.plan_cycle_day   IS 'Day-of-month the billing cycle resets (1–28).';


-- ============================================================
-- SESSIONS
-- ============================================================

CREATE TABLE sessions (
    id                 UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id            UUID        NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    context            TEXT,
    summarized_context TEXT,
    start_datetime     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    end_datetime       TIMESTAMPTZ,
    is_active          BOOLEAN     NOT NULL DEFAULT TRUE,
    created_at         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at         TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT sessions_datetime_order
        CHECK (end_datetime IS NULL OR end_datetime >= start_datetime)
);

CREATE INDEX idx_sessions_user_id   ON sessions (user_id);
CREATE INDEX idx_sessions_active    ON sessions (user_id, is_active)
    WHERE is_active = TRUE;
CREATE INDEX idx_sessions_start     ON sessions (start_datetime DESC);

COMMENT ON TABLE  sessions                   IS 'Individual voice chat sessions.';
COMMENT ON COLUMN sessions.context           IS 'Full running context / transcript for the session.';
COMMENT ON COLUMN sessions.summarized_context IS 'Compressed summary used to trim the context window.';
COMMENT ON COLUMN sessions.is_active         IS 'TRUE while the session is ongoing.';


-- ============================================================
-- SUMMARIES
-- ============================================================

CREATE TYPE summary_period_type AS ENUM ('daily', 'weekly', 'monthly');

CREATE TABLE summaries (
    id          UUID               PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     UUID               NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    summary     TEXT               NOT NULL,
    start_date  DATE               NOT NULL,
    end_date    DATE               NOT NULL,
    period_type summary_period_type NOT NULL,
    -- 1536 = text-embedding-3-small/large; adjust to match your model's output dim
    embedding   VECTOR(1536),
    created_at  TIMESTAMPTZ        NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ        NOT NULL DEFAULT NOW(),

    CONSTRAINT summaries_date_order
        CHECK (end_date >= start_date),

    -- Prevent duplicate summaries for the same user/period/range
    CONSTRAINT summaries_unique_period
        UNIQUE (user_id, period_type, start_date)
);

CREATE INDEX idx_summaries_user_id    ON summaries (user_id);
CREATE INDEX idx_summaries_period     ON summaries (user_id, period_type, start_date DESC);

-- HNSW index for fast approximate nearest-neighbour search (cosine distance).
-- Switch to vector_l2_ops if your embeddings are L2-normalised instead.
-- m=16, ef_construction=64 are safe defaults; tune up for recall, down for build speed.
CREATE INDEX idx_summaries_embedding_hnsw ON summaries
    USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);

-- Partial index that skips un-embedded rows so the ANN index stays tight.
CREATE INDEX idx_summaries_embedding_ivfflat ON summaries
    USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 100)
    WHERE embedding IS NOT NULL;

COMMENT ON TABLE  summaries             IS 'Periodic conversation summaries per user.';
COMMENT ON COLUMN summaries.period_type IS 'Granularity of the summary window.';
COMMENT ON COLUMN summaries.embedding   IS 'Vector embedding of summary text for semantic similarity search. Dimension must match your embedding model.';


-- ============================================================
-- USAGE
-- ============================================================

CREATE TYPE usage_period_type AS ENUM ('daily', 'monthly');

CREATE TABLE usage (
    id             UUID              PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id        UUID              NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    start_date     DATE              NOT NULL,
    end_date       DATE              NOT NULL,
    cost           NUMERIC(10,6)     NOT NULL DEFAULT 0 CHECK (cost >= 0),
    period         usage_period_type NOT NULL,
    quota_exceeded BOOLEAN           NOT NULL DEFAULT FALSE,
    created_at     TIMESTAMPTZ       NOT NULL DEFAULT NOW(),
    updated_at     TIMESTAMPTZ       NOT NULL DEFAULT NOW(),

    CONSTRAINT usage_date_order
        CHECK (end_date >= start_date),

    -- Unique usage record per user × period × start_date (as specified)
    CONSTRAINT usage_unique_period
        UNIQUE (user_id, period, start_date)
);

CREATE INDEX idx_usage_user_period  ON usage (user_id, period, start_date DESC);
CREATE INDEX idx_usage_quota        ON usage (user_id, period, quota_exceeded)
    WHERE quota_exceeded = TRUE;

COMMENT ON TABLE  usage                IS 'Tracks LLM/TTS cost consumption per user per period.';
COMMENT ON COLUMN usage.cost           IS 'Accumulated spend in USD for this window.';
COMMENT ON COLUMN usage.quota_exceeded IS 'Set TRUE when the user has exceeded their plan limit.';


-- ============================================================
-- updated_at TRIGGER (shared function)
-- ============================================================

CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_plans_updated_at
    BEFORE UPDATE ON plans
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TRIGGER trg_users_updated_at
    BEFORE UPDATE ON users
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TRIGGER trg_sessions_updated_at
    BEFORE UPDATE ON sessions
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TRIGGER trg_summaries_updated_at
    BEFORE UPDATE ON summaries
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TRIGGER trg_usage_updated_at
    BEFORE UPDATE ON usage
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();


-- ============================================================
-- SEED: default plans
-- ============================================================

INSERT INTO plans (slug, tier, daily_cost_limit, monthly_cost) VALUES
    ('free',     1, 0.05,  0.00),
    ('starter',  2, 0.25,  9.99),
    ('standard', 3, 1.00, 29.99),
    ('heavy',    4, 5.00, 99.99);


COMMIT;