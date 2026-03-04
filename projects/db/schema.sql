-- pgvector extension for similarity search
CREATE EXTENSION IF NOT EXISTS vector;

-- Research document metadata + change detection
CREATE TABLE IF NOT EXISTS research_documents (
    doc_id          SERIAL PRIMARY KEY,
    source_type     TEXT NOT NULL,          -- 'summary', 'source_article', 'pdf'
    file_path       TEXT NOT NULL UNIQUE,   -- relative path from coach/research/
    title           TEXT,
    url             TEXT,
    topic           TEXT,                   -- e.g. 'cardiac-drift', 'ctl-atl-tsb'
    doc_type        TEXT,                   -- from YAML front-matter
    file_hash       TEXT NOT NULL,          -- SHA256 for change detection
    embedded_at     TIMESTAMPTZ DEFAULT NOW()
);

-- Text chunks with vector embeddings (all-MiniLM-L6-v2 = 384 dimensions)
CREATE TABLE IF NOT EXISTS research_chunks (
    chunk_id        SERIAL PRIMARY KEY,
    doc_id          INTEGER NOT NULL REFERENCES research_documents(doc_id) ON DELETE CASCADE,
    chunk_index     SMALLINT NOT NULL,
    section_name    TEXT,                   -- 'Coaching Context', 'Overview', etc.
    content         TEXT NOT NULL,
    token_count     INTEGER,
    embedding       vector(384) NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_chunks_doc ON research_chunks(doc_id);
CREATE INDEX IF NOT EXISTS idx_chunks_embedding ON research_chunks
    USING ivfflat (embedding vector_cosine_ops) WITH (lists = 20);
