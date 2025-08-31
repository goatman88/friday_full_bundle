# Friday AI — Admin + OCR + Role Upload Limits + Qdrant

## Features
- Chat UI `/chat`, Admin UI `/admin`
- JWT auth: access + refresh, role-based (user/admin)
- Uploads: PDF/TXT/MD/DOCX/HTML; optional OCR on DOCX images (Tesseract)
- Vector store priority: **Qdrant** → **PGVector** → Redis fallback
- RAG tools, JSON-mode, history export/clear

## Quick Start (local)
```bash
python -m venv .venv && . .venv/bin/activate  # Windows: .venv\Scripts\Activate
pip install -r requirements.txt
# (optional) docker compose up -d pg qdrant
# choose a vector backend:
#   Qdrant:  export QDRANT_URL=http://localhost:6333
#   PG:      export PG_URL=postgresql://friday:password@localhost:5432/fridaydb
export OPENAI_API_KEY=sk-...
python app.py
## New Admin Goodies
- **Vectors dashboard:** `/vectors` to browse/search/delete user chunks and view stats
- **Maintenance:** `/maint` to run PG VACUUM/REINDEX or Qdrant optimize
- **Tool streaming:** `/api/chat/stream_tools` — SSE emits:
  - `{"type":"tool_event","tool":...,"args":...,"result":...}`
  - `{"type":"delta","delta":"…"}` tokens
  - `{"type":"usage",...}`, then `{"type":"done"}`




