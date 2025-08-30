# Friday AI

Friday AI is a lightweight Flask + OpenAI chatbot web app, deployed on Render.

## Features
- Chat endpoint with streaming (SSE)
- Persistent conversation history (Redis or in-memory fallback)
- Model switching (`/api/models` + `/api/model`)
- Usage stats (`/api/stats`)
- Exportable history (`/api/history/export`)
- Security headers + optional rate limiting

## Endpoints

- `/chat` — Web UI  
- `/api/chat` — POST a message  
- `/api/chat/stream` — SSE streaming chat  
- `/api/history` — conversation history  
- `/api/history/export` — export full thread  
- `/api/models` — list available models  
- `/api/model` — set active model  
- `/api/stats` — runtime stats  
- `/routes` — list all routes  
- `/debug/health` — health/commit info  

## Deploy

1. Set env vars in Render:
   - `OPENAI_API_KEY`
   - `OPENAI_MODEL` (default: `gpt-4o-mini`)
   - `REDIS_URL` (optional, for persistent history)

2. Push to GitHub:
   ```bash
   git add .
   git commit -m "Initial deploy"
   git push origin main
