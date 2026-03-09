-- RP: Roleplay chat tables
-- Run against the shared PostgreSQL instance (projects/db)

CREATE TABLE IF NOT EXISTS rp_character_cards (
    id              SERIAL PRIMARY KEY,
    name            TEXT NOT NULL,
    avatar          BYTEA,
    card_data       JSONB NOT NULL DEFAULT '{}',
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_rp_cards_name ON rp_character_cards(name);

CREATE TABLE IF NOT EXISTS rp_prompt_templates (
    id              SERIAL PRIMARY KEY,
    name            TEXT NOT NULL,
    content         TEXT NOT NULL DEFAULT '',
    active          BOOLEAN NOT NULL DEFAULT FALSE,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS rp_scenarios (
    id              SERIAL PRIMARY KEY,
    name            TEXT NOT NULL,
    description     TEXT NOT NULL DEFAULT '',
    settings        JSONB NOT NULL DEFAULT '{}',
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS rp_conversations (
    id              SERIAL PRIMARY KEY,
    user_card_id    INTEGER NOT NULL REFERENCES rp_character_cards(id) ON DELETE CASCADE,
    ai_card_id      INTEGER NOT NULL REFERENCES rp_character_cards(id) ON DELETE CASCADE,
    scenario_id     INTEGER REFERENCES rp_scenarios(id) ON DELETE SET NULL,
    model           TEXT NOT NULL,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

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
