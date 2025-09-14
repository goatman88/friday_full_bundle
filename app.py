# app.py
import os
import json
import datetime as dt
from urllib.parse import urlparse

from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS

# -----------------------
# Config & App
# -----------------------
APP_NAME = "Friday backend"
API_TOKEN = os.getenv("API_TOKEN", "").strip()
DATABASE_URL = os.getenv("DATABASE_URL", "").strip()  # e.g. postgres://... or empty for SQLite

app = Flask(__name__, static_folder="static")
CORS(app)

def need_auth() -> bool:
    return len(API_TOKEN) > 0

def check_auth() -> bool:
    if not need_auth():
        return True
    auth = request.headers.get("Authorization", "")
    return auth.startswith("Bearer ") and auth.split(" ", 1)[1] == API_TOKEN

def routes_list():
    rules = []
    for r in app.url_map.iter_rules():
        # Skip static converter noise
        rules.append(str(r))
    # stable order
    return sorted(rules)

# -----------------------
# Storage (Postgres or SQLite/FTS5)
# -----------------------
USE_POSTGRES = DATABASE_URL.startswith("postgres://") or DATABASE_URL.startswith("postgresql://")

if USE_POSTGRES:
    # Lazy import to avoid extra deps locally
    import psycopg2
    from psycopg2.extras import RealDictCursor

    def pg_conn():
        return psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)

    def init_db():
        with pg_conn() as conn, conn.cursor() as cur:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS documents (
                    id SERIAL PRIMARY KEY,
                    title TEXT NOT NULL,
                    source TEXT,
                    text  TEXT NOT NULL,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                );
                """
            )
            conn.commit()

    def index_doc(title: str, text: str, source: str = None):
        with pg_conn() as conn, conn.cursor() as cur:
            cur.execute(
                "INSERT INTO documents(title, source, text) VALUES (%s, %s, %s) RETURNING id;",
                (title, source, text),
            )
            new_id = cur.fetchone()["id"]
            conn.commit()
            return {"id": f"doc_{new_id}", "title": title}

    def search_docs(query: str, topk: int = 3):
        # Simple ILIKE match ordered by length of match/created_at
        q = f"%{query}%"
        with pg_conn() as conn, conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, title, source, text, created_at
                FROM documents
                WHERE title ILIKE %s OR text ILIKE %s
                ORDER BY created_at DESC
                LIMIT %s;
                """,
                (q, q, topk),
            )
            rows = cur.fetchall()
            contexts = []
            for r in rows:
                preview = r["text"][:180].replace("\n", " ")
                contexts.append({
                    "id": f"doc_{r['id']}",
                    "title": r["title"],
                    "source": r.get("source"),
                    "score": 0.5,   # placeholder score
                    "preview": preview
                })
            return contexts

