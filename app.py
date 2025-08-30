# app.py
import os, json, time
from datetime import datetime
from collections import deque
from flask import (
    Flask, jsonify, request, render_template,
    send_from_directory, Response
)
from flask_cors import CORS

# --- App setup ---------------------------------------------------------------
# If your chat.html is in /templates, change template_folder="templates"
app = Flask(__name__, static_folder="static", template_folder="integrations/templates")
CORS(app)

COMMIT = (os.getenv("RENDER_GIT_COMMIT", "") or os.getenv("COMMIT", ""))[:7]
OPENAI_KEY = os.getenv("OPENAI_API_KEY", "")
DEFAULT_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o")  # nicer than 4o-mini
AVAILABLE_MODELS = [
    "gpt-4o", "gpt-4o-mini", "gpt-4.1-mini", "o3-mini"
]

# simple in-memory history (per app instance)
HISTORY_MAX = 200
HISTORY: deque[dict] = deque(maxlen=HISTORY_MAX)

# active model is mutable at runtime
ACTIVE_MODEL = DEFAULT_MODEL


# --- Pages -------------------------------------------------------------------
@app.get("/")
def home():
    return render_template("chat.html", title="Friday AI")

@app.get("/chat")
def chat_page():
    return render_template("chat.html", title="Friday AI")


# --- Observability -----------------------------------------------------------
@app.get("/routes")
def routes():
    table = []
    for rule in app.url_map.iter_rules():
        table.append({
            "endpoint": rule.endpoint,
            "methods": sorted(m for m in rule.methods if m in {"GET","POST","OPTIONS"}),
            "rule": str(rule),
        })
    return jsonify(sorted(table, key=lambda r: r["rule"]))

@app.get("/debug/health")
def health():
    return jsonify({"ok": True, "commit": COMMIT or None})


# --- API: chat ---------------------------------------------------------------
def _openai_client():
    if not OPENAI_KEY:
        return None
    from openai import OpenAI
    return OpenAI(api_key=OPENAI_KEY)

@app.post("/api/chat")
def api_chat():
    """JSON: { message, stream? }"""
    try:
        data = request.get_json(force=True)
        message = (data.get("message") or "").strip()
        stream = bool(data.get("stream"))
    except Exception:
        return jsonify({"error":"invalid_request","detail":"Expected JSON body"}), 400

    if not message:
        return jsonify({"error":"empty_message"}), 400

    # record user turn
    HISTORY.append({
        "ts": time.time(),
        "role": "user",
        "content": message,
    })

    # Dev echo path if no key
    if not OPENAI_KEY:
        reply = f"Pong! (dev echo) You said: {message}"
        HISTORY.append({"ts": time.time(), "role": "assistant", "content": reply})
        return jsonify({"reply": reply})

    # Real OpenAI call
    try:
        client = _openai_client()
        # We’re using non-stream first; UI’s stream flag is future-proofed
        resp = client.chat.completions.create(
            model=ACTIVE_MODEL,
            messages=[
                {"role":"system","content":"You are Friday AI. Be concise, warm, and helpful."},
                *[{"role":m["role"],"content":m["content"]}
                  for m in list(HISTORY)[-20:] if m["role"] in ("user","assistant")],
                {"role":"user","content":message},
            ],
            temperature=0.6,
        )
        reply = (resp.choices[0].message.content or "").strip()
    except Exception as e:
        return jsonify({"error":"upstream_error","detail":str(e)}), 502

    HISTORY.append({"ts": time.time(), "role":"assistant", "content": reply})
    return jsonify({"reply": reply})


# --- API: models -------------------------------------------------------------
@app.get("/api/models")
def list_models():
    active = ACTIVE_MODEL if OPENAI_KEY else None
    return jsonify({"active": active, "available": AVAILABLE_MODELS})

@app.post("/api/model")
def set_model():
    global ACTIVE_MODEL
    try:
        desired = (request.get_json(force=True).get("model") or "").strip()
    except Exception:
        return jsonify({"error":"invalid_request"}), 400

    if desired not in AVAILABLE_MODELS:
        return jsonify({"error":"unsupported_model","available":AVAILABLE_MODELS}), 400

    ACTIVE_MODEL = desired
    return jsonify({"active": ACTIVE_MODEL})


# --- API: history ------------------------------------------------------------
@app.get("/api/history")
def get_history():
    msgs = [{"role":m["role"], "content":m["content"], "ts":m["ts"]} for m in list(HISTORY)]
    return jsonify({"messages": msgs})

@app.get("/api/history/export")
def export_history():
    def _lines():
        for m in HISTORY:
            yield json.dumps(m, ensure_ascii=False) + "\n"
    fname = f"friday_history_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}Z.ndjson"
    headers = {"Content-Disposition": f'attachment; filename="{fname}"'}
    return Response(_lines(), mimetype="application/x-ndjson", headers=headers)


# --- Static passthrough ------------------------------------------------------
@app.get("/static/<path:filename>")
def static_files(filename):
    return send_from_directory(app.static_folder, filename)


# --- API error pages ---------------------------------------------------------
@app.errorhandler(404)
def not_found(_):
    if request.path.startswith("/api/"):
        return jsonify({"error": "not_found", "path": request.path}), 404
    return "Not Found", 404

@app.errorhandler(405)
def method_not_allowed(_):
    if request.path.startswith("/api/"):
        return jsonify({"error": "method_not_allowed", "path": request.path}), 405
    return "Method Not Allowed", 405


# --- Entrypoint --------------------------------------------------------------
if __name__ == "__main__":
    port = int(os.getenv("PORT", "5000"))
    app.run(host="0.0.0.0", port=port, debug=True)





