import os
from flask import Flask, request, jsonify
from flask_cors import CORS
import psycopg
import openai

# --- Flask setup ---
app = Flask(__name__)
CORS(app)

openai.api_key = os.getenv("OPENAI_API_KEY")

# --- Postgres connection ---
DB_URL = os.getenv("DATABASE_URL")  # Render Postgres add-on sets this automatically
conn = psycopg.connect(DB_URL, autocommit=True)

# Ensure vector table exists
with conn.cursor() as cur:
    cur.execute("""
        CREATE TABLE IF NOT EXISTS documents (
            id SERIAL PRIMARY KEY,
            title TEXT,
            content TEXT,
            embedding VECTOR(1536)
        );
    """)

# --- Healthcheck ---
@app.route("/health")
def health():
    return jsonify({"ok": True, "status": "running"})

# --- RAG: Index ---
@app.route("/api/rag/index", methods=["POST"])
def rag_index():
    data = request.get_json()
    text = data.get("text", "")
    title = data.get("title", "Untitled")

    # Get embedding from OpenAI
    emb = openai.embeddings.create(
        model="text-embedding-3-small",
        input=text
    )["data"][0]["embedding"]

    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO documents (title, content, embedding) VALUES (%s, %s, %s)",
            (title, text, emb)
        )

    return jsonify({"ok": True, "indexed": {"title": title}})

# --- RAG: Query ---
@app.route("/api/rag/query", methods=["POST"])
def rag_query():
    data = request.get_json()
    query = data.get("query", "")
    topk = int(data.get("topk", 3))

    qemb = openai.embeddings.create(
        model="text-embedding-3-small",
        input=query
    )["data"][0]["embedding"]

    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT title, content, embedding <#> %s AS score
            FROM documents
            ORDER BY score ASC
            LIMIT %s;
            """,
            (qemb, topk)
        )
        rows = cur.fetchall()

    return jsonify({
        "ok": True,
        "answers": [{"title": r[0], "content": r[1], "score": float(r[2])} for r in rows]
    })

# --- Root ---
@app.route("/")
def root():
    return jsonify({"message": "Friday AI is live 🚀"})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)))




























































