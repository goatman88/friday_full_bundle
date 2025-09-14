# src/vision.py
from flask import Blueprint, request, jsonify, current_app

bp = Blueprint("vision", __name__, url_prefix="/api/vision")

def _client():
    try:
        return current_app.view_functions["rag_query"].__globals__["openai_client"]
    except Exception:
        return None

def _bearer():
    tok = request.headers.get("Authorization","")
    return tok.split(" ",1)[1].strip() if tok.startswith("Bearer ") else None

@bp.post("/describe")
def describe():
    if not _bearer(): return jsonify({"ok":False,"error":"Unauthorized"}), 401
    body = request.get_json(silent=True) or {}
    image_url = (body.get("image_url") or "").strip()
    prompt = (body.get("prompt") or "Describe this image in detail.").strip()
    client = _client()
    if not client: return jsonify({"ok":False,"error":"OpenAI disabled"}), 503
    if not image_url: return jsonify({"ok":False,"error":"image_url required"}), 400

    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{
            "role":"user",
            "content":[
                {"type":"text","text":prompt},
                {"type":"image_url","image_url":{"url":image_url}}
            ]
        }],
        temperature=0.3
    )
    text = resp.choices[0].message.content
    return jsonify({"ok":True, "description": text})

