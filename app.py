import os
import time
from pathlib import Path
from typing import Optional

from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from dotenv import load_dotenv

# ---- Bootstrapping
load_dotenv()  # reads .env if present (works on Render too if you add env vars there)

BASE_DIR = Path(__file__).parent.resolve()
DATA_DIR = BASE_DIR / "data"
UPLOAD_DIR = DATA_DIR / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

OPENAI_API_KEY: Optional[str] = os.getenv("OPENAI_API_KEY") or os.getenv("OPENAI_API_KEY_1")
MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

app = Flask(__name__)
CORS(app)
app.config["MAX_CONTENT_LENGTH"] = 100 * 1024 * 1024  # 100 MB uploads


# ---------- helpers
def has_key() -> bool:
    return bool(OPENAI_API_KEY and OPENAI_API_KEY.strip())


def cheap_local_reply(user_msg: str) -> str:
    """Fallback answer when no OpenAI key is present or API call fails."""
    outline = [
        "Problem summary: " + (user_msg or "(no message provided)"),
        "Plan: break the problem into 3–5 concrete steps",
        "Prioritize the highest-leverage step first",
        "Retest/measure after each step and iterate."
    ]
    return "\n".join(outline)


def call_openai(user_msg: str) -> str:
    """
    Small, robust wrapper. If anything goes wrong we fall back locally.
    """
    if not has_key():
        return cheap_local_reply(user_msg)

    try:
        from openai import OpenAI
        client = OpenAI(api_key=OPENAI_API_KEY)
        resp = client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system",
                 "content": (
                     "You are Friday, an Einstein-level analyst. "
                     "Think step-by-step, use checklists and a RUSH matrix "
                     "(Risk, Urgency, Scope, Hurdle) when helpful. "
                     "Be clear, concise, and actionable."
                 )},
                {"role": "user", "content": user_msg or ""}
            ],
            temperature=0.2,
        )
        return resp.choices[0].message.content.strip()
    except Exception as e:
        # Keep backend always answering; don’t crash chat.
        return f"OpenAI unavailable; giving a fast local answer.\n\n{cheap_local_reply(user_msg)}"


# ---------- routes

@app.get("/")
def root():
    return jsonify({"ok": True, "message": "Friday API is up"})

@app.get("/health")
def health():
    return jsonify({"ok": True, "status": "running"})

@app.post("/chat")
def chat():
    data = request.get_json(silent=True) or {}
    msg = (data.get("message") or "").strip()
    if not msg:
        return jsonify({"ok": False, "error": "message is required"}), 400
    return jsonify({"ok": True, "reply": f"You said: {msg}"})



@app.post("/data/upload")
def data_upload():
    """
    Accepts ANY file type via multipart/form-data.
    Field name: file (supports multiple files with key 'file' repeated)
    """
    if "file" not in request.files:
        return jsonify({"ok": False, "error": "Use multipart/form-data with key 'file'."}), 400

    files = request.files.getlist("file")
    saved = []

    for f in files:
        if not f.filename:
            continue
        # Make filename safe and unique
        stem = Path(f.filename).name
        ts = int(time.time() * 1000)
        safe_name = f"{ts}__{stem}"
        dest = UPLOAD_DIR / safe_name
        f.save(dest)

        saved.append({
            "filename": stem,
            "stored_as": safe_name,
            "bytes": dest.stat().st_size,
            "path": str(dest.relative_to(BASE_DIR).as_posix())
        })

    if not saved:
        return jsonify({"ok": False, "error": "No valid files provided."}), 400

    return jsonify({"ok": True, "count": len(saved), "files": saved})


@app.get("/files/<path:filename>")
def serve_file(filename: str):
    # Download previously uploaded files
    return send_from_directory(UPLOAD_DIR, filename, as_attachment=True)

# --- DEBUG: list routes ---
@app.get("/__routes")
def __routes():
    routes = []
    for rule in app.url_map.iter_rules():
        routes.append({
            "rule": str(rule),
            "endpoint": rule.endpoint,
            "methods": sorted(m for m in rule.methods if m not in {"HEAD", "OPTIONS"})
        })
    return jsonify({"ok": True, "routes": routes})


if __name__ == "__main__":
    # Local dev: python app.py
    app.run(host="127.0.0.1", port=5000, debug=True)





































