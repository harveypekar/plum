-- RP: Roleplay chat tables
-- Run against the shared PostgreSQL instance (projects/db)

CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS rp_character_cards (
    id              SERIAL PRIMARY KEY,
    name            TEXT NOT NULL,
    avatar          BYTEA,
    card_data       JSONB NOT NULL DEFAULT '{}',
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_rp_cards_name ON rp_character_cards(name);

CREATE TABLE IF NOT EXISTS rp_scenarios (
    id              SERIAL PRIMARY KEY,
    name            TEXT NOT NULL,
    description     TEXT NOT NULL DEFAULT '',
    first_message   TEXT NOT NULL DEFAULT '',
    settings        JSONB NOT NULL DEFAULT '{}',
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

-- Migration: add first_message if missing
DO $$ BEGIN
    ALTER TABLE rp_scenarios ADD COLUMN first_message TEXT NOT NULL DEFAULT '';
EXCEPTION WHEN duplicate_column THEN NULL;
END $$;

CREATE TABLE IF NOT EXISTS rp_conversations (
    id              SERIAL PRIMARY KEY,
    user_card_id    INTEGER NOT NULL REFERENCES rp_character_cards(id) ON DELETE CASCADE,
    ai_card_id      INTEGER NOT NULL REFERENCES rp_character_cards(id) ON DELETE CASCADE,
    scenario_id     INTEGER REFERENCES rp_scenarios(id) ON DELETE SET NULL,
    model           TEXT NOT NULL,
    scene_state     TEXT NOT NULL DEFAULT '',
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

-- Migration: add scene_state if missing
DO $$ BEGIN
    ALTER TABLE rp_conversations ADD COLUMN scene_state TEXT NOT NULL DEFAULT '';
EXCEPTION WHEN duplicate_column THEN NULL;
END $$;

-- Migration: track which message the scene state was last generated from
DO $$ BEGIN
    ALTER TABLE rp_conversations ADD COLUMN scene_state_msg_id INTEGER DEFAULT NULL;
EXCEPTION WHEN duplicate_column THEN NULL;
END $$;

CREATE TABLE IF NOT EXISTS rp_messages (
    id              SERIAL PRIMARY KEY,
    conversation_id INTEGER NOT NULL REFERENCES rp_conversations(id) ON DELETE CASCADE,
    role            TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
    content         TEXT NOT NULL,
    raw_response    JSONB,
    sequence        INTEGER NOT NULL,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_rp_messages_conv ON rp_messages(conversation_id, sequence);

CREATE TABLE IF NOT EXISTS rp_first_message_cache (
    id              SERIAL PRIMARY KEY,
    combo_hash      TEXT NOT NULL UNIQUE,
    card_hash       TEXT NOT NULL,
    scenario_hash   TEXT NOT NULL,
    model           TEXT NOT NULL,
    content         TEXT NOT NULL,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_rp_fmc_combo ON rp_first_message_cache(combo_hash);

CREATE TABLE IF NOT EXISTS rp_fewshot_examples (
    id              SERIAL PRIMARY KEY,
    card_id         INTEGER REFERENCES rp_character_cards(id) ON DELETE CASCADE,
    scene_context   TEXT NOT NULL,
    user_message    TEXT NOT NULL,
    assistant_message TEXT NOT NULL,
    embedding       vector(768) NOT NULL,
    model           TEXT NOT NULL DEFAULT '',
    token_estimate  INTEGER NOT NULL DEFAULT 0,
    active          BOOLEAN NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- Migration: add card_id if missing
DO $$ BEGIN
    ALTER TABLE rp_fewshot_examples ADD COLUMN card_id INTEGER REFERENCES rp_character_cards(id) ON DELETE CASCADE;
EXCEPTION WHEN duplicate_column THEN NULL;
END $$;

-- Migration: add model if missing
DO $$ BEGIN
    ALTER TABLE rp_fewshot_examples ADD COLUMN model TEXT NOT NULL DEFAULT '';
EXCEPTION WHEN duplicate_column THEN NULL;
END $$;

CREATE INDEX IF NOT EXISTS idx_rp_fewshot_embedding
    ON rp_fewshot_examples USING hnsw (embedding vector_cosine_ops)
    WHERE active;

CREATE TABLE IF NOT EXISTS rp_conversation_summaries (
    id              SERIAL PRIMARY KEY,
    conversation_id INTEGER NOT NULL REFERENCES rp_conversations(id) ON DELETE CASCADE,
    summary         TEXT NOT NULL,
    through_msg_id  INTEGER NOT NULL,
    through_sequence INTEGER NOT NULL,
    msg_count       INTEGER NOT NULL,
    token_estimate  INTEGER NOT NULL,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_rp_summaries_conv
    ON rp_conversation_summaries(conversation_id, through_sequence DESC);

-- Migration: track which message the summary was last generated from
DO $$ BEGIN
    ALTER TABLE rp_conversations ADD COLUMN summary_msg_id INTEGER DEFAULT NULL;
EXCEPTION WHEN duplicate_column THEN NULL;
END $$;
