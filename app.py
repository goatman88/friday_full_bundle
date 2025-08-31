# app.py
import os, io, json, time, math, secrets, hashlib, mimetypes, uuid, zipfile, csv
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple

# --- Load .env locally (non-prod) ---
try:
    from dotenv import load_dotenv
    if os.getenv("FLASK_ENV", "").lower() != "production":
        load_dotenv(override=False)
except Exception:
    pass

from flask import (
    Flask, jsonify, request, send_from_directory,
    Response, stream_with_context
)
from flask_cors import CORS

# ---------- Sentry (optional) ----------
SENTRY_DSN = os.getenv("SENTRY_DSN", "")
try:
    if SENTRY_DSN:
        import sentry_sdk
        from sentry_sdk.integrations.flask import FlaskIntegration
        sentry_sdk.init(
            dsn=SENTRY_DSN,
            integrations=[FlaskIntegration()],
            traces_sample_rate=float(os.getenv("SENTRY_TRACES_SAMPLE_RATE", "0.05")),
            environment=os.getenv("ENVIRONMENT", os.getenv("FLASK_ENV", "development")),
            release=os.getenv("RENDER_GIT_COMMIT", "")[:7] or os.getenv("COMMIT", "")
        )
except Exception:
    pass

# ---------- Flask ----------
app = Flask(__name__, static_folder="static", template_folder="templates")
CORS(app, resources={r"/*": {"origins": [o.strip() for o in os.getenv("CORS_ALLOW_ORIGINS", "*").split(",")]}})

COMMIT = (os.getenv("RENDER_GIT_COMMIT", "")[:7] or os.getenv("COMMIT", "") or "dev")
OPENAI_KEY = os.getenv("OPENAI_API_KEY", "")
DEFAULT_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
SYSTEM_PROMPT = os.getenv("PROMPT_SYSTEM", "You are Friday AI: quick, accurate, actionable.")
EMBED_MODEL = os.getenv("EMBED_MODEL", "text-embedding-3-small")
EMBED_DIM = int(os.getenv("EMBED_DIM", "1536"))  # small=1536; large=3072

# ---------- Auth / JWT ----------
ACCESS_TTL_MIN = int(os.getenv("ACCESS_TTL_MIN", "15"))
REFRESH_TTL_DAYS = int(os.getenv("REFRESH_TTL_DAYS", "14"))
JWT_SECRET = os.getenv("JWT_SECRET", "dev-secret-change-me")
APP_LOGIN_PASSWORD = os.getenv("APP_LOGIN_PASSWORD", "")
ADMIN_TOKEN = os.getenv("ADMIN_TOKEN", "")

# ---------- Rate limit ----------
RL_WINDOW = int(os.getenv("RATE_LIMIT_WINDOW_SECONDS", "60"))
RL_MAX = int(os.getenv("RATE_LIMIT_MAX", "60"))

# ---------- Upload limits (role-based) ----------
UPLOAD_MAX_MB_USER = int(os.getenv("UPLOAD_MAX_MB_USER", "20"))
UPLOAD_MAX_MB_ADMIN = int(os.getenv("UPLOAD_MAX_MB_ADMIN", "50"))
app.config["MAX_CONTENT_LENGTH"] = int(os.getenv("MAX_CONTENT_LENGTH_BYTES", str(60*1024*1024)))

# ---------- Pricing ----------
PRICES = {
    "gpt-4o":        {"in": 0.0025, "out": 0.0100},
    "gpt-4o-mini":   {"in": 0.0005, "out": 0.0015},
    "gpt-4.1-mini":  {"in": 0.0006, "out": 0.0018},
    "o3-mini":       {"in": 0.0005, "out": 0.0015},
}

# ---------- Redis (history, rate limit, cache) ----------
r = None
try:
    REDIS_URL = os.getenv("REDIS_URL", "")
    if REDIS_URL:
        import redis
        r = redis.from_url(REDIS_URL, decode_responses=True)
except Exception:
    r = None

def redis_ok() -> bool:
    if not r: return False
    try: r.ping(); return True
    except Exception: return False

# ---------- PGVector (optional fallback) ----------
pg = None
pg_cosine_ok = None
def _connect_pg():
    global pg, pg_cosine_ok
    PG_URL = os.getenv("PG_URL", "")
    if not PG_URL: return None
    try:
        import psycopg
        from pgvector.psycopg import register_vector
        pg = psycopg.connect(PG_URL, autocommit=True)
        register_vector(pg)
        with pg.cursor() as cur:
            cur.execute("CREATE EXTENSION IF NOT EXISTS vector;")
            cur.execute(f"""
                CREATE TABLE IF NOT EXISTS rag_chunks (
                    id UUID PRIMARY KEY,
                    username TEXT NOT NULL,
                    text TEXT NOT NULL,
                    metadata JSONB DEFAULT '{{}}',
                    embedding vector({EMBED_DIM})
                );
            """)
            try:
                cur.execute("CREATE INDEX IF NOT EXISTS idx_rag_chunks_text ON rag_chunks USING GIN (to_tsvector('english', text));")
            except Exception:
                pass
            try:
                cur.execute(f"CREATE INDEX IF NOT EXISTS idx_rag_chunks_embedding_cos ON rag_chunks USING ivfflat (embedding vector_cosine_ops) WITH (lists=100);")
                pg_cosine_ok = True
            except Exception:
                pg_cosine_ok = False
                try:
                    cur.execute(f"CREATE INDEX IF NOT EXISTS idx_rag_chunks_embedding_l2 ON rag_chunks USING ivfflat (embedding vector_l2_ops) WITH (lists=100);")
                except Exception:
                    pass
            cur.execute("CREATE INDEX IF NOT EXISTS idx_rag_chunks_user ON rag_chunks (username);")
        return pg
    except Exception as e:
        print("PG init failed:", e)
        pg = None
        return None

# ---------- Qdrant (preferred) ----------
qdrant = None
QDRANT_COLLECTION = os.getenv("QDRANT_COLLECTION", "rag_chunks")
def _connect_qdrant():
    global qdrant
    QDRANT_URL = os.getenv("QDRANT_URL", "")
    if not QDRANT_URL: return None
    try:
        from qdrant_client import QdrantClient
        from qdrant_client.models import Distance, VectorParams
        qdrant = QdrantClient(
            url=QDRANT_URL,
            api_key=os.getenv("QDRANT_API_KEY", None),
            timeout=10
        )
        try:
            qdrant.get_collection(QDRANT_COLLECTION)
        except Exception:
            qdrant.recreate_collection(
                collection_name=QDRANT_COLLECTION,
                vectors_config=VectorParams(size=EMBED_DIM, distance=Distance.COSINE),
            )
        return qdrant
    except Exception as e:
        print("Qdrant init failed:", e)
        qdrant = None
        return None

