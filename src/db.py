from typing import Any, Dict, Iterable, List, Optional, Tuple
import json
import psycopg
from psycopg.rows import dict_row
from pgvector.psycopg import register_vector
from . import settings

_conn_cache = None

def get_conn() -> psycopg.Connection:
    global _conn_cache
    if _conn_cache and not _conn_cache.closed:
        return _conn_cache
    if not settings.DATABASE_URL:
        raise RuntimeError("DATABASE_URL is not set")
    _conn_cache = psycopg.connect(settings.DATABASE_URL, autocommit=True)
    register_vector(_conn_cache)
    return _conn_cache

SCHEMA_SQL = f"""
CREATE EXTENSION IF NOT EXISTS vector;
CREATE TABLE IF NOT EXISTS rag_docs (
  id          BIGSERIAL PRIMARY KEY,
  title       TEXT,
  source      TEXT,
  user_id     TEXT,
  mime        TEXT,
  text        TEXT NOT NULL,
  metadata    JSONB DEFAULT '{{}}'::jsonb,
  embedding   VECTOR({settings.EMBED_DIM}),
  created_at  TIMESTAMPTZ DEFAULT now()
);
-- Similarity index
CREATE INDEX IF NOT EXISTS rag_docs_ivfflat
  ON rag_docs USING ivfflat (embedding vector_cosine_ops)
  WITH (lists = 100);
-- Lightweight metadata index
CREATE INDEX IF NOT EXISTS rag_docs_gin_meta ON rag_docs USING GIN (metadata);
CREATE INDEX IF NOT EXISTS rag_docs_source ON rag_docs (source);
"""

def init_db() -> Dict[str, Any]:
    with get_conn() as conn, conn.cursor(row_factory=dict_row) as cur:
        for stmt in [s.strip() for s in SCHEMA_SQL.split(";") if s.strip()]:
            cur.execute(stmt + ";")
        cur.execute("SELECT count(*) AS n FROM rag_docs;")
        n = cur.fetchone()["n"]
        return {"ok": True, "table": "rag_docs", "count": n}

def insert_doc(title: str, text: str, source: str, user_id: str, mime: str,
               embedding: List[float], metadata: Optional[Dict[str, Any]] = None) -> int:
    md = json.dumps(metadata or {})
    sql = """
        INSERT INTO rag_docs (title, text, source, user_id, mime, metadata, embedding)
        VALUES (%s, %s, %s, %s, %s, %s::jsonb, %s)
        RETURNING id;
    """
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(sql, (title, text, source, user_id, mime, md, embedding))
        return cur.fetchone()[0]

def upsert_batch(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    sql = """
        INSERT INTO rag_docs (title, text, source, user_id, mime, metadata, embedding)
        VALUES (%s, %s, %s, %s, %s, %s::jsonb, %s);
    """
    with get_conn() as conn, conn.cursor() as cur:
        for r in rows:
            md = json.dumps(r.get("metadata") or {})
            cur.execute(sql, (r.get("title"), r["text"], r.get("source","admin"),
                              r.get("user_id","public"), r.get("mime","text/plain"), md, r["embedding"]))
    return {"ok": True, "inserted": len(rows)}

def delete_docs(id: Optional[int] = None, source: Optional[str] = None) -> Dict[str, Any]:
    with get_conn() as conn, conn.cursor() as cur:
        if id is not None:
            cur.execute("DELETE FROM rag_docs WHERE id=%s;", (id,))
            return {"ok": True, "deleted": cur.rowcount}
        if source:
            cur.execute("DELETE FROM rag_docs WHERE source=%s;", (source,))
            return {"ok": True, "deleted": cur.rowcount}
        return {"ok": False, "error": "provide id or source"}

def search_similar(embedding: List[float], topk: int = 3,
                   source: Optional[str]=None, user_id: Optional[str]=None,
                   where_meta: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    sql = """
      SELECT id, title, source, user_id, mime, text,
             1 - (embedding <=> %s) AS score
      FROM rag_docs
    """
    params: List[Any] = [embedding]
    conds: List[str] = []
    if source:
        conds.append("source = %s"); params.append(source)
    if user_id:
        conds.append("user_id = %s"); params.append(user_id)
    if where_meta:
        conds.append("metadata @> %s::jsonb"); params.append(json.dumps(where_meta))
    if conds:
        sql += " WHERE " + " AND ".join(conds)
    sql += " ORDER BY embedding <=> %s LIMIT %s;"
    params.extend([embedding, topk])

    with get_conn() as conn, conn.cursor(row_factory=dict_row) as cur:
        cur.execute(sql, params)
        return list(cur.fetchall())

