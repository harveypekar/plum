"""RAG module for running research knowledge base.

Ingests research files (summaries, source articles, PDFs) into pgvector,
provides similarity search for grounding AI coaching in evidence.

Usage:
    python rag.py --ingest              # Ingest all research files (incremental)
    python rag.py "cardiac drift"       # Query the knowledge base
    python rag.py --stats               # Show ingestion statistics
"""

import hashlib
import re
import sys
from pathlib import Path

import db

SCRIPT_DIR = Path(__file__).resolve().parent
RESEARCH_DIR = SCRIPT_DIR / "research"

# ---------------------------------------------------------------------------
# Embedding model
# ---------------------------------------------------------------------------

_model = None


def get_model():
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer
        _model = SentenceTransformer("all-MiniLM-L6-v2")
    return _model


def embed_texts(texts: list[str]) -> list[list[float]]:
    """Batch embed texts. Returns list of 384-dim vectors."""
    return get_model().encode(texts, normalize_embeddings=True).tolist()


# ---------------------------------------------------------------------------
# File hashing
# ---------------------------------------------------------------------------

def file_hash(path: Path) -> str:
    """SHA256 hash of file contents."""
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


def topic_from_filename(path: Path) -> str:
    """Extract topic slug from filename: 'cardiac-drift-1.md' -> 'cardiac-drift'."""
    stem = path.stem
    # Strip trailing -N suffix (source article numbering)
    return re.sub(r"-\d+$", "", stem)


# ---------------------------------------------------------------------------
# YAML front-matter parser (minimal, no PyYAML dependency)
# ---------------------------------------------------------------------------

def parse_front_matter(text: str) -> tuple[dict, str]:
    """Parse YAML front-matter from markdown. Returns (metadata, body)."""
    if not text.startswith("---"):
        return {}, text

    end = text.find("\n---", 3)
    if end == -1:
        return {}, text

    fm_block = text[3:end].strip()
    body = text[end + 4:].strip()

    meta = {}
    for line in fm_block.split("\n"):
        if ":" in line:
            key, val = line.split(":", 1)
            val = val.strip().strip('"').strip("'")
            meta[key.strip()] = val

    return meta, body


# ---------------------------------------------------------------------------
# Chunking
# ---------------------------------------------------------------------------

def chunk_markdown_by_sections(text: str) -> list[tuple[str, str]]:
    """Split markdown at ## headers. Returns list of (section_name, content)."""
    chunks = []
    current_name = None
    current_lines = []

    for line in text.split("\n"):
        if line.startswith("## "):
            if current_name is not None:
                content = "\n".join(current_lines).strip()
                if content:
                    chunks.append((current_name, content))
            current_name = line[3:].strip()
            current_lines = []
        else:
            current_lines.append(line)

    # Last section
    if current_name is not None:
        content = "\n".join(current_lines).strip()
        if content:
            chunks.append((current_name, content))

    # If no ## headers found, treat whole text as one chunk
    if not chunks and text.strip():
        # Use first # header as name, or "Content"
        first_line = text.strip().split("\n")[0]
        name = first_line.lstrip("# ").strip() if first_line.startswith("#") else "Content"
        chunks.append((name, text.strip()))

    return chunks


def chunk_text_by_paragraphs(text: str, target_tokens: int = 500,
                              overlap_tokens: int = 50) -> list[tuple[str, str]]:
    """Chunk plain text at paragraph boundaries. Returns list of (None, content)."""
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    if not paragraphs:
        return []

    chunks = []
    current = []
    current_tokens = 0

    for para in paragraphs:
        para_tokens = len(para.split())
        if current_tokens + para_tokens > target_tokens and current:
            chunks.append((None, "\n\n".join(current)))
            # Overlap: keep last paragraph if it fits
            if current and len(current[-1].split()) <= overlap_tokens:
                current = [current[-1]]
                current_tokens = len(current[-1].split())
            else:
                current = []
                current_tokens = 0
        current.append(para)
        current_tokens += para_tokens

    if current:
        chunks.append((None, "\n\n".join(current)))

    return chunks


def estimate_tokens(text: str) -> int:
    """Rough token estimate (~0.75 words per token for English)."""
    return int(len(text.split()) / 0.75)


# ---------------------------------------------------------------------------
# Ingestion
# ---------------------------------------------------------------------------

def ingest_markdown(path: Path, source_type: str):
    """Ingest a markdown file (summary or source article)."""
    fhash = file_hash(path)
    rel_path = str(path.relative_to(RESEARCH_DIR))

    # Skip if unchanged
    stored_hash = db.get_document_hash(rel_path)
    if stored_hash == fhash:
        return 0

    text = path.read_text(encoding="utf-8")
    meta, body = parse_front_matter(text)

    topic = topic_from_filename(path)
    title = meta.get("title") or path.stem.replace("-", " ").title()
    url = meta.get("url")
    doc_type = meta.get("type")

    # Upsert document and clear old chunks
    doc_id = db.upsert_research_document(
        file_path=rel_path, source_type=source_type,
        title=title, url=url, topic=topic, doc_type=doc_type, file_hash=fhash
    )
    db.delete_document_chunks(doc_id)

    # Chunk by ## sections
    chunks = chunk_markdown_by_sections(body)

    if not chunks:
        return 0

    # Batch embed all chunks
    texts = [content for _, content in chunks]
    embeddings = embed_texts(texts)

    for i, ((section_name, content), emb) in enumerate(zip(chunks, embeddings)):
        db.insert_chunk(
            doc_id=doc_id, chunk_index=i, section_name=section_name,
            content=content, token_count=estimate_tokens(content), embedding=emb
        )

    return len(chunks)


