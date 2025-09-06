import os
from functools import wraps
from flask import Flask, request, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

# --- Config ---
API_TOKEN = os.getenv("API_TOKEN", "changeme")
# Report whether the token is actually set in the environment (not the fallback)
KEY_PRESENT = os.getenv("API_TOKEN") is not None


# --- Auth helper ---
def _extract_token_from_headers() -> str | None:
    """Return token from either Authorization: Bearer <token> or X-API-TOKEN."""
    # Custom header
    h = request.headers.get("X-API-TOKEN")
    if h:
        return h

    # Standard Bearer header
    auth = request.headers.get("Authorization", "")
    if auth.lower().startswith("bearer "):
        return auth.split(" ", 1)[1].strip()

    return None


def require_token(fn):
    """Decorator to protect endpoints with API token."""
    @wraps(fn)
    def wrapper(*args, **kwargs):
        # Allow preflight and health without a token
        if request.method == "OPTIONS" or request.path == "/health":
            return fn(*args, **kwargs)

        token = _extract_token_from_headers()
        if token != API_TOKEN:
            return jsonify({"ok": False, "error": "Unauthorized"}), 401
        return fn(*args, **kwargs)
    return wrapper


# --- Routes ---

@app.route("/")
@require_token
def root():
    return jsonify({"ok": True, "msg": "Friday backend online"})


@app.route("/health")
def health():
    return jsonify({
        "ok": True,
        "status": "running",
        "key_present": bool(KEY_PRESENT)
    })


@app.route("/chat", methods=["POST"])
@require_token
def chat():
    data = request.get_json(silent=True) or {}
    message = data.get("message", "")
    return jsonify({"ok": True, "reply": f"Friday heard: {message}"})


@app.route("/data/upload", methods=["POST"])
@require_token
def upload():
    file = request.files.get("file")
    notes = request.form.get("notes", "")

    if not file:
        return jsonify({"ok": False, "error": "No file uploaded"}), 400

    # Save to /tmp (ephemeral on Render)
    save_dir = "/tmp"
    os.makedirs(save_dir, exist_ok=True)
    save_path = os.path.join(save_dir, file.filename)
    file.save(save_path)

    return jsonify({
        "ok": True,
        "notes": notes,
        "saved_as": save_path,
        "bytes": os.path.getsize(save_path)
    })


@app.get("/__routes")
@require_token
def list_routes():
    """Diagnostic endpoint to list all registered routes."""
    routes = []
    for rule in app.url_map.iter_rules():
        methods = sorted(m for m in rule.methods if m not in {"HEAD", "OPTIONS"})
        routes.append({"methods": methods, "rule": str(rule.rule)})
    return jsonify({"ok": True, "routes": routes})


# --- Entrypoint ---
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)














































