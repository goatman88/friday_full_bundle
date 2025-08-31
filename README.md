# Friday AI — Flask Starter (Batteries Included)

Chat UI + persistent history (SQLite/Redis), admin panel, backup/restore, JWT auth, moderation guardrails, RAG (embeddings), image generation, file uploads, usage tracking, weather tool, and CI.

## Run locally

```bash
python3 -m venv .venv && source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env  # fill values
python app.py