# init vector backends
_connect_qdrant()
if not qdrant:
    _connect_pg()

# ---------- Keys & helpers ----------
def k_history(u: str) -> str: return f"hist:{u}"
def k_model_active() -> str: return "model:active"
def k_user_model(u: str) -> str: return f"user:{u}:model"
def k_admin_code(code: str) -> str: return f"admin:code:{code}"
def k_rl(scope: str) -> str: return f"rl:{scope}"
def k_cache(prefix: str, key: str) -> str: return f"cache:{prefix}:{key}"

def active_model(username: Optional[str] = None) -> str:
    if r:
        if username:
            m = r.get(k_user_model(username))
            if m: return m
        m = r.get(k_model_active())
        if m: return m
    return DEFAULT_MODEL

def set_active_model(model: str, username: Optional[str] = None) -> str:
    if r:
        if username:
            r.set(k_user_model(username), model, ex=60*60*24*30)
        else:
            r.set(k_model_active(), model)
    global DEFAULT_MODEL
    DEFAULT_MODEL = model
    return model

def append_history(username: str, message: str, reply: str) -> None:
    if not r: return
    r.rpush(k_history(username), json.dumps({"ts": time.time(), "message": message, "reply": reply}))
    r.ltrim(k_history(username), -500, -1)

def get_history(username: str, limit: int = 200) -> List[Dict[str, Any]]:
    if not r: return []
    entries = r.lrange(k_history(username), max(-limit, -500), -1)
    out = []
    for raw in entries:
        try: out.append(json.loads(raw))
        except Exception: pass
    return out

def clear_history(username: str) -> int:
    if not r: return 0
    return r.delete(k_history(username)) or 0

def client_scope() -> str:
    uname = request.args.get("username") or ((request.json or {}).get("username") if request.is_json else None)
    if uname: return f"user:{uname}"
    fwd = request.headers.get("X-Forwarded-For", "") or request.remote_addr or "unknown"
    return f"ip:{(fwd.split(',')[0] or 'unknown').strip()}"

def rate_limit_check(scope: str) -> Tuple[bool,int,int]:
    if not r: return (True, RL_MAX, int(time.time()) + RL_WINDOW)
    key = k_rl(scope)
    try:
        cur = r.incr(key)
        ttl = r.ttl(key)
        if ttl < 0:
            r.expire(key, RL_WINDOW)
            ttl = RL_WINDOW
        return (cur <= RL_MAX, max(0, RL_MAX - cur), int(time.time()) + ttl)
    except Exception:
        return (True, RL_MAX, int(time.time()) + RL_WINDOW)

# ---------- JWT helpers ----------
def _jwt_encode(payload: Dict[str, Any]) -> str:
    import jwt
    return jwt.encode(payload, JWT_SECRET, algorithm="HS256")

def make_access(username: str, role: str = "user") -> str:
    return _jwt_encode({"sub": username, "role": role, "typ": "access", "iat": int(time.time()), "exp": int(time.time() + ACCESS_TTL_MIN*60)})

def make_refresh(username: str, role: str = "user") -> str:
    return _jwt_encode({"sub": username, "role": role, "typ": "refresh", "iat": int(time.time()), "exp": int(time.time() + REFRESH_TTL_DAYS*24*3600)})

def decode_jwt_from_header() -> Optional[Dict[str, Any]]:
    import jwt
    auth = request.headers.get("Authorization","")
    if not auth.startswith("Bearer "): return None
    token = auth.split(" ",1)[1].strip()
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
    except Exception:
        return None

def require_access(role: Optional[str] = None) -> Optional[Dict[str, Any]]:
    data = decode_jwt_from_header()
    if not data or data.get("typ") != "access": return None
    if role and data.get("role") != role: return None
    return data

# ---------- OpenAI ----------
def price_estimate(model: str, p_tok: int, c_tok: int) -> float:
    p = PRICES.get(model, PRICES.get("gpt-4o-mini"))
    return (p_tok/1000.0)*p["in"] + (c_tok/1000.0)*p["out"]

def embed_texts(texts: List[str], model: Optional[str] = None) -> List[List[float]]:
    """Embed texts with selected model (default EMBED_MODEL)."""
    model = model or EMBED_MODEL
    if not OPENAI_KEY:
        # dev fallback hash-vector
        def cheap_vec(s: str, dim=64):
            v = [0.0]*dim
            for i,ch in enumerate(s.encode("utf-8")):
                v[i % dim] += (ch % 13) / 13.0
            n = math.sqrt(sum(x*x for x in v)) or 1.0
            return [x/n for x in v]
        return [cheap_vec(t) for t in texts]
    from openai import OpenAI
    client = OpenAI(api_key=OPENAI_KEY)
    res = client.embeddings.create(model=model, input=texts)
    return [d.embedding for d in res.data]

def moderate_text(text: str) -> Dict[str, Any]:
    if not OPENAI_KEY:
        return {"ok": True}
    try:
        from openai import OpenAI
        client = OpenAI(api_key=OPENAI_KEY)
        m = client.moderations.create(model="omni-moderation-latest", input=text)
        flagged = False
        try: flagged = bool(m.results[0].flagged)
        except Exception: pass
        return {"ok": not flagged}
    except Exception as e:
        return {"ok": True, "note": f"moderation_error:{e}"}

# ---------- Tools ----------
def http_get(url: str, params: Dict[str, Any], timeout=8, tries=3, backoff=0.5):
    import requests
    last = None
    for i in range(tries):
        try:
            res = requests.get(url, params=params, timeout=timeout)
            if res.status_code >= 500: raise Exception(f"{res.status_code}")
            return res
        except Exception as e:
            last = e; time.sleep(backoff*(2**i))
    raise last or RuntimeError("http_get failed")

def cache_get(prefix: str, key: str):
    if not r: return None
    return r.get(k_cache(prefix, key))

def cache_set(prefix: str, key: str, value: Any, ttl: int = 300):
    if not r: return
    r.setex(k_cache(prefix, key), ttl, json.dumps(value))

def tool_weather(city: str) -> Dict[str, Any]:
    if not city: return {"ok": False, "reason":"missing_city"}
    h = hashlib.sha256(city.strip().lower().encode()).hexdigest()
    c = cache_get("wx", h)
    if c:
        try: return json.loads(c)
        except Exception: pass
    try:
        g = http_get("https://geocoding-api.open-meteo.com/v1/search", {"name": city, "count": 1})
        gd = g.json()
        if not gd.get("results"): return {"ok": False, "reason": "not_found"}
        lat = gd["results"][0]["latitude"]; lon = gd["results"][0]["longitude"]
        name = gd["results"][0]["name"]; country = gd["results"][0].get("country","")
        w = http_get("https://api.open-meteo.com/v1/forecast", {"latitude": lat, "longitude": lon, "current_weather": "true"})
        cw = (w.json() or {}).get("current_weather") or {}
        out = {"ok": True, "city": f"{name}, {country}".strip(", "), "temperature_c": cw.get("temperature"), "windspeed_kmh": cw.get("windspeed")}
        cache_set("wx", h, out, 180)
        return out
    except Exception as e:
        return {"ok": False, "reason": str(e)}

