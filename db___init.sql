-- Enable pgvector
CREATE EXTENSION IF NOT EXISTS vector;

-- Documents table (logical docs you ingest)
CREATE TABLE IF NOT EXISTS documents (
  id           BIGSERIAL PRIMARY KEY,
  external_id  TEXT UNIQUE,             -- optional: your file id/url
  title        TEXT,
  source       TEXT,                    -- 'text','url','file','note', etc
  meta         JSONB DEFAULT '{}'::jsonb,
  created_at   TIMESTAMPTZ DEFAULT now()
);

-- Chunk table (embeddings live here)
-- 3072 dims for text-embedding-3-large; 1536 if you use -3-small.
CREATE TABLE IF NOT EXISTS chunks (
  id           BIGSERIAL PRIMARY KEY,
  document_id  BIGINT REFERENCES documents(id) ON DELETE CASCADE,
  ord          INT NOT NULL,            -- chunk order in doc
  text         TEXT NOT NULL,
  embedding    VECTOR(3072) NOT NULL    -- change to (1536) if you use -3-small
);

-- IVF index for fast ANN using cosine distance
CREATE INDEX IF NOT EXISTS idx_chunks_embedding_ivf
ON chunks
USING ivfflat (embedding vector_cosine_ops)
WITH (lists = 100);

-- For small datasets, a HNSW index is also nice (PG16+, pgvector >=0.7)
-- CREATE INDEX IF NOT EXISTS idx_chunks_embedding_hnsw
-- ON chunks USING hnsw (embedding vector_cosine_ops);