else:
    # SQLite with FTS5
    import sqlite3
    SQLITE_PATH = os.getenv("SQLITE_PATH", "friday.db")

    def sq_conn():
        # Enable row factory for dict-ish access
        conn = sqlite3.connect(SQLITE_PATH, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    def init_db():
        with sq_conn() as conn:
            cur = conn.cursor()
            cur.execute("""
                CREATE TABLE IF NOT EXISTS documents (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    source TEXT,
                    text  TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
            """)
            # FTS virtual table mirrors docs for search
            cur.execute("""
                CREATE VIRTUAL TABLE IF NOT EXISTS documents_fts
                USING fts5(title, text, content='documents', content_rowid='id');
            """)
            # Triggers to keep FTS in sync
            cur.executescript("""
                CREATE TRIGGER IF NOT EXISTS documents_ai AFTER INSERT ON documents BEGIN
                    INSERT INTO documents_fts(rowid, title, text)
                    VALUES (new.id, new.title, new.text);
                END;
                CREATE TRIGGER IF NOT EXISTS documents_ad AFTER DELETE ON documents BEGIN
                    INSERT INTO documents_fts(documents_fts, rowid, title, text)
                    VALUES('delete', old.id, old.title, old.text);
                END;
                CREATE TRIGGER IF NOT EXISTS documents_au AFTER UPDATE ON documents BEGIN
                    INSERT INTO documents_fts(documents_fts, rowid, title, text)
                    VALUES('delete', old.id, old.title, old.text);
                    INSERT INTO documents_fts(rowid, title, text)
                    VALUES (new.id, new.title, new.text);
                END;
            """)
            conn.commit()

    def index_doc(title: str, text: str, source: str = None):
        now = dt.datetime.utcnow().isoformat()
        with sq_conn() as conn:
            cur = conn.cursor()
            cur.execute(
                "INSERT INTO documents(title, source, text, created_at) VALUES (?, ?, ?, ?)",
                (title, source, text, now),
            )
            new_id = cur.lastrowid
            conn.commit()
            return {"id": f"doc_{new_id}", "title": title}

    def search_docs(query: str, topk: int = 3):
        with sq_conn() as conn:
            cur = conn.cursor()
            # FTS5 match – we OR the terms; if it fails, fall back to LIKE
            try:
                cur.execute(
                    """
                    SELECT d.id, d.title, d.source, d.text
                    FROM documents_fts f
                    JOIN documents d ON d.id = f.rowid
                    WHERE documents_fts MATCH ?
                    LIMIT ?;
                    """,
                    (query, topk),
                )
            except sqlite3.OperationalError:
                like_q = f"%{query}%"
                cur.execute(
                    """
                    SELECT id, title, source, text
                    FROM documents
                    WHERE title LIKE ? OR text LIKE ?
                    ORDER BY created_at DESC
                    LIMIT ?;
                    """,
                    (like_q, like_q, topk),
                )
            rows = cur.fetchall()
            contexts = []
            for r in rows:
                preview = r["text"][:180].replace("\n", " ")
                contexts.append({
                    "id": f"doc_{r['id']}",
                    "title": r["title"],
                    "source": r["source"],
                    "score": 0.5,
                    "preview": preview
                })
            return contexts

# Prepare storage at import time (Render imports module once)
init_db()

# -----------------------
# Helper: auth guard
# -----------------------
def require_auth():
    if not check_auth():
        return jsonify({"ok": False, "error": "Unauthorized"}), 401
    return None

# -----------------------
# Routes
# -----------------------
@app.get("/")
def root_info():
    return jsonify({
        "message": f"{APP_NAME} is running",
        "ok": True,
        "routes": routes_list()
    }), 200

@app.get("/__routes")
def __routes():
    return jsonify(routes_list()), 200

@app.get("/__whoami")
def __whoami():
    return jsonify({
        "app_id": id(app),
        "cwd": os.getcwd(),
        "module_file": __file__,
        "python": os.popen("python -V").read().strip() or "unknown"
    }), 200

@app.get("/health")
def health():
    return jsonify({"ok": True, "status": "running"}), 200

@app.get("/ping")
def ping():
    return "pong", 200

@app.post("/api/rag/index")
def rag_index():
    if need_auth():
        guard = require_auth()
        if guard: return guard

    body = request.get_json(silent=True) or {}
    title = (body.get("title") or "").strip() or "Untitled"
    text  = (body.get("text") or "").strip()
    source = (body.get("source") or "").strip() or None
    if not text:
        return jsonify({"ok": False, "error": "text is required"}), 400

    doc = index_doc(title=title, text=text, source=source)
    return jsonify({"ok": True, "indexed": [doc]}), 200

@app.post("/api/rag/query")
def rag_query():
    if need_auth():
        guard = require_auth()
        if guard: return guard

    body = request.get_json(silent=True) or {}
    query = (body.get("query") or "").strip()
    topk = int(body.get("topk") or body.get("k") or 3)
    topk = max(1, min(topk, 10))

    if not query:
        return jsonify({"ok": False, "error": "query is required"}), 400

    contexts = search_docs(query=query, topk=topk)

    # super simple answer heuristic
    answer = contexts[0]["preview"] if contexts else "No matches."
    return jsonify({"ok": True, "answer": answer, "contexts": contexts}), 200

@app.get("/static/<path:filename>")
def serve_static(filename):
    return send_from_directory(app.static_folder, filename)

# -----------------------
# WSGI entrypoint
# -----------------------
# Render's Start Command typically points to "app:app"
# When running locally: `python app.py`
if __name__ == "__main__":
    port = int(os.getenv("PORT", "5000"))
    app.run(host="0.0.0.0", port=port, debug=False)

























































