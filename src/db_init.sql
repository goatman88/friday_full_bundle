CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS documents (
  id BIGSERIAL PRIMARY KEY,
  external_id TEXT UNIQUE,
  title TEXT,
  source TEXT,
  meta JSONB DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS chunks (
  id BIGSERIAL PRIMARY KEY,
  document_id BIGINT REFERENCES documents(id) ON DELETE CASCADE,
  ord INT NOT NULL,
  text TEXT NOT NULL,
  embedding VECTOR(3072) NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_chunks_embedding_ivf
ON chunks USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);