def tool_sysinfo() -> Dict[str, Any]:
    return {"ok": True, "commit": COMMIT, "redis": redis_ok(), "pg": bool(pg), "qdrant": bool(qdrant), "model": active_model()}

def tool_web(query: str) -> Dict[str, Any]:
    if not query: return {"ok": False, "reason":"missing_query"}
    h = hashlib.sha256(query.strip().lower().encode()).hexdigest()
    c = cache_get("ddg", h)
    if c:
        try: return json.loads(c)
        except Exception: pass
    try:
        res = http_get("https://api.duckduckgo.com/", {"q": query, "format": "json", "no_html": 1, "skip_disambig": 1})
        data = res.json()
        out = {"ok": True, "heading": data.get("Heading"), "summary": data.get("AbstractText"), "related": [
            {"Text": t.get("Text"), "FirstURL": t.get("FirstURL")}
            for t in (data.get("RelatedTopics") or []) if isinstance(t, dict)
        ][:5]}
        cache_set("ddg", h, out, 300)
        return out
    except Exception as e:
        return {"ok": False, "reason": str(e)}

# ---------- RAG backend routing ----------
def rag_backend() -> str:
    if qdrant: return "qdrant"
    if pg: return "pgvector"
    if r: return "redis"
    return "none"

# ---------- RAG index/search ----------
def rag_index(username: str, docs: List[Dict[str, Any]]) -> Dict[str, Any]:
    vecs = embed_texts([d.get("text","") for d in docs])
    # sanity check dimension (if using real embeddings)
    if vecs and OPENAI_KEY and len(vecs[0]) != EMBED_DIM:
        return {"ok": False, "reason": f"embedding_dim_mismatch expected {EMBED_DIM}, got {len(vecs[0])}"}
    for d, v in zip(docs, vecs):
        d["vec"] = v

    backend = rag_backend()
    if backend == "qdrant":
        try:
            from qdrant_client.models import PointStruct
            pts = [PointStruct(id=str(uuid.uuid4()), vector=d["vec"], payload={"username": username, "text": d["text"], "metadata": d.get("metadata", {})}) for d in docs]
            qdrant.upsert(collection_name=QDRANT_COLLECTION, points=pts, wait=True)
            return {"ok": True, "count": len(pts), "backend": "qdrant"}
        except Exception as e:
            return {"ok": False, "reason": f"qdrant_upsert_failed:{e}"}

    if backend == "pgvector":
        try:
            from pgvector.psycopg import Vector
            import psycopg
            from psycopg.types.json import Json
            inserted = 0
            with pg.cursor() as cur:
                for d in docs:
                    try:
                        cur.execute(
                            "INSERT INTO rag_chunks (id, username, text, metadata, embedding) VALUES (%s,%s,%s,%s,%s) "
                            "ON CONFLICT (id) DO NOTHING;",
                            (uuid.uuid4(), username, d["text"], Json(d.get("metadata") or {}), Vector(d["vec"]))
                        )
                        inserted += 1
                    except Exception:
                        pass
            return {"ok": True, "count": inserted, "backend": "pgvector"}
        except Exception as e:
            return {"ok": False, "reason": f"pgvector_upsert_failed:{e}"}

    if backend == "redis":
        key = f"rag:{username}:docs"
        pipe = r.pipeline()
        for d in docs:
            row = {"id": d.get("id") or secrets.token_urlsafe(6), "text": d.get("text",""), "meta": d.get("metadata", {}), "vec": d["vec"]}
            pipe.rpush(key, json.dumps(row))
        pipe.execute()
        r.ltrim(key, -2000, -1)
        return {"ok": True, "count": len(docs), "backend": "redis"}

    return {"ok": False, "reason":"no_vector_backend"}

def cosine(a: List[float], b: List[float]) -> float:
    s = sum(x*y for x,y in zip(a,b))
    na = math.sqrt(sum(x*x for x in a)) or 1.0
    nb = math.sqrt(sum(x*x for x in b)) or 1.0
    return s/(na*nb)

def rag_search(username: str, query: str, top_k: int = 4) -> Dict[str, Any]:
    qvec = embed_texts([query])[0]
    if qvec and OPENAI_KEY and len(qvec) != EMBED_DIM:
        return {"ok": False, "reason": f"embedding_dim_mismatch expected {EMBED_DIM}, got {len(qvec)}"}
    backend = rag_backend()

    if backend == "qdrant":
        try:
            from qdrant_client.models import Filter, FieldCondition, MatchValue
            flt = Filter(must=[FieldCondition(key="username", match=MatchValue(value=username))])
            res = qdrant.search(
                collection_name=QDRANT_COLLECTION,
                query_vector=qvec,
                limit=top_k,
                query_filter=flt,
                with_payload=True,
            )
            matches = []
            for p in res:
                pl = p.payload or {}
                matches.append({
                    "id": str(p.id),
                    "text": pl.get("text",""),
                    "metadata": pl.get("metadata", {}),
                    "score": round(float(p.score or 0), 4)
                })
            return {"ok": True, "matches": matches, "backend": "qdrant"}
        except Exception as e:
            return {"ok": False, "reason": f"qdrant_search_failed:{e}"}

    if backend == "pgvector":
        try:
            from pgvector.psycopg import Vector
            rows=[]
            with pg.cursor() as cur:
                if pg_cosine_ok:
                    cur.execute(
                        "SELECT id, text, metadata, 1 - (embedding <=> %s) AS score "
                        "FROM rag_chunks WHERE username=%s ORDER BY embedding <=> %s LIMIT %s;",
                        (Vector(qvec), username, Vector(qvec), top_k)
                    )
                else:
                    cur.execute(
                        "SELECT id, text, metadata, (1.0 / (1.0 + (embedding <-> %s))) AS score "
                        "FROM rag_chunks WHERE username=%s ORDER BY embedding <-> %s LIMIT %s;",
                        (Vector(qvec), username, Vector(qvec), top_k)
                    )
                for rid, t, meta, score in cur.fetchall():
                    rows.append({"id": str(rid), "text": t or "", "metadata": meta or {}, "score": round(float(score or 0), 4)})
            return {"ok": True, "matches": rows, "backend": "pgvector"}
        except Exception as e:
            return {"ok": False, "reason": f"pgvector_search_failed:{e}"}

    if backend == "redis":
        items = r.lrange(f"rag:{username}:docs", 0, -1)
        scored = []
        for raw in items:
            try:
                row = json.loads(raw)
                sc = cosine(qvec, row.get("vec") or [])
                scored.append((sc, row))
            except Exception:
                pass
        scored.sort(key=lambda t: t[0], reverse=True)
        out = [{"score": round(s,4), "id": r0["id"], "text": r0["text"], "metadata": r0.get("meta", {})} for s, r0 in scored[:top_k]]
        return {"ok": True, "matches": out, "backend":"redis"}

    return {"ok": False, "reason":"no_vector_backend"}

