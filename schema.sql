CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS documents (
  id            BIGSERIAL PRIMARY KEY,
  title         TEXT,
  text          TEXT,
  mime          TEXT,
  source        TEXT,
  user_id       TEXT,
  embedding     JSONB,           -- legacy/fallback
  embedding_vec VECTOR(1536),    -- pgvector (text-embedding-3-small)
  created_at    TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_documents_embedding_vec_cosine
ON documents
USING ivfflat (embedding_vec vector_cosine_ops) WITH (lists = 100);

CREATE INDEX IF NOT EXISTS idx_documents_user_id
ON documents (COALESCE(user_id,'public'));

ANALYZE documents;

