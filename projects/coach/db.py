"""DB helper for RAG research knowledge base.

Connection via DATABASE_URL env var, or reads projects/db/.env for password.
Uses pgvector for similarity search on research_chunks.
"""

import os
from pathlib import Path

import psycopg2
import psycopg2.extras

SCRIPT_DIR = Path(__file__).resolve().parent
SCHEMA_PATH = SCRIPT_DIR.parent / "db" / "schema.sql"
DB_ENV_PATH = SCRIPT_DIR.parent / "db" / ".env"

_conn = None


def _read_db_env() -> dict:
    """Read key=value pairs from projects/db/.env."""
    env = {}
    if DB_ENV_PATH.exists():
        for line in DB_ENV_PATH.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip()
    return env


def get_connection():
    """Get a psycopg2 connection (cached). Reads DATABASE_URL or .env."""
    global _conn
    if _conn is not None and _conn.closed == 0:
        return _conn

    dsn = os.environ.get("DATABASE_URL")
    if dsn:
        _conn = psycopg2.connect(dsn)
    else:
        env = _read_db_env()
        _conn = psycopg2.connect(
            host=env.get("POSTGRES_HOST", "localhost"),
            port=int(env.get("POSTGRES_PORT", "5432")),
            user=env.get("POSTGRES_USER", "plum"),
            password=env.get("POSTGRES_PASSWORD", ""),
            dbname=env.get("POSTGRES_DB", "plum"),
        )
    _conn.autocommit = True
    return _conn


def ensure_schema():
    """Run schema.sql if research tables don't exist."""
    conn = get_connection()
    with conn.cursor() as cur:
        cur.execute("""
            SELECT EXISTS (
                SELECT 1 FROM information_schema.tables
                WHERE table_name = 'research_documents'
            )
        """)
        if cur.fetchone()[0]:
            return
    sql = SCHEMA_PATH.read_text()
    with conn.cursor() as cur:
        cur.execute(sql)
    print("Schema created.")


# ---------------------------------------------------------------------------
# RAG document & chunk operations
# ---------------------------------------------------------------------------

def upsert_research_document(file_path, source_type, title, url, topic, doc_type, file_hash):
    """Insert or update a research document. Returns doc_id."""
    conn = get_connection()
    with conn.cursor() as cur:
        cur.execute("""
            INSERT INTO research_documents
                (file_path, source_type, title, url, topic, doc_type, file_hash, embedded_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, NOW())
            ON CONFLICT (file_path) DO UPDATE SET
                source_type = EXCLUDED.source_type,
                title = EXCLUDED.title,
                url = EXCLUDED.url,
                topic = EXCLUDED.topic,
                doc_type = EXCLUDED.doc_type,
                file_hash = EXCLUDED.file_hash,
                embedded_at = NOW()
            RETURNING doc_id
        """, (file_path, source_type, title, url, topic, doc_type, file_hash))
        return cur.fetchone()[0]


def delete_document_chunks(doc_id):
    """Delete all chunks for a document (before re-embedding)."""
    conn = get_connection()
    with conn.cursor() as cur:
        cur.execute("DELETE FROM research_chunks WHERE doc_id = %s", (doc_id,))


def insert_chunk(doc_id, chunk_index, section_name, content, token_count, embedding):
    """Insert a single chunk with its embedding vector."""
    conn = get_connection()
    vec_str = "[" + ",".join(str(x) for x in embedding) + "]"
    with conn.cursor() as cur:
        cur.execute("""
            INSERT INTO research_chunks
                (doc_id, chunk_index, section_name, content, token_count, embedding)
            VALUES (%s, %s, %s, %s, %s, %s::vector)
        """, (doc_id, chunk_index, section_name, content, token_count, vec_str))


def get_document_hash(file_path):
    """Get stored file hash for change detection. Returns None if not found."""
    conn = get_connection()
    with conn.cursor() as cur:
        cur.execute(
            "SELECT file_hash FROM research_documents WHERE file_path = %s",
            (file_path,)
        )
        row = cur.fetchone()
        return row[0] if row else None


def vector_search(embedding, top_k=5, exclude_chunk_ids=None):
    """Cosine similarity search on research_chunks.

    Returns list of dicts with chunk_id, content, section_name, score,
    file_path, title, topic.
    """
    conn = get_connection()
    vec_str = "[" + ",".join(str(x) for x in embedding) + "]"

    exclude_clause = ""
    params = [vec_str, vec_str, top_k]
    if exclude_chunk_ids:
        placeholders = ",".join(["%s"] * len(exclude_chunk_ids))
        exclude_clause = f"AND c.chunk_id NOT IN ({placeholders})"
        params = [vec_str] + list(exclude_chunk_ids) + [vec_str, top_k]

    # Build query: cosine distance (<=>) returns distance, so 1 - distance = similarity
    if exclude_chunk_ids:
        sql = f"""
            SELECT c.chunk_id, c.content, c.section_name,
                   1 - (c.embedding <=> %s::vector) AS score,
                   d.file_path, d.title, d.topic
            FROM research_chunks c
            JOIN research_documents d ON c.doc_id = d.doc_id
            WHERE 1=1 {exclude_clause}
            ORDER BY c.embedding <=> %s::vector
            LIMIT %s
        """
    else:
        sql = """
            SELECT c.chunk_id, c.content, c.section_name,
                   1 - (c.embedding <=> %s::vector) AS score,
                   d.file_path, d.title, d.topic
            FROM research_chunks c
            JOIN research_documents d ON c.doc_id = d.doc_id
            ORDER BY c.embedding <=> %s::vector
            LIMIT %s
        """

    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(sql, params)
        return [dict(row) for row in cur.fetchall()]
