# Friday AI (Flask) – with Redis History

A tiny Flask service + static chat UI. Works out-of-the-box with **dev echo** replies and supports OpenAI, persistent history (Redis), and basic admin mint/redeem for access codes.

---

## Endpoints

- **UI**
  - `GET /` and `GET /chat` → serves `static/chat.html`
- **Diagnostics**
  - `GET /routes`
  - `GET /debug/health`
- **Chat**
  - `POST /api/chat` → `{ "message": "...", "username": "guest", "model": "gpt-4o-mini" }`
  - `GET  /api/chat/stream?message=..&username=..` (simple SSE demo)
- **History**
  - `GET /api/history?username=guest`
  - `GET /api/history/export?username=guest` → downloads JSON
- **Models**
  - `GET  /api/models`
  - `POST /api/model` → `{ "model": "gpt-4o" }` (global)
- **Admin**
  - `POST /api/admin/mint` → header `Authorization: Bearer <ADMIN_TOKEN>`, body `{ "count": 1 }`
  - `POST /api/auth/redeem` → `{ "code": "<token>", "username": "newuser" }`

---

## Environment variables

| Name                | Required | Example / Notes |
|---------------------|----------|-----------------|
| `PORT`              | no       | Render injects this automatically. Locally defaults to `5000`. |
| `OPENAI_API_KEY`    | optional | Set to use real completions. If absent, the API returns a friendly dev-echo. |
| `OPENAI_MODEL`      | optional | Default active model. e.g. `gpt-4o-mini` |
| `REDIS_URL`         | optional (recommended) | `redis://default:<password>@<host>:6379/0` |
| `ADMIN_TOKEN`       | optional | Enables `/api/admin/mint` (Bearer). Set a long random secret. |
| `CORS_ALLOW_ORIGINS`| optional | Defaults to `*` |

> **Render tip (Redis URL):** if you also created a Render **Redis** instance, open it → **Connect** → copy the `redis://...` string and paste into your web service’s **Environment** as `REDIS_URL`.

---

## Local dev

```bash
# create venv
python -m venv .venv
# activate (mac/linux)
source .venv/bin/activate
# activate (Windows PowerShell)
# .venv\Scripts\Activate.ps1

pip install -r requirements.txt
# Run with dev echo replies (no OpenAI key needed)
python app.py
# open http://localhost:5000/chat


## Quick start
```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env  # fill values
python app.py