# ---------- OpenAI tool loop ----------
OPENAI_TOOLS = [
    {"type":"function","function":{"name":"get_weather","description":"Get current weather for a city.","parameters":{"type":"object","properties":{"city":{"type":"string"}},"required":["city"]}}},
    {"type":"function","function":{"name":"web_search","description":"DuckDuckGo instant answer quick lookup","parameters":{"type":"object","properties":{"query":{"type":"string"}},"required":["query"]}}},
    {"type":"function","function":{"name":"system_info","description":"Server/model status","parameters":{"type":"object","properties":{}}}},
    {"type":"function","function":{"name":"rag_search","description":"Search user’s indexed docs for grounding","parameters":{"type":"object","properties":{"username":{"type":"string"},"query":{"type":"string"},"top_k":{"type":"integer","minimum":1,"maximum":10}},"required":["username","query"]}}}
]

def tool_loop(model: str, user_msg: str, username: str, max_hops=6) -> Dict[str, Any]:
    pre = moderate_text(user_msg)
    if not pre.get("ok", True):
        return {"reply":"I can’t help with that request.", "traces":[{"tool":"moderation","result":pre}]}

    if not OPENAI_KEY:
        traces=[]
        l = user_msg.lower()
        if "weather" in l:
            city = user_msg.split()[-1]
            out = tool_weather(city); traces.append({"tool":"get_weather","args":{"city":city},"result":out})
            return {"reply": f"Temp in {out.get('city','?')}: {out.get('temperature_c','?')}°C", "traces":traces}
        if "search" in l:
            out = tool_web(user_msg); traces.append({"tool":"web_search","args":{"query":user_msg},"result":out})
            return {"reply": out.get("summary") or out.get("heading") or "(no result)", "traces":traces}
        if "doc" in l or "rag" in l:
            out = rag_search(username, user_msg, 4); traces.append({"tool":"rag_search","result":out})
            return {"reply": f"Top matches: {len(out.get('matches',[]))}", "traces":traces}
        return {"reply": f"(dev echo) {user_msg}", "traces":[]}

    from openai import OpenAI
    client = OpenAI(api_key=OPENAI_KEY)
    messages = [{"role":"system","content":SYSTEM_PROMPT},{"role":"user","content": user_msg}]
    traces=[]; pt=0; ct=0

    for _ in range(max_hops):
        r0 = client.chat.completions.create(model=model, messages=messages, tools=OPENAI_TOOLS, tool_choice="auto", temperature=0.4)
        u = getattr(r0, "usage", None)
        if u:
            pt += int(getattr(u,"prompt_tokens",0)); ct += int(getattr(u,"completion_tokens",0))
        msg = r0.choices[0].message
        if not getattr(msg, "tool_calls", None):
            text = (msg.content or "").strip() or "(no reply)"
            cost = price_estimate(model, pt, ct)
            return {"reply": text, "traces": traces, "usage":{"prompt_tokens":pt,"completion_tokens":ct,"est_cost_usd": round(cost,6)}}

        for tc in msg.tool_calls:
            name = tc.function.name
            args = json.loads(tc.function.arguments or "{}")
            if name == "get_weather":   res = tool_weather(args.get("city",""))
            elif name == "web_search":  res = tool_web(args.get("query",""))
            elif name == "system_info": res = tool_sysinfo()
            elif name == "rag_search":  res = rag_search(args.get("username") or username, args.get("query",""), int(args.get("top_k") or 4))
            else: res = {"ok": False, "reason": f"unknown_tool:{name}"}
            traces.append({"tool":name,"args":args,"result":res})
            messages.append({"role":"assistant","tool_calls":[tc]})
            messages.append({"role":"tool","tool_call_id": tc.id, "name": name, "content": json.dumps(res)})

    return {"reply":"Planner hit hop limit. Try again with a simpler ask.", "traces":traces}

# ---------- Ingestion helpers ----------
from werkzeug.utils import secure_filename
ALLOWED_EXT = {".txt", ".md", ".pdf", ".docx", ".html", ".htm"}

ENABLE_OCR = os.getenv("ENABLE_OCR", "true").lower() == "true"
OCR_LANGS = os.getenv("OCR_LANGS", "eng")
_tesseract_ready = None

def _ocr_ready() -> bool:
    global _tesseract_ready
    if _tesseract_ready is not None:
        return _tesseract_ready
    if not ENABLE_OCR:
        _tesseract_ready = False
        return False
    try:
        import pytesseract
        from PIL import Image  # noqa
        _ = pytesseract.get_tesseract_version()
        _tesseract_ready = True
        return True
    except Exception:
        _tesseract_ready = False
        return False

def _chunk_text(text: str, size=900, overlap=250) -> List[str]:
    text = (text or "").strip()
    if not text: return []
    out=[]; i=0
    while i < len(text):
        out.append(text[i:i+size])
        i += max(1, size-overlap)
    return out

def _read_pdf(data: bytes) -> str:
    try:
        import PyPDF2
        reader = PyPDF2.PdfReader(io.BytesIO(data))
        parts=[]
        for p in reader.pages:
            try: parts.append(p.extract_text() or "")
            except Exception: pass
        return "\n".join(parts).strip()
    except Exception:
        return ""

def _read_docx_text(data: bytes) -> str:
    try:
        from docx import Document
        doc = Document(io.BytesIO(data))
        return "\n".join([p.text for p in doc.paragraphs]).strip()
    except Exception:
        return ""

def _read_docx_image_ocr(data: bytes) -> str:
    if not _ocr_ready():
        return ""
    try:
        import pytesseract
        from PIL import Image
        text_parts=[]
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            for name in z.namelist():
                if name.startswith("word/media/") and name.lower().split(".")[-1] in {"png","jpg","jpeg","bmp","tif","tiff"}:
                    img_bytes = z.read(name)
                    try:
                        img = Image.open(io.BytesIO(img_bytes))
                        txt = pytesseract.image_to_string(img, lang=OCR_LANGS)
                        if txt and txt.strip():
                            text_parts.append(txt.strip())
                    except Exception:
                        pass
        return "\n".join(text_parts).strip()
    except Exception:
        return ""

def _read_html(data: bytes) -> str:
    try:
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(data, "html.parser")
        for t in soup(["script","style","noscript"]): t.extract()
        return soup.get_text("\n").strip()
    except Exception:
        return ""

