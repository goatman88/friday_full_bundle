# app.py
from __future__ import annotations
import os, sys
from flask import Flask, request, jsonify

app = Flask(__name__)

# --------- ROUTES ----------
@app.get("/")
def root():
    return jsonify({
        "ok": True,
        "message": "Friday backend is running",
        "routes": sorted([r.rule for r in app.url_map.iter_rules()])
    }), 200

@app.get("/ping")
def ping():
    return "pong", 200

@app.get("/__routes")
def routes():
    return jsonify(sorted([str(r) for r in app.url_map.iter_rules()])), 200

@app.get("/__whoami")
def whoami():
    return jsonify({
        "module_file": __file__,
        "cwd": os.getcwd(),
        "python": sys.version,
        "app_id": id(app),
    }), 200

@app.get("/health")
def health():
    return jsonify({"ok": True, "status": "running"}), 200

@app.post("/api/rag/index")
def rag_index():
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        return jsonify({"error": "Unauthorized", "ok": False}), 401
    body = request.get_json(silent=True) or {}
    return jsonify({
        "ok": True,
        "indexed": [{"id": "doc_1", "title": body.get("title","")}]
    }), 200

@app.post("/api/rag/query")
def rag_query():
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        return jsonify({"error": "Unauthorized", "ok": False}), 401
    body = request.get_json(silent=True) or {}
    _ = body.get("query","")
    return jsonify({
        "ok": True,
        "answer": "Widgets are blue and waterproof.",
        "contexts": [{
            "id":"doc_1","title":"Widget FAQ","score":0.42,
            "preview":"Widgets are blue and waterproof."
        }]
    }), 200

# --------- STARTUP LOG (shows in Render logs) ----------
print(">>> Booting Friday app… file:", __file__)
print(">>> CWD:", os.getcwd())
print(">>> Routes:", sorted([r.rule for r in app.url_map.iter_rules()]))

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
























































