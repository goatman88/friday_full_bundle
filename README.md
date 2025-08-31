[![CI](https://github.com/GOATMAN88/friday_full_bundle/actions/workflows/ci.yml/badge.svg)](https://github.com/GOATMAN88/friday_full_bundle/actions/workflows/ci.yml)

# Friday AI — Flask Starter (Multi-tenant, Guardrails, RAG, Tools)

## New capabilities
- **Per-user file buckets**: uploads live in `/uploads/<org|noorg>/<user|anon>/`
- **Orgs + invite codes** (optional): set `INVITE_REQUIRED=true`, create invites via `POST /api/admin/invite` (header `X-Admin-Token`)
- **pgvector (Postgres)**: set `PG_URL`; RAG search switches to vector index automatically
- **Tool calling**: the model auto-routes simple “weather in X” or “calc 2+2” using safe tools
- **Telemetry**: Sentry (dsn), optional OpenTelemetry (OTLP) if `OTEL_ENABLED=true`

## Quick start
```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env  # fill values
python app.py


