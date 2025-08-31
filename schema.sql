-- Postgres (optional pgvector store)
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS rag_chunks (
  id TEXT PRIMARY KEY,
  user_id TEXT,
  org_id TEXT,
  name TEXT,
  content TEXT,
  embedding vector(1536),
  created TIMESTAMP DEFAULT NOW()
);

-- SQLite (created automatically in app.py, included here for completeness)
-- messages(cid,user_id,org_id,role,content,ts)
-- users(id,org_id,email,name,pwd_hash,created)
-- orgs(id,name,created)
-- invites(code,org_id,created,used_by)
-- docs(id,user_id,org_id,name,content,embedding,created)
