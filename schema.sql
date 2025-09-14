-- Enable extension
CREATE EXTENSION IF NOT EXISTS vector;

-- Documents table
CREATE TABLE IF NOT EXISTS docs (
  id SERIAL PRIMARY KEY,
  user_id TEXT DEFAULT 'public',
  title TEXT NOT NULL,
  source TEXT,
  mime TEXT,
  text TEXT NOT NULL,
  embedding vector(1536) NOT NULL,
  created_at TIMESTAMPTZ DEFAULT now()
);

-- Cosine-distance index for fast ANN
CREATE INDEX IF NOT EXISTS docs_embedding_ivfflat
  ON docs USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);


CREATE INDEX IF NOT EXISTS idx_documents_embedding_vec_cosine
ON documents
USING ivfflat (embedding_vec vector_cosine_ops) WITH (lists = 100);

CREATE INDEX IF NOT EXISTS idx_documents_user_id
ON documents (COALESCE(user_id,'public'));

UPDATE documents
SET embedding_vec = vector((
  SELECT array_agg((j->>i)::float)
  FROM jsonb_array_elements(embedding) WITH ORDINALITY AS e(j,i)
))
WHERE embedding IS NOT NULL
  AND embedding_vec IS NULL;
ANALYZE documents;


