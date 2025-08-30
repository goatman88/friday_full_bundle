# Friday AI — Flask Starter

Chat UI + persistent history (Redis/SQLite/memory), admin panel, backup/restore, moderation, image gen, and file uploads.

## Quick Start (Local)

```bash
python3 -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
export OPENAI_API_KEY=sk-xxx
export ADMIN_TOKEN=super-secure
export ASSET_CDN="https://fonts.googleapis.com,https://fonts.gstatic.com"
python app.py

