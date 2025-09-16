# src/app.py
from __future__ import annotations
import os
from flask import Flask, jsonify

def create_app() -> Flask:
    app = Flask(__name__)

    # Health
    @app.get("/ping")
    def ping():
        return jsonify({"app": "Friday", "ok": True, "status": "alive"})

    # S3 health endpoint (import inside so we test the same code path used at runtime)
    @app.get("/api/health/s3")
    def health_s3():
        try:
            from .backend.storage_s3 import presign_get_url  # relative import
        except Exception as e:
            return jsonify({"ok": False, "stage": "import", "error": str(e)}), 500

        missing = [k for k in ("AWS_ACCESS_KEY_ID","AWS_SECRET_ACCESS_KEY","AWS_DEFAULT_REGION","S3_BUCKET") if not os.getenv(k)]
        if missing:
            return jsonify({"ok": False, "stage": "env", "missing": missing}), 500

        try:
            bucket = os.getenv("S3_BUCKET")
            url = presign_get_url(f"s3://{bucket}/healthcheck/dummy.txt", 60)
            return jsonify({"ok": True, "sample": url[:120] + "..."})
        except Exception as e:
            return jsonify({"ok": False, "stage": "presign", "error": str(e)}), 500

    # Register RAG blueprint
    from .backend.rag_blueprint import bp as rag_bp  # relative import
    app.register_blueprint(rag_bp)

    return app

# export for wsgi
app = create_app()


















































