# ---------- PAGES ----------
@app.get("/")
def home():
    return send_from_directory(app.static_folder, "chat.html")

@app.get("/chat")
def chat_page():
    return send_from_directory(app.static_folder, "chat.html")

@app.get("/admin")
def admin_page():
    return send_from_directory(app.static_folder, "admin.html")

@app.get("/vectors")
def vectors_page():
    return send_from_directory(app.static_folder, "vectors.html")

@app.get("/maint")
def maint_page():
    return send_from_directory(app.static_folder, "maint.html")

# ---------- DIAGNOSTICS ----------
@app.get("/routes")
def routes():
    out=[]
    for rule in app.url_map.iter_rules():
        out.append({"endpoint": rule.endpoint, "methods": sorted(m for m in rule.methods if m in {"GET","POST","OPTIONS"}), "rule": str(rule)})
    return jsonify(sorted(out, key=lambda r: r["rule"]))

@app.get("/debug/health")
def health():
    return jsonify({"ok": True, "commit": COMMIT, "redis": redis_ok(), "pg": bool(pg), "qdrant": bool(qdrant), "model": active_model(), "openai": bool(OPENAI_KEY)})

@app.get("/api/metrics")
def metrics():
    scope = client_scope()
    allowed, remaining, reset = rate_limit_check(scope)
    return jsonify({"rate_limit":{"allowed":allowed,"remaining":remaining,"reset":reset},"model": active_model(),"pg": bool(pg), "qdrant": bool(qdrant)})

# ---------- AUTH ----------
@app.post("/api/auth/login")
def auth_login():
    body = request.get_json(silent=True) or {}
    username = (body.get("username") or "guest").strip() or "guest"
    password = body.get("password") or ""
    admin_code = (body.get("admin_code") or "").strip()
    if APP_LOGIN_PASSWORD and password != APP_LOGIN_PASSWORD:
        return jsonify({"error":"invalid_password"}), 401
    role = "admin" if (ADMIN_TOKEN and admin_code == ADMIN_TOKEN) else "user"
    return jsonify({"access_token": make_access(username, role), "refresh_token": make_refresh(username, role), "user":{"username": username, "role": role}})

@app.post("/api/auth/refresh")
def auth_refresh():
    body = request.get_json(silent=True) or {}
    token = (body.get("refresh_token") or "").strip()
    if not token:
        auth = request.headers.get("Authorization","")
        if auth.startswith("Bearer "): token = auth.split(" ",1)[1]
    if not token: return jsonify({"error":"missing_refresh_token"}), 400
    import jwt
    try:
        data = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
        if data.get("typ") != "refresh": raise Exception("wrong_token_type")
        username = data.get("sub") or "guest"
        role = data.get("role") or "user"
        return jsonify({"access_token": make_access(username, role), "user":{"username":username,"role":role}})
    except Exception as e:
        return jsonify({"error":"invalid_refresh","detail": str(e)}), 401

# ---------- MODELS ----------
@app.get("/api/models")
def list_models():
    return jsonify({"active": active_model(request.args.get("username") or "guest"), "available": ["gpt-4o","gpt-4o-mini","gpt-4.1-mini","o3-mini"]})

@app.post("/api/model")
def set_model_api():
    allowed, _, _ = rate_limit_check(client_scope())
    if not allowed: return jsonify({"error":"rate_limited"}), 429
    model = (request.get_json(silent=True) or {}).get("model","").strip()
    if not model: return jsonify({"error":"missing_model"}), 400
    set_active_model(model)
    return jsonify({"active": active_model()})

# ---------- CHAT (JSON) ----------
@app.post("/api/chat")
def api_chat():
    allowed, remaining, reset = rate_limit_check(client_scope())
    if not allowed:
        return jsonify({"error":"rate_limited","retry_after": reset - int(time.time())}), 429
    data = request.get_json(force=True) or {}
    msg = (data.get("message") or "").strip()
    username = (data.get("username") or "guest").strip() or "guest"
    model = (data.get("model") or active_model(username)).strip()
    if not msg: return jsonify({"error":"missing_message"}), 400
    out = tool_loop(model, msg, username, max_hops=6)
    append_history(username, msg, out.get("reply",""))
    return jsonify({**out, "rate_limit":{"remaining":remaining,"reset":reset}})

# ---------- STREAM: text-only ----------
def sse_line(obj: Dict[str,Any]) -> str: return f"data: {json.dumps(obj, ensure_ascii=False)}\n\n"

@app.get("/api/chat/stream")
def api_chat_stream():
    message = (request.args.get("message") or "").strip()
    username = request.args.get("username") or "guest"
    model = request.args.get("model") or active_model(username)
    if not message: return jsonify({"error":"missing_message"}), 400

    def generate():
        final=[]
        if not OPENAI_KEY:
            demo=f"(dev echo) {message}"
            for ch in demo: final.append(ch); yield sse_line({"type":"delta","delta": ch}); time.sleep(0.01)
            yield sse_line({"type":"done"}); append_history(username, message, "".join(final)); return
        from openai import OpenAI
        client = OpenAI(api_key=OPENAI_KEY)
        stream = client.chat.completions.create(
            model=model,
            messages=[{"role":"system","content":SYSTEM_PROMPT},{"role":"user","content": message}],
            temperature=0.6, stream=True
        )
        for chunk in stream:
            part = ""
            try: part = chunk.choices[0].delta.content or ""
            except Exception: part = ""
            if part:
                final.append(part)
                yield sse_line({"type":"delta","delta": part})
        yield sse_line({"type":"done"})
        append_history(username, message, "".join(final))
    return Response(stream_with_context(generate()), headers={"Content-Type":"text/event-stream","Cache-Control":"no-cache","Connection":"keep-alive","X-Accel-Buffering":"no"})

# ---------- STREAM: tools + tokens ----------
@app.get("/api/chat/stream_tools")
def api_chat_stream_tools():
    """Streams token deltas *and* emits events for tool calls/results."""
    message = (request.args.get("message") or "").strip()
    username = request.args.get("username") or "guest"
    model = request.args.get("model") or active_model(username)
    if not message: return jsonify({"error":"missing_message"}), 400

    def generate():
        out = tool_loop(model, message, username, max_hops=6)
        traces = out.get("traces", [])
        # tool events first
        for t in traces:
            yield sse_line({"type":"tool_event","tool": t.get("tool"), "args": t.get("args"), "result": t.get("result")})
        # then stream text
        reply = (out.get("reply") or "").strip() or "(no reply)"
        for ch in reply:
            yield sse_line({"type":"delta","delta": ch}); time.sleep(0.005)
        if out.get("usage"): yield sse_line({"type":"usage","usage": out["usage"]})
        yield sse_line({"type":"done"})
        append_history(username, message, reply)
    return Response(stream_with_context(generate()), headers={"Content-Type":"text/event-stream","Cache-Control":"no-cache","Connection":"keep-alive","X-Accel-Buffering":"no"})

