import os
import json
from datetime import datetime, timezone
from flask import Flask, request, jsonify, send_from_directory, make_response, abort

# ------------------------------------------------------------------------------
# App setup
# ------------------------------------------------------------------------------
API_TOKEN = os.getenv("API_TOKEN", "").strip()

app = Flask(
    __name__,
    static_folder="static",          # folder where chat.html/docs.html live
    static_url_path="/static"
)

# ------------------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------------------
def now_iso():
    return datetime.now(timezone.utc).isoformat()

def bearer_token_from_request(req: request) -> str | None:
    """Return token string if header looks like: Authorization: Bearer <token>"""
    auth = req.headers.get("Authorization", "")
    if not auth:
        return None
    parts = auth.split()
    if len(parts) == 2 and parts[0].lower() == "bearer":
        return parts[1]
    return None

def require_auth():
    """Abort 401 if bearer token missing/invalid."""
    if not API_TOKEN:
        abort(make_response(jsonify(error="Server missing API_TOKEN"), 500))
    tok = bearer_token_from_request(request)
    if tok != API_TOKEN:
        abort(make_response(jsonify(error="Unauthorized", ok=False), 401))

# ------------------------------------------------------------------------------
# Public routes
# ------------------------------------------------------------------------------
@app.route("/")
def home():
    # Minimal landing with links (no duplicate endpoint names)
    html = """<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width,initial-scale=1" />
    <title>Friday API</title>
    <link rel="icon" href="/static/favicon.ico" />
    <link rel="stylesheet" href="/static/site.css" />
    <style>
      body{font-family:system-ui,-apple-system,Segoe UI,Roboto,Inter,Arial,sans-serif;
           margin:0; background:#0b1220; color:#e9eefc}
      header{display:flex;justify-content:space-between;align-items:center;
             padding:20px 24px;background:#0f172a;border-bottom:1px solid #1f2a44}
      a{color:#8ab4ff;text-decoration:none}
      .btn{display:inline-block;background:#2563eb;color:#fff;padding:10px 14px;
           border-radius:10px;margin-right:10px}
      .wrap{max-width:840px;margin:40px auto;padding:0 16px}
      .links{margin-top:16px}
    </style>
  </head>
  <body>
    <header>
      <div>🚀 <strong>Friday API</strong></div>
      <nav>
        <a class="btn" href="/ui">Open Chat UI</a>
        <a class="btn" href="/docs">Docs</a>
      </nav>
    </header>
    <div class="wrap">
      <p>If you can see this, the backend is deployed successfully.</p>
      <div class="links">
        <p>Quick links: <a href="/health">/health</a>,
           <a href="/docs">/docs</a>,
           <a href="/ui">/ui</a></p>
      </div>
    </div>
  </body>
</html>"""
    return html

@app.route("/health")
def health():
    return jsonify(
        ok=True,
        status="running",
        key_present=bool(API_TOKEN),
        time=now_iso(),
    )

# ------------------------------------------------------------------------------
# Static UI pages
# ------------------------------------------------------------------------------
@app.route("/ui")
def ui():
    # Serve static/chat.html
    return send_from_directory("static", "chat.html")

@app.route("/docs")
def docs():
    # Serve static/docs.html
    return send_from_directory("static", "docs.html")

# ------------------------------------------------------------------------------
# Protected API routes
# ------------------------------------------------------------------------------
@app.route("/__routes", methods=["GET"])
def list_routes():
    require_auth()
    # Small introspection of registered routes (methods other than HEAD/OPTIONS)
    info = []
    for rule in app.url_map.iter_rules():
        methods = sorted(m for m in rule.methods if m not in ("HEAD", "OPTIONS"))
        info.append({"rule": str(rule), "endpoint": rule.endpoint, "methods": methods})
    return jsonify(ok=True, routes=info)

@app.route("/chat", methods=["POST"])
def chat():
    require_auth()
    # Expect JSON: { "message": "..." }
    try:
        data = request.get_json(force=True, silent=False) or {}
    except Exception:
        return jsonify(error="Invalid JSON body", ok=False), 400

    msg = (data.get("message") or "").strip()
    if not msg:
        return jsonify(error="Missing 'message'", ok=False), 400

    # Echo demo (plug in your real LLM logic here)
    reply = f"Friday heard: {msg}"
    return jsonify(ok=True, reply=reply)

# ------------------------------------------------------------------------------
# Error handlers (JSON for API paths)
# ------------------------------------------------------------------------------
@app.errorhandler(401)
def _unauth(e):
    return jsonify(error="Unauthorized", ok=False), 401

@app.errorhandler(405)
def _method_not_allowed(e):
    # Helpful JSON for /chat if someone GETs it from browser
    return jsonify(error="Method Not Allowed", ok=False), 405

@app.errorhandler(404)
def _not_found(e):
    # Keep normal HTML 404 for non-API pages
    if request.path.startswith("/chat") or request.path.startswith("/__routes"):
        return jsonify(error="Not Found", ok=False), 404
    return e, 404

# ------------------------------------------------------------------------------
# Entrypoint (Render uses `gunicorn`/`waitress-serve app:app` per your start cmd)
# ------------------------------------------------------------------------------
if __name__ == "__main__":
    # Local dev (optional): python app.py
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "5000")), debug=True)



















































