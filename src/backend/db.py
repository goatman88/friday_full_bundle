# src/backend/db.py
from __future__ import annotations
import os, json
from typing import Any, Iterable, Optional

import psycopg
from psycopg_pool import ConnectionPool

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL is not set")

# Fast, safe pool for web apps
pool = ConnectionPool(
    conninfo=DATABASE_URL,
    min_size=1,
    max_size=int(os.getenv("DB_POOL_MAX", "10")),
    kwargs={"application_name": "friday"},
)

def execute(sql: str, params: Optional[Iterable[Any]] = None) -> int:
    """Run INSERT/UPDATE/DELETE. Returns rowcount."""
    with pool.connection() as conn, conn.cursor() as cur:
        cur.execute(sql, params or ())
        return cur.rowcount

def fetchone(sql: str, params: Optional[Iterable[Any]] = None) -> Optional[tuple]:
    with pool.connection() as conn, conn.cursor() as cur:
        cur.execute(sql, params or ())
        return cur.fetchone()

def fetchall(sql: str, params: Optional[Iterable[Any]] = None) -> list[tuple]:
    with pool.connection() as conn, conn.cursor() as cur:
        cur.execute(sql, params or ())
        return cur.fetchall()

def ensure_schema() -> None:
    """Create pgvector schema + tables/indexes if missing."""
    ddl = """
    CREATE EXTENSION IF NOT EXISTS vector;

    CREATE TABLE IF NOT EXISTS documents (
        id           BIGSERIAL PRIMARY KEY,
        external_id  TEXT UNIQUE,
        title        TEXT,
        s3_uri       TEXT NOT NULL,
        content      TEXT,
        embedding    VECTOR(1536), -- default dim; can be 3072 if you set EMBEDDING_DIMS=3072
        created_at   TIMESTAMPTZ DEFAULT NOW()
    );

    -- HNSW index for cosine distance (needs pgvector >= 0.5.0)
    DO $$
    BEGIN
        IF NOT EXISTS (
            SELECT 1 FROM pg_indexes
            WHERE schemaname = 'public' AND indexname = 'idx_documents_embedding_hnsw'
        ) THEN
            CREATE INDEX idx_documents_embedding_hnsw ON documents
            USING hnsw (embedding vector_cosine_ops);
        END IF;
    END$$;
    """
    with pool.connection() as conn, conn.cursor() as cur:
        cur.execute(ddl)