# ---------- HISTORY ----------
@app.get("/api/history")
def history_get():
    return jsonify(get_history(request.args.get("username") or "guest", limit=int(request.args.get("limit") or 200)))

@app.post("/api/history/clear")
def history_clear():
    n = clear_history((request.get_json(silent=True) or {}).get("username") or "guest")
    return jsonify({"ok": True, "cleared": bool(n)})

@app.get("/api/history/export")
def history_export():
    u = request.args.get("username") or "guest"
    items = get_history(u, limit=1000)
    return Response(json.dumps(items, indent=2, ensure_ascii=False), mimetype="application/json", headers={"Content-Disposition": f'attachment; filename="history_{u}.json"'})

# ---------- RAG APIs (browse + admin ops) ----------

@app.post("/api/rag/query")
def api_rag_query():
    """Semantic search endpoint used by vectors UI."""
    data = request.get_json(force=True) or {}
    username = (data.get("username") or "guest").strip() or "guest"
    query = (data.get("query") or "").strip()
    top_k = int(data.get("top_k") or 6)
    if not query: return jsonify({"error":"missing_query"}), 400
    res = rag_search(username, query, top_k)
    return jsonify(res), (200 if res.get("ok", True) else 500)

@app.get("/api/rag/stats")
def api_rag_stats():
    backend = rag_backend()
    out = {"backend": backend}
    try:
        if backend == "qdrant":
            info = qdrant.get_collection(QDRANT_COLLECTION)
            out["points_count"] = getattr(info, "points_count", None)
        elif backend == "pgvector":
            with pg.cursor() as cur:
                cur.execute("SELECT count(*) FROM rag_chunks;")
                out["rows"] = cur.fetchone()[0]
                cur.execute("SELECT count(DISTINCT username) FROM rag_chunks;")
                out["users"] = cur.fetchone()[0]
        elif backend == "redis":
            out["note"] = "redis backend; per-user list under key rag:{username}:docs"
    except Exception as e:
        out["error"] = str(e)
    return jsonify(out)

@app.get("/api/rag/list")
def api_rag_list():
    username = (request.args.get("username") or "guest").strip() or "guest"
    limit = max(1, min(int(request.args.get("limit") or 20), 200))
    offset = max(0, int(request.args.get("offset") or 0))
    backend = rag_backend()
    rows=[]; total=None
    try:
        if backend == "qdrant":
            res = qdrant.scroll(collection_name=QDRANT_COLLECTION, with_payload=True, limit=limit, offset=offset)
            pts = res[0] or []
            for p in pts:
                pl = p.payload or {}
                if pl.get("username") == username:
                    rows.append({"id": str(p.id), "text": pl.get("text","")[:400], "metadata": pl.get("metadata",{})})
            total = None
        elif backend == "pgvector":
            with pg.cursor() as cur:
                cur.execute("SELECT count(*) FROM rag_chunks WHERE username=%s;", (username,))
                total = cur.fetchone()[0]
                cur.execute("SELECT id, text, metadata FROM rag_chunks WHERE username=%s ORDER BY id OFFSET %s LIMIT %s;", (username, offset, limit))
                for rid, t, meta in cur.fetchall():
                    rows.append({"id": str(rid), "text": (t or "")[:400], "metadata": meta or {}})
        elif backend == "redis":
            key = f"rag:{username}:docs"
            all_items = r.lrange(key, 0, -1)
            total = len(all_items)
            page = all_items[offset: offset+limit]
            for raw in page:
                try:
                    o = json.loads(raw)
                    rows.append({"id": o.get("id"), "text": (o.get("text","")[:400]), "metadata": o.get("meta",{})})
                except Exception:
                    pass
        else:
            return jsonify({"error":"no_vector_backend"}), 503
    except Exception as e:
        return jsonify({"error": str(e), "backend": backend}), 500
    return jsonify({"backend": backend, "username": username, "rows": rows, "limit": limit, "offset": offset, "total": total})

@app.post("/api/rag/delete")
def api_rag_delete():
    data = request.get_json(silent=True) or {}
    username = (data.get("username") or "guest").strip() or "guest"
    doc_id = (data.get("id") or "").strip()
    delete_all = bool(data.get("all"))
    backend = rag_backend()
    try:
        if backend == "qdrant":
            if delete_all:
                from qdrant_client.models import Filter, FieldCondition, MatchValue
                qdrant.delete(collection_name=QDRANT_COLLECTION, points_selector=Filter(must=[FieldCondition(key="username", match=MatchValue(value=username))]))
                return jsonify({"ok": True, "backend":"qdrant", "deleted":"all"})
            if not doc_id: return jsonify({"error":"missing_id"}), 400
            qdrant.delete(collection_name=QDRANT_COLLECTION, points_selector=[doc_id])
            return jsonify({"ok": True, "backend":"qdrant", "deleted": doc_id})

        elif backend == "pgvector":
            with pg.cursor() as cur:
                if delete_all:
                    cur.execute("DELETE FROM rag_chunks WHERE username=%s;", (username,))
                    return jsonify({"ok": True, "backend":"pgvector", "deleted": "all"})
                if not doc_id: return jsonify({"error":"missing_id"}), 400
                cur.execute("DELETE FROM rag_chunks WHERE id=%s AND username=%s;", (uuid.UUID(doc_id), username))
                return jsonify({"ok": True, "backend":"pgvector", "deleted": doc_id})

        elif backend == "redis":
            key = f"rag:{username}:docs"
            if delete_all:
                r.delete(key)
                return jsonify({"ok": True, "backend":"redis", "deleted":"all"})
            if not doc_id: return jsonify({"error":"missing_id"}), 400
            items = r.lrange(key, 0, -1)
            deleted = False
            for it in items:
                try:
                    o = json.loads(it)
                    if o.get("id")==doc_id:
                        r.lrem(key, 1, it); deleted=True; break
                except Exception: pass
            return jsonify({"ok": True, "backend":"redis", "deleted": doc_id, "found": deleted})
        else:
            return jsonify({"error":"no_vector_backend"}), 503
    except Exception as e:
        return jsonify({"error": str(e), "backend": backend}), 500

@app.post("/api/rag/compact")
def api_rag_compact():
    backend = rag_backend()
    if backend == "pgvector":
        try:
            with pg.cursor() as cur:
                cur.execute("VACUUM (VERBOSE, ANALYZE) rag_chunks;")
                cur.execute("REINDEX TABLE rag_chunks;")
            return jsonify({"ok": True, "backend":"pgvector", "action":"vacuum+reindex"})
        except Exception as e:
            return jsonify({"error": str(e)}), 500
    return jsonify({"ok": True, "backend": backend, "note":"nothing to compact"})