def ingest_pdf(path: Path):
    """Ingest a PDF file using PyMuPDF."""
    import fitz

    fhash = file_hash(path)
    rel_path = str(path.relative_to(RESEARCH_DIR))

    stored_hash = db.get_document_hash(rel_path)
    if stored_hash == fhash:
        return 0

    topic = topic_from_filename(path)
    title = path.stem.replace("-", " ").replace("_", " ").title()

    doc_id = db.upsert_research_document(
        file_path=rel_path, source_type="pdf",
        title=title, url=None, topic=topic, doc_type="pdf", file_hash=fhash
    )
    db.delete_document_chunks(doc_id)

    # Extract text from all pages
    doc = fitz.open(str(path))
    full_text = ""
    for page in doc:
        full_text += page.get_text() + "\n\n"
    doc.close()

    # Strip NUL bytes and other control chars that break SQL
    full_text = full_text.replace("\x00", "").strip()
    if not full_text:
        print(f"  WARNING: no text extracted from {path.name}")
        return 0

    chunks = chunk_text_by_paragraphs(full_text, target_tokens=500, overlap_tokens=50)

    if not chunks:
        return 0

    texts = [content for _, content in chunks]
    embeddings = embed_texts(texts)

    for i, ((section_name, content), emb) in enumerate(zip(chunks, embeddings)):
        db.insert_chunk(
            doc_id=doc_id, chunk_index=i, section_name=section_name,
            content=content, token_count=estimate_tokens(content), embedding=emb
        )

    return len(chunks)


def ingest_all():
    """Process all research files: summaries, source MDs, PDFs."""
    db.ensure_schema()

    total_docs = 0
    total_chunks = 0

    # 1. Summaries
    summary_dir = RESEARCH_DIR / "summary"
    if summary_dir.exists():
        for path in sorted(summary_dir.glob("*.md")):
            n = ingest_markdown(path, source_type="summary")
            if n > 0:
                print(f"  {path.name}: {n} chunks")
                total_docs += 1
                total_chunks += n

    # 2. Source articles (MD only)
    source_dir = RESEARCH_DIR / "source"
    if source_dir.exists():
        for path in sorted(source_dir.glob("*.md")):
            n = ingest_markdown(path, source_type="source_article")
            if n > 0:
                print(f"  {path.name}: {n} chunks")
                total_docs += 1
                total_chunks += n

    # 3. PDFs
    if source_dir.exists():
        for path in sorted(source_dir.glob("*.pdf")):
            n = ingest_pdf(path)
            if n > 0:
                print(f"  {path.name}: {n} chunks")
                total_docs += 1
                total_chunks += n

    print(f"\nDone. {total_chunks} chunks from {total_docs} documents.")


# ---------------------------------------------------------------------------
# Retrieval
# ---------------------------------------------------------------------------

def query(text: str, top_k: int = 5, exclude_chunk_ids: list = None) -> list[dict]:
    """Embed query text, search pgvector, return results with metadata."""
    embedding = embed_texts([text])[0]
    return db.vector_search(embedding, top_k=top_k, exclude_chunk_ids=exclude_chunk_ids)


def format_context(results: list[dict]) -> str:
    """Format retrieved chunks as text block for LLM prompt injection."""
    parts = []
    for r in results:
        header = r.get("title") or r.get("topic") or "Research"
        if r.get("section_name"):
            header += f" — {r['section_name']}"
        parts.append(f"[{header}]\n{r['content']}\n[Source: {r['file_path']}]")
    return "\n\n".join(parts)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def show_stats():
    """Show ingestion statistics."""
    conn = db.get_connection()
    with conn.cursor() as cur:
        cur.execute("SELECT source_type, count(*) FROM research_documents GROUP BY source_type ORDER BY source_type")
        rows = cur.fetchall()
        print("Documents by type:")
        for source_type, count in rows:
            print(f"  {source_type}: {count}")

        cur.execute("SELECT count(*) FROM research_chunks")
        total = cur.fetchone()[0]
        print(f"\nTotal chunks: {total}")


def main():
    import argparse
    parser = argparse.ArgumentParser(description="RAG knowledge base for running coach.")
    parser.add_argument("query_text", nargs="?", help="Query text for similarity search")
    parser.add_argument("--ingest", action="store_true", help="Ingest all research files")
    parser.add_argument("--stats", action="store_true", help="Show ingestion statistics")
    parser.add_argument("--top-k", type=int, default=5, help="Number of results (default: 5)")
    args = parser.parse_args()

    if args.ingest:
        print("Ingesting research files...")
        ingest_all()
    elif args.stats:
        show_stats()
    elif args.query_text:
        print(f"Querying: {args.query_text}\n")
        results = query(args.query_text, top_k=args.top_k)
        for i, r in enumerate(results, 1):
            score = f"{r['score']:.3f}" if r.get('score') is not None else "?"
            source = r.get("file_path", "unknown")
            section = r.get("section_name", "")
            title = r.get("title", "")
            print(f"--- Result {i} (score: {score}) ---")
            if title:
                print(f"Title: {title}")
            print(f"Source: {source}")
            if section:
                print(f"Section: {section}")
            preview = r["content"][:300]
            if len(r["content"]) > 300:
                preview += "..."
            print(f"\n{preview}\n")
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
