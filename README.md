# Friday AI — Vector + Refresh

**What you get**
- Chat UI (`/chat`) with models and login
- JWT auth with short-lived access tokens + long-lived refresh tokens
- File uploads (PDF/TXT/MD/DOCX/HTML) → embeddings → vector DB (PGVector). Falls back to Redis if PG isn’t set.
- RAG tools + JSON-mode endpoint
- Admin-only actions with UI guard (mint codes)

## Quick Start

### Local (no vector DB)
```bash
python -m venv .venv && . .venv/bin/activate  # Windows: .venv\Scripts\Activate
pip install -r requirements.txt
set OPENAI_API_KEY=sk-...   # PowerShell: $env:OPENAI_API_KEY="sk-..."
python app.py