@app.post("/api/rag/qdrant/flush")
def api_qdrant_flush():
    backend = rag_backend()
    if backend != "qdrant":
        return jsonify({"ok": False, "backend": backend, "note":"not qdrant"}), 400
    try:
        qdrant.optimize_index(QDRANT_COLLECTION)
        return jsonify({"ok": True, "backend":"qdrant", "action":"optimize"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ---------- RAG: CSV Export ----------
@app.get("/api/rag/export.csv")
def api_rag_export_csv():
    username = (request.args.get("username") or "").strip()
    if not username:
        return jsonify({"error":"missing_username"}), 400
    backend = rag_backend()
    rows=[]
    try:
        if backend == "qdrant":
            # naive scroll; filter after fetch
            collected = 0
            offset = None
            while True:
                page, offset, _ = qdrant.scroll(collection_name=QDRANT_COLLECTION, with_payload=True, limit=256, offset=offset)
                if not page: break
                for p in page:
                    pl = p.payload or {}
                    if pl.get("username")==username:
                        rows.append({"id": str(p.id), "username": username, "text": pl.get("text",""), "metadata": json.dumps(pl.get("metadata",{}), ensure_ascii=False)})
                collected += len(page)
                if len(page) < 256 or len(rows) >= 5000:  # safety cap
                    break

        elif backend == "pgvector":
            with pg.cursor() as cur:
                cur.execute("SELECT id, text, metadata FROM rag_chunks WHERE username=%s ORDER BY id;", (username,))
                for rid, t, meta in cur.fetchall():
                    rows.append({"id": str(rid), "username": username, "text": t or "", "metadata": json.dumps(meta or {}, ensure_ascii=False)})

        elif backend == "redis":
            key = f"rag:{username}:docs"
            for raw in r.lrange(key, 0, -1):
                try:
                    o = json.loads(raw)
                    rows.append({"id": o.get("id"), "username": username, "text": o.get("text",""), "metadata": json.dumps(o.get("meta",{}), ensure_ascii=False)})
                except Exception:
                    pass
        else:
            return jsonify({"error":"no_vector_backend"}), 503
    except Exception as e:
        return jsonify({"error": str(e), "backend": backend}), 500

    def gen_csv():
        yield "id,username,text,metadata\n"
        w = csv.writer(io.StringIO())  # dummy, not used; we’ll manual-escape commas via csv module on the fly
        for row in rows:
            # use csv to handle quoting
            buf = io.StringIO()
            csv.writer(buf).writerow([row["id"], row["username"], row["text"], row["metadata"]])
            yield buf.getvalue()
    return Response(gen_csv(), mimetype="text/csv", headers={"Content-Disposition": f'attachment; filename="rag_{username}.csv"'})

# ---------- RAG: Re-embed / Reindex sweep (ADMIN) ----------
def _reembed_qdrant(username: Optional[str], max_items: int, batch: int, embed_model: Optional[str]) -> Dict[str,Any]:
    done=0; offset=None; updated=0
    from qdrant_client.models import PointStruct
    while done < max_items:
        page, offset, _ = qdrant.scroll(collection_name=QDRANT_COLLECTION, with_payload=True, limit=min(256, max_items-done), offset=offset)
        if not page: break
        # filter and collect texts
        pts=[]; texts=[]
        for p in page:
            pl = p.payload or {}
            if username and pl.get("username") != username:
                continue
            txt = pl.get("text","")
            pts.append(p); texts.append(txt)
        if not texts:
            done += len(page); 
            if len(page) < 256: break
            continue
        # embed in batches
        for i in range(0, len(texts), batch):
            chunk = texts[i:i+batch]
            vecs = embed_texts(chunk, model=embed_model)
            if vecs and OPENAI_KEY and len(vecs[0]) != EMBED_DIM:
                return {"ok": False, "reason": f"embedding_dim_mismatch expected {EMBED_DIM}, got {len(vecs[0])}"}
            up=[]
            for j, v in enumerate(vecs):
                p0 = pts[i+j]
                up.append(PointStruct(id=p0.id, vector=v, payload=p0.payload))
            qdrant.upsert(collection_name=QDRANT_COLLECTION, points=up, wait=True)
            updated += len(up)
        done += len(page)
        if len(page) < 256: break
    return {"ok": True, "backend":"qdrant", "updated": updated}

def _reembed_pg(username: Optional[str], max_items: int, batch: int, embed_model: Optional[str]) -> Dict[str,Any]:
    from pgvector.psycopg import Vector
    updated=0
    with pg.cursor() as cur:
        if username:
            cur.execute("SELECT id, text FROM rag_chunks WHERE username=%s ORDER BY id LIMIT %s;", (username, max_items))
        else:
            cur.execute("SELECT id, text FROM rag_chunks ORDER BY id LIMIT %s;", (max_items,))
        rows = cur.fetchall()
    for i in range(0, len(rows), batch):
        chunk = rows[i:i+batch]
        texts = [t or "" for _, t in chunk]
        vecs = embed_texts(texts, model=embed_model)
        if vecs and OPENAI_KEY and len(vecs[0]) != EMBED_DIM:
            return {"ok": False, "reason": f"embedding_dim_mismatch expected {EMBED_DIM}, got {len(vecs[0])}"}
        with pg.cursor() as cur:
            for (rid, _), v in zip(chunk, vecs):
                cur.execute("UPDATE rag_chunks SET embedding=%s WHERE id=%s;", (Vector(v), rid))
                updated += 1
    return {"ok": True, "backend":"pgvector", "updated": updated}

def _reembed_redis(username: Optional[str], max_items: int, batch: int, embed_model: Optional[str]) -> Dict[str,Any]:
    if not username:
        return {"ok": False, "reason":"redis_requires_username"}
    key = f"rag:{username}:docs"
    items = r.lrange(key, 0, max_items-1)
    docs=[]
    for raw in items:
        try: docs.append(json.loads(raw))
        except Exception: pass
    texts=[d.get("text","") for d in docs]
    updated=0
    for i in range(0, len(texts), batch):
        chunk=texts[i:i+batch]
        vecs = embed_texts(chunk, model=embed_model)
        if vecs and OPENAI_KEY and len(vecs[0]) != EMBED_DIM:
            return {"ok": False, "reason": f"embedding_dim_mismatch expected {EMBED_DIM}, got {len(vecs[0])}"}
        for j, v in enumerate(vecs):
            docs[i+j]["vec"] = v
            updated += 1
    # rewrite list
    pipe = r.pipeline()
    r.delete(key)
    for d in docs:
        pipe.rpush(key, json.dumps(d))
    pipe.execute()
    return {"ok": True, "backend":"redis", "updated": updated}

def _require_admin(req) -> bool:
    data = decode_jwt_from_header()
    if data and data.get("typ")=="access" and data.get("role")=="admin": return True
    if not ADMIN_TOKEN: return False
    auth = req.headers.get("Authorization", "")
    if not auth.startswith("Bearer "): return False
    return secrets.compare_digest(auth.split(" ",1)[1].strip(), ADMIN_TOKEN)

@app.post("/api/rag/reembed_all")
def api_rag_reembed_all():
    if not _require_admin(request): return jsonify({"error":"unauthorized"}), 401
    data = request.get_json(silent=True) or {}
    username = (data.get("username") or "").strip() or None
    max_items = max(1, min(int(data.get("max") or 500), 5000))
    batch = max(1, min(int(data.get("batch") or 64), 256))
    model_override = (data.get("embed_model") or "").strip() or None

    backend = rag_backend()
    try:
        if backend == "qdrant":
            res = _reembed_qdrant(username, max_items, batch, model_override)
        elif backend == "pgvector":
            res = _reembed_pg(username, max_items, batch, model_override)
        elif backend == "redis":
            res = _reembed_redis(username, max_items, batch, model_override)
        else:
            return jsonify({"error":"no_vector_backend"}), 503
        return jsonify(res)
    except Exception as e:
        return jsonify({"error": str(e), "backend": backend}), 500

# alias for convenience
@app.post("/api/rag/reindex_all_users")
def api_rag_reindex_all_users():
    return api_rag_reembed_all()

# ---------- Upload (role-based size + OCR) ----------
@app.post("/api/upload")
def upload_index():
    user = decode_jwt_from_header()
    if not user: return jsonify({"error":"unauthorized"}), 401
    username = user.get("sub") or "guest"
    role = user.get("role") or "user"

    total = int(request.headers.get("Content-Length") or 0)
    limit_mb = UPLOAD_MAX_MB_ADMIN if role == "admin" else UPLOAD_MAX_MB_USER
    if total > 0 and total > (limit_mb * 1024 * 1024):
        return jsonify({"error":"payload_too_large","limit_mb": limit_mb}), 413

    if "files" not in request.files: return jsonify({"error": "no_files"}), 400
    files = request.files.getlist("files")
    if not files: return jsonify({"error":"no_files"}), 400

    docs=[]; total_chunks=0; ocr_blocks=0
    for f in files:
        fname = secure_filename(f.filename or "")
        if not fname: continue
        ext = os.path.splitext(fname)[1].lower()
        if ext not in ALLOWED_EXT: continue
        data = f.read()
        text = ""
        if ext == ".pdf": text = _read_pdf(data)
        elif ext in {".txt",".md"}:
            try: text = data.decode("utf-8", errors="ignore")
            except Exception: text = ""
        elif ext == ".docx":
            base = _read_docx_text(data)
            ocr = _read_docx_image_ocr(data)
            text = "\n".join([t for t in [base, ocr] if t])
            if ocr: ocr_blocks += 1
        elif ext in {".html",".htm"}: text = _read_html(data)
        if not text: continue
        for idx, ch in enumerate(_chunk_text(text)):
            docs.append({"id": f"{fname}-{idx}", "text": ch, "metadata": {"filename": fname, "chunk": idx}})
            total_chunks += 1

    if not docs: return jsonify({"ok": False, "reason": "no_text_extracted"}), 400
    res = rag_index(username, docs)
    return jsonify({"ok": True, "backend": res.get("backend"), "indexed_docs": res.get("count", 0), "chunks": total_chunks, "ocr_blocks": ocr_blocks, "role": role, "limit_mb": limit_mb})

# ---------- Admin ----------
def require_admin(req) -> bool:
    return _require_admin(req)

@app.post("/api/admin/mint")
def admin_mint():
    if not require_admin(request): return jsonify({"error":"unauthorized"}), 401
    if not r: return jsonify({"error":"redis_unavailable"}), 503
    count = max(1, min(int((request.get_json(silent=True) or {}).get("count") or 1), 20))
    toks=[]
    for _ in range(count):
        code = secrets.token_urlsafe(8)
        r.set(k_admin_code(code), "1", ex=60*60*24)  # 24h
        toks.append(code)
    return jsonify({"tokens": toks, "ttl_hours": 24})

@app.post("/api/auth/redeem")
def auth_redeem():
    if not r: return jsonify({"error":"redis_unavailable"}), 503
    body = request.get_json(silent=True) or {}
    code = (body.get("code") or "").strip()
    username = (body.get("username") or "guest").strip() or "guest"
    if not code: return jsonify({"error":"missing_code"}), 400
    key = k_admin_code(code)
    if not r.get(key): return jsonify({"success": False, "reason":"invalid_or_expired"}), 400
    r.delete(key)
    return jsonify({"success": True, "user": username})

@app.post("/api/admin/history/clear")
def admin_history_clear():
    if not require_admin(request): return jsonify({"error":"unauthorized"}), 401
    body = request.get_json(silent=True) or {}
    uname = (body.get("username") or "guest").strip()
    n = clear_history(uname)
    return jsonify({"ok": True, "cleared": bool(n), "username": uname})

# ---------- Structured JSON ----------
@app.post("/api/structured")
def structured_json():
    data = request.get_json(force=True) or {}
    prompt = (data.get("prompt") or "").strip()
    if not prompt: return jsonify({"error":"missing_prompt"}), 400
    model = (data.get("model") or active_model()).strip()
    if not OPENAI_KEY:
        return jsonify({"json":{"note":"dev no-key","echo": prompt[:120]}})
    from openai import OpenAI
    client = OpenAI(api_key=OPENAI_KEY)
    resp = client.chat.completions.create(
        model=model,
        messages=[{"role":"system","content": SYSTEM_PROMPT},{"role":"user","content": prompt}],
        response_format={"type":"json_object"},
        temperature=0.2
    )
    txt = resp.choices[0].message.content.strip() or "{}"
    try: obj = json.loads(txt)
    except Exception: obj = {"raw": txt}
    return jsonify({"json": obj})

# ---------- Static ----------
@app.get("/static/<path:filename>")
def static_files(filename):
    return send_from_directory(app.static_folder, filename)

# ---------- Errors ----------
@app.errorhandler(404)
def not_found(_):
    if request.path.startswith("/api/"):
        return jsonify({"error":"not_found","path": request.path}), 404
    return "Not Found", 404

@app.errorhandler(405)
def method_not_allowed(_):
    if request.path.startswith("/api/"):
        return jsonify({"error":"method_not_allowed","path": request.path}), 405
    return "Method Not Allowed", 405

if __name__ == "__main__":
    port = int(os.getenv("PORT", "5000"))
    app.run(host="0.0.0.0", port=port, debug=(os.getenv("FLASK_ENV","").lower()!="production"), threaded=True)




























