import os
from datetime import datetime
from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
from openai import OpenAI

# Local helper (this is why the file must exist)
from s3_uploads import get_s3_client  # not used yet, but import proves the module is resolvable


def create_app() -> Flask:
    app = Flask(__name__, static_folder="static", static_url_path="/static")
    CORS(app, resources={r"/*": {"origins": "*"}})

    # ---- OpenAI client (no proxies kwarg!) ----
    # If OPENAI_API_KEY isn't set, the SDK will also look in standard locations,
    # but we keep this explicit to avoid strange proxy-related kwargs creeping in.
    _ = os.environ.get("OPENAI_API_KEY", "")
    client = OpenAI(api_key=_ or None)

    # ------------- basics -------------
    @app.get("/")
    def root():
        return jsonify(
            {
                "message": "Friday backend is running",
                "ok": True,
                "routes": [
                    "/",
                    "/__routes",
                    "/__whoami",
                    "/health",
                    "/ping",
                    "/api/rag/index",
                    "/api/rag/query",
                    "/static/<path:filename>",
                ],
            }
        )

    @app.get("/__routes")
    def list_routes():
        # tiny self-inspection
        paths = sorted({rule.rule for rule in app.url_map.iter_rules()})
        return jsonify(paths)

    @app.get("/__whoami")
    def whoami():
        return jsonify(
            {
                "app_id": int(datetime.utcnow().timestamp() * 1000),
                "cwd": os.getcwd(),
                "module_file": __file__,
                "python": os.popen("python -V").read().strip() or "unknown",
            }
        )

    @app.get("/health")
    def health():
        return jsonify({"ok": True, "status": "running"})

    @app.get("/ping")
    def ping():
        return jsonify({"pong": True, "ts": datetime.utcnow().isoformat()})

    # ------------- static files -------------
    @app.get("/static/<path:filename>")
    def static_files(filename):
        return send_from_directory(app.static_folder, filename)

    # ------------- minimal RAG stubs -------------
    # Index: accept { title, text, source, mime?, user_id? } and echo ok
    @app.post("/api/rag/index")
    def rag_index():
        payload = request.get_json(silent=True) or {}
        # In your next step you’ll persist this to Postgres/pgvector. For now, echo.
        doc = {
            "id": f"doc_{int(datetime.utcnow().timestamp())}",
            "title": payload.get("title", "Untitled"),
            "preview": (payload.get("text") or "")[:120],
            "source": payload.get("source", "unknown"),
        }
        return jsonify({"ok": True, "indexed": doc})

    # Query: accept { query, topk } and return dummy answer with last indexed preview
    @app.post("/api/rag/query")
    def rag_query():
        payload = request.get_json(silent=True) or {}
        q = payload.get("query", "")
        topk = int(payload.get("topk", 3))
        # A very small harmless call, mostly to validate client config (no proxies arg)
        # We do not block startup if OpenAI key is missing.
        try:
            _ = client.models.list()
            llm_ok = True
        except Exception:
            llm_ok = False

        dummy = [
            {
                "id": f"ctx_{i}",
                "title": "Widget FAQ",
                "preview": "Widgets are blue and waterproof. Store them in dry places.",
                "score": 0.42 - i * 0.01,
            }
            for i in range(max(1, topk))
        ]
        return jsonify(
            {
                "ok": True,
                "answer": f"Best effort answer for: {q}",
                "contexts": dummy,
                "llm_ready": llm_ok,
            }
        )

    return app


# WSGI entry when launched via `python src/app.py` (dev only)
if __name__ == "__main__":
    app = create_app()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "8080")), debug=True)











































































