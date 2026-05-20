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

-- Migration: add category (user vs lora-generated)
DO $$ BEGIN
    ALTER TABLE rp_conversations ADD COLUMN category TEXT NOT NULL DEFAULT 'user';
EXCEPTION WHEN duplicate_column THEN NULL;
END $$;

-- Migration: author's note for mid-conversation style steering
DO $$ BEGIN
    ALTER TABLE rp_conversations ADD COLUMN authors_note TEXT NOT NULL DEFAULT '';
EXCEPTION WHEN duplicate_column THEN NULL;
END $$;
DO $$ BEGIN
    ALTER TABLE rp_conversations ADD COLUMN authors_note_depth INTEGER NOT NULL DEFAULT 4;
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

-- Migration: add pipeline context columns to rp_messages
DO $$ BEGIN
    ALTER TABLE rp_messages ADD COLUMN system_prompt TEXT DEFAULT NULL;
EXCEPTION WHEN duplicate_column THEN NULL;
END $$;

DO $$ BEGIN
    ALTER TABLE rp_messages ADD COLUMN scene_state TEXT DEFAULT NULL;
EXCEPTION WHEN duplicate_column THEN NULL;
END $$;

DO $$ BEGIN
    ALTER TABLE rp_messages ADD COLUMN post_prompt TEXT DEFAULT NULL;
EXCEPTION WHEN duplicate_column THEN NULL;
END $$;

-- Migration: add budget report JSON to rp_messages
DO $$ BEGIN
    ALTER TABLE rp_messages ADD COLUMN budget_json JSONB DEFAULT NULL;
EXCEPTION WHEN duplicate_column THEN NULL;
END $$;

-- Migration: add full assembled prompt to rp_messages
DO $$ BEGIN
    ALTER TABLE rp_messages ADD COLUMN prompt_json JSONB DEFAULT NULL;
EXCEPTION WHEN duplicate_column THEN NULL;
END $$;

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
CREATE INDEX IF NOT EXISTS idx_rp_fewshot_card_id
    ON rp_fewshot_examples(card_id);

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

-- Eval compare: A/B test multiple generation configs for the same prompt
CREATE TABLE IF NOT EXISTS rp_eval_sets (
    id              SERIAL PRIMARY KEY,
    conversation_id INTEGER NOT NULL REFERENCES rp_conversations(id) ON DELETE CASCADE,
    sequence        INTEGER NOT NULL,
    selected_id     INTEGER DEFAULT NULL,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS rp_eval_candidates (
    id              SERIAL PRIMARY KEY,
    eval_set_id     INTEGER NOT NULL REFERENCES rp_eval_sets(id) ON DELETE CASCADE,
    label           TEXT NOT NULL DEFAULT '',
    model           TEXT NOT NULL,
    config          JSONB NOT NULL DEFAULT '{}',
    prompt_json     JSONB,
    budget_json     JSONB,
    content         TEXT NOT NULL DEFAULT '',
    raw_response    JSONB,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_rp_eval_sets_conv
    ON rp_eval_sets(conversation_id, sequence);
CREATE INDEX IF NOT EXISTS idx_rp_eval_candidates_set
    ON rp_eval_candidates(eval_set_id);

-- Migration: preference tags on eval selections
DO $$ BEGIN
    ALTER TABLE rp_eval_sets ADD COLUMN preference_tags JSONB DEFAULT '[]';
EXCEPTION WHEN duplicate_column THEN NULL;
END $$;

CREATE TABLE IF NOT EXISTS rp_eval_metrics (
    id              SERIAL PRIMARY KEY,
    domain          TEXT NOT NULL,
    target_type     TEXT NOT NULL,
    target_id       TEXT NOT NULL,
    target_label    TEXT NOT NULL DEFAULT '',
    judge_model     TEXT NOT NULL,
    rubric_name     TEXT NOT NULL,
    scores          JSONB NOT NULL,
    weighted_average REAL NOT NULL,
    raw_judge_output TEXT NOT NULL DEFAULT '',
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_rp_eval_metrics_target
    ON rp_eval_metrics(target_type, target_id, created_at DESC);

CREATE TABLE IF NOT EXISTS rp_lorebooks (
    id              SERIAL PRIMARY KEY,
    card_id         INTEGER NOT NULL REFERENCES rp_character_cards(id) ON DELETE CASCADE,
    name            TEXT NOT NULL DEFAULT '',
    scan_depth      INTEGER NOT NULL DEFAULT 10,
    token_budget    INTEGER NOT NULL DEFAULT 2048,
    recursive_scan  BOOLEAN NOT NULL DEFAULT FALSE,
    enabled         BOOLEAN NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_rp_lorebooks_card ON rp_lorebooks(card_id);

CREATE TABLE IF NOT EXISTS rp_lorebook_entries (
    id              SERIAL PRIMARY KEY,
    lorebook_id     INTEGER NOT NULL REFERENCES rp_lorebooks(id) ON DELETE CASCADE,
    name            TEXT NOT NULL DEFAULT '',
    keys            TEXT[] NOT NULL DEFAULT '{}',
    secondary_keys  TEXT[] NOT NULL DEFAULT '{}',
    content         TEXT NOT NULL DEFAULT '',
    enabled         BOOLEAN NOT NULL DEFAULT TRUE,
    constant        BOOLEAN NOT NULL DEFAULT FALSE,
    selective       BOOLEAN NOT NULL DEFAULT FALSE,
    position        TEXT NOT NULL DEFAULT 'after_char' CHECK (position IN ('before_char', 'after_char')),
    insertion_order INTEGER NOT NULL DEFAULT 100,
    priority        INTEGER NOT NULL DEFAULT 100,
    comment         TEXT NOT NULL DEFAULT '',
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_rp_lorebook_entries_book
    ON rp_lorebook_entries(lorebook_id, insertion_order);
