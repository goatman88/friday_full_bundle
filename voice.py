# src/voice.py
import base64
from flask import Blueprint, request, jsonify, current_app

bp = Blueprint("voice", __name__, url_prefix="/api/voice")

def _client():
    try:
        return current_app.view_functions["rag_query"].__globals__["openai_client"]
    except Exception:
        return None

def _bearer():
    tok = request.headers.get("Authorization","")
    return tok.split(" ",1)[1].strip() if tok.startswith("Bearer ") else None

@bp.post("/tts")
def tts():
    if not _bearer(): return jsonify({"ok":False,"error":"Unauthorized"}), 401
    body = request.get_json(silent=True) or {}
    text = (body.get("text") or "").strip()
    voice = (body.get("voice") or "alloy").strip()
    if not text: return jsonify({"ok":False,"error":"Missing text"}), 400

    client = _client()
    if not client: return jsonify({"ok":False,"error":"OpenAI disabled"}), 503

    # gpt-4o-mini-tts (returns base64)
    audio = client.audio.speech.create(
        model="gpt-4o-mini-tts",
        voice=voice,
        input=text,
        format="mp3"
    )
    b64 = base64.b64encode(audio.read()).decode("utf-8")
    return jsonify({"ok":True, "format":"mp3", "audio_b64": b64})

@bp.post("/stt")
def stt():
    if not _bearer(): return jsonify({"ok":False,"error":"Unauthorized"}), 401
    client = _client()
    if not client: return jsonify({"ok":False,"error":"OpenAI disabled"}), 503

    if "file" not in request.files:
        return jsonify({"ok":False,"error":"Upload field 'file' required"}), 400
    f = request.files["file"]
    # Whisper-1 transcription
    transcript = client.audio.transcriptions.create(
        model="whisper-1",
        file=(f.filename, f.stream, f.mimetype)
    )
    return jsonify({"ok":True, "text": transcript.text})

