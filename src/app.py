# app.py
import os
import json
from urllib.parse import urlparse

from flask import Flask, jsonify, request
from flask_cors import CORS
import boto3
from botocore.exceptions import ClientError, NoCredentialsError, EndpointConnectionError


def create_app() -> Flask:
    app = Flask(__name__)
    CORS(app)

    # ---- Config via environment variables ----
    AWS_REGION = os.getenv("AWS_REGION", "us-east-1")
    BUCKET_NAME = os.environ.get("S3_BUCKET")  # REQUIRED
    # Optional: If your environment already has an instance/profile role, you can
    # omit the explicit key/secret envs below.
    AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID")
    AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")
    AWS_SESSION_TOKEN = os.getenv("AWS_SESSION_TOKEN")  # optional

    if not BUCKET_NAME:
        raise RuntimeError("Missing required env var S3_BUCKET")

    # ---- AWS client ----
    boto_kwargs = {"region_name": AWS_REGION}
    if AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY:
        boto_kwargs.update(
            aws_access_key_id=AWS_ACCESS_KEY_ID,
            aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
            aws_session_token=AWS_SESSION_TOKEN,
        )

    s3 = boto3.client("s3", **boto_kwargs)

    # ---- Helpers ----
    def ok(data, status=200):
        return jsonify({"ok": True, **({"data": data} if not isinstance(data, dict) else data)}), status

    def fail(message, status=400, **extra):
        payload = {"ok": False, "error": str(message)}
        payload.update(extra)
        return jsonify(payload), status

    def s3_key_from_uri(s3_uri: str) -> tuple[str, str]:
        """
        Accepts 's3://bucket/key/...' and returns (bucket, key)
        """
        p = urlparse(s3_uri)
        if p.scheme != "s3" or not p.netloc or not p.path:
            raise ValueError("s3_uri must look like s3://bucket/key")
        return p.netloc, p.path.lstrip("/")

    # ---- Health ----
    @app.get("/api/health")
    def root_health():
        return ok({"status": "ok", "service": "backend"})

    @app.get("/api/rag/health")
    def rag_health():
        # Optionally test S3 access
        try:
            s3.list_buckets()
            s3_ok = True
        except Exception as e:
            s3_ok = False
        return ok({"status": "ok", "s3": s3_ok})

    # ---- 1) Presign upload URL ----
    @app.post("/api/rag/upload_url")
    def upload_url():
        try:
            body = request.get_json(force=True) or {}
            filename = body.get("filename") or "demo.txt"
            content_type = body.get("content_type") or "text/plain"

            # You can prepend a folder/prefix if you want:
            key = filename if not body.get("prefix") else f"{body['prefix'].rstrip('/')}/{filename}"

            put_url = s3.generate_presigned_url(
                ClientMethod="put_object",
                Params={
                    "Bucket": BUCKET_NAME,
                    "Key": key,
                    "ContentType": content_type,
                },
                ExpiresIn=3600,
            )

            return ok({
                "put_url": put_url,
                "s3_uri": f"s3://{BUCKET_NAME}/{key}",
                "content_type": content_type,
            })
        except (NoCredentialsError, EndpointConnectionError) as e:
            return fail("S3 credential/endpoint error", 500, detail=str(e))
        except Exception as e:
            return fail(e, 400)

    # ---- 2) Confirm / "index" the uploaded file ----
    @app.post("/api/rag/confirm_upload")
    def confirm_upload():
        """
        Body example:
        {
          "s3_uri": "s3://bucket/path/demo.txt",
          "title": "Demo file",
          "external_id": "demo_1",
          "metadata": {"collection": "default", "tags": ["test"], "source": "cli"},
          "chunk": {"size": 1200, "overlap": 150}
        }
        """
        try:
            body = request.get_json(force=True) or {}
            s3_uri = body.get("s3_uri")
            if not s3_uri:
                return fail("Missing 's3_uri'", 400)

            bucket, key = s3_key_from_uri(s3_uri)

            # Verify object exists
            try:
                head = s3.head_object(Bucket=bucket, Key=key)
            except ClientError as e:
                code = e.response.get("ResponseMetadata", {}).get("HTTPStatusCode")
                if code == 404:
                    return fail("S3 object not found; did you PUT the file bytes?", 404)
                raise

            # Here is where you'd trigger your real indexing pipeline.
            # For now we just echo back the request and file size.
            size = head.get("ContentLength")

            return ok({
                "indexed": True,
                "s3_uri": s3_uri,
                "bytes": size,
                "title": body.get("title"),
                "external_id": body.get("external_id"),
                "metadata": body.get("metadata"),
                "chunk": body.get("chunk"),
                "note": "This is a demo 'confirm/index' response. Plug in your actual indexer here."
            })
        except Exception as e:
            return fail(e, 400)

    # ---- 3) Optional: naive query stub (so your script doesn’t 404) ----
    @app.post("/api/rag/query")
    def rag_query():
        try:
            body = request.get_json(force=True) or {}
            q = body.get("q") or body.get("query") or ""
            return ok({
                "answer": f"(demo) You asked: {q!r}. The real RAG answerer isn’t wired yet.",
                "status": "stub"
            })
        except Exception as e:
            return fail(e, 400)

    # ---- Fallback OpenAPI/docs stubs (optional) ----
    @app.get("/openapi.json")
    def openapi_stub():
        return ok({"title": "Demo API", "version": "0.0.1", "paths": [
            "/api/health", "/api/rag/health", "/api/rag/upload_url",
            "/api/rag/confirm_upload", "/api/rag/query"
        ]})

    @app.get("/docs")
    def docs_stub():
        return ok({"message": "Add Swagger UI here if you want."})

    return app


if __name__ == "__main__":
    port = int(os.getenv("PORT", "8080"))
    app = create_app()
    # Render/Heroku-style: bind to 0.0.0.0
    app.run(host="0.0.0.0", port=port, debug=os.getenv("DEBUG", "false").lower() == "true")



















































































