# app.py
import os, io, json, time, math, secrets, hashlib, mimetypes, uuid
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple, Generator

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

# Optional Sentry
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

app = Flask(__name__, static_folder="static", template_folder="templates")
CORS(app, resources={r"/*": {"origins": [o.strip() for o in os.getenv("CORS_ALLOW_ORIGINS", "*").split(",")]}})

COMMIT = (os.getenv("RENDER_GIT_COMMIT", "")[:7] or os.getenv("COMMIT", "") or "dev")
OPENAI_KEY = os.getenv("OPENAI_API_KEY", "")
DEFAULT_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
SYSTEM_PROMPT = os.getenv("PROMPT_SYSTEM", "You are Friday AI: quick, accurate, actionable.")
EMBED_MODEL = os.getenv("EMBED_MODEL", "text-embedding-3-small")

# ---------- Token lifetimes (upgrade: refresh tokens) ----------
ACCESS_TTL_MIN = int(os.getenv("ACCESS_TTL_MIN", "15"))        # short-lived access token
REFRESH_TTL_DAYS = int(os.getenv("REFRESH_TTL_DAYS", "14"))    # longer-lived refresh token
JWT_SECRET = os.getenv("JWT_SECRET", "dev-secret-change-me")
APP_LOGIN_PASSWORD = os.getenv("APP_LOGIN_PASSWORD", "")
ADMIN_TOKEN = os.getenv("ADMIN_TOKEN", "")

# ---------- Rate limit ----------
RL_WINDOW = int(os.getenv("RATE_LIMIT_WINDOW_SECONDS", "60"))
RL_MAX = int(os.getenv("RATE_LIMIT_MAX", "60"))

# ---------- Pricing (rough) ----------
PRICES = {
    "gpt-4o":        {"in": 0.0025, "out": 0.0100},
    "gpt-4o-mini":   {"in": 0.0005, "out": 0.0015},
    "gpt-4.1-mini":  {"in": 0.0006, "out": 0.0018},
    "o3-mini":       {"in": 0.0005, "out": 0.0015},
}

# ---------- Redis (history, RL, cache) ----------
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

# ---------- PGVector (vector DB) with fallback to Redis ----------
pg = None
pg_cosine_ok = None  # lazy-detected cosine operator
EMBED_DIM = int(os.getenv("EMBED_DIM", "1536"))  # text-embedding-3-small = 1536; large = 3072

def _connect_pg():
    global pg
    PG_URL = os.getenv("PG_URL", "")
    if not PG_URL:
        return None
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
            # cosine index if available, else l2 index
            try:
                cur.execute(f"CREATE INDEX IF NOT EXISTS idx_rag_chunks_embedding_cos ON rag_chunks USING ivfflat (embedding vector_cosine_ops) WITH (lists=100);")
            except Exception:
                cur.execute(f"CREATE INDEX IF NOT EXISTS idx_rag_chunks_embedding_l2 ON rag_chunks USING ivfflat (embedding vector_l2_ops) WITH (lists=100);")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_rag_chunks_user ON rag_chunks (username);")
        return pg
    except Exception as e:
        print("PG init failed:", e)
        pg = None
        return None

_connect_pg()

def pg_upsert_docs(username: str, docs: List[Dict[str, Any]]) -> int:
    if not pg: return 0
    from pgvector.psycopg import Vector
    import psycopg
    from psycopg.types.json import Json
    inserted = 0
    with pg.cursor() as cur:
        for d in docs:
            try:
                cur.execute(
                    "INSERT INTO rag_chunks (id, username, text, metadata, embedding) VALUES (%s,%s,%s,%s,%s) "
                    "ON CONFLICT (id) DO UPDATE SET text=EXCLUDED.text, metadata=EXCLUDED.metadata, embedding=EXCLUDED.embedding;",
                    (uuid.uuid4(), username, d["text"], Json(d.get("metadata") or {}), Vector(d["vec"]))
                )
                inserted += 1
            except Exception:
                pass
    return inserted

def pg_query(username: str, qvec: List[float], top_k: int = 4) -> List[Dict[str, Any]]:
    """Try cosine operator <=> first (pgvector >=0.5); else fall back to L2 <->."""
    if not pg: return []
    from pgvector.psycopg import Vector
    rows = []
    global pg_cosine_ok
    with pg.cursor() as cur:
        if pg_cosine_ok is None:
            try:
                cur.execute("SELECT 1 FROM pg_proc WHERE proname = 'cosine_distance' LIMIT 1;")
                pg_cosine_ok = bool(cur.fetchone())
            except Exception:
                pg_cosine_ok = False
        try:
            if pg_cosine_ok:
                cur.execute(
                    "SELECT id, text, metadata, 1 - (embedding <=> %s) AS score "
                    "FROM rag_chunks WHERE username=%s ORDER BY embedding <=> %s LIMIT %s;",
                    (Vector(qvec), username, Vector(qvec), top_k)
                )
            else:
                # use L2 distance (smaller is better); convert to a pseudo-score
                cur.execute(
                    "SELECT id, text, metadata, (1.0 / (1.0 + (embedding <-> %s))) AS score "
                    "FROM rag_chunks WHERE username=%s ORDER BY embedding <-> %s LIMIT %s;",
                    (Vector(qvec), username, Vector(qvec), top_k)
                )
            for rid, t, meta, score in cur.fetchall():
                rows.append({"id": str(rid), "text": t, "metadata": meta or {}, "score": round(float(score or 0), 4)})
        except Exception as e:
            print("pg_query failed:", e)
    return rows

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

# ---------- JWT (access & refresh) ----------
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

# ---------- OpenAI helpers ----------
def price_estimate(model: str, p_tok: int, c_tok: int) -> float:
    p = PRICES.get(model, PRICES.get("gpt-4o-mini"))
    return (p_tok/1000.0)*p["in"] + (c_tok/1000.0)*p["out"]

def embed_texts(texts: List[str]) -> List[List[float]]:
    if not OPENAI_KEY:
        # dev fake embeddings
        def cheap_vec(s: str, dim=64):
            v = [0.0]*dim
            for i,ch in enumerate(s.encode("utf-8")):
                v[i % dim] += (ch % 13) / 13.0
            n = math.sqrt(sum(x*x for x in v)) or 1.0
            return [x/n for x in v]
        return [cheap_vec(t) for t in texts]
    from openai import OpenAI
    client = OpenAI(api_key=OPENAI_KEY)
    res = client.embeddings.create(model=EMBED_MODEL, input=texts)
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
    return {"ok": True, "commit": COMMIT, "redis": redis_ok(), "pg": bool(pg), "model": active_model()}

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

def rag_index(username: str, docs: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Index into PGVector if available, else Redis-only (kept for compatibility)."""
    texts = [d.get("text","") for d in docs]
    vecs = embed_texts(texts)
    for d, v in zip(docs, vecs):
        d["vec"] = v

    if pg:
        inserted = pg_upsert_docs(username, docs)
        return {"ok": True, "count": inserted, "backend": "pgvector"}
    else:
        if not r: return {"ok": False, "reason":"no_vector_backend"}
        key = f"rag:{username}:docs"
        pipe = r.pipeline()
        for d in docs:
            row = {"id": d.get("id") or secrets.token_urlsafe(6), "text": d.get("text",""), "meta": d.get("metadata", {}), "vec": d["vec"]}
            pipe.rpush(key, json.dumps(row))
        pipe.execute()
        r.ltrim(key, -2000, -1)
        return {"ok": True, "count": len(docs), "backend": "redis"}

def cosine(a: List[float], b: List[float]) -> float:
    s = sum(x*y for x,y in zip(a,b))
    na = math.sqrt(sum(x*x for x in a)) or 1.0
    nb = math.sqrt(sum(x*x for x in b)) or 1.0
    return s/(na*nb)

def rag_search(username: str, query: str, top_k: int = 4) -> Dict[str, Any]:
    qvec = embed_texts([query])[0]
    if pg:
        matches = pg_query(username, qvec, top_k=top_k)
        return {"ok": True, "matches": matches, "backend": "pgvector"}
    if not r:
        return {"ok": False, "reason": "no_vector_backend"}
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

# ---------- OpenAI w/ tools ----------
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
        # dev echo + simple tools
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

# ---------- File ingestion (PDF/TXT/MD/DOCX/HTML) ----------
from werkzeug.utils import secure_filename
ALLOWED_EXT = {".txt", ".md", ".pdf", ".docx", ".html", ".htm"}
app.config["MAX_CONTENT_LENGTH"] = int(os.getenv("MAX_CONTENT_LENGTH_BYTES", str(20*1024*1024)))  # 20MB

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

def _read_docx(data: bytes) -> str:
    try:
        from docx import Document
        doc = Document(io.BytesIO(data))
        return "\n".join([p.text for p in doc.paragraphs]).strip()
    except Exception:
        return ""

def _read_html(data: bytes) -> str:
    try:
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(data, "html.parser")
        # strip scripts/styles
        for t in soup(["script","style","noscript"]): t.extract()
        return soup.get_text("\n").strip()
    except Exception:
        return ""

# ---------- Routes: pages ----------
@app.get("/")
def home():
    return send_from_directory(app.static_folder, "chat.html")

@app.get("/chat")
def chat_page():
    return send_from_directory(app.static_folder, "chat.html")

# ---------- Diagnostics ----------
@app.get("/routes")
def routes():
    out=[]
    for rule in app.url_map.iter_rules():
        out.append({"endpoint": rule.endpoint, "methods": sorted(m for m in rule.methods if m in {"GET","POST","OPTIONS"}), "rule": str(rule)})
    return jsonify(sorted(out, key=lambda r: r["rule"]))

@app.get("/debug/health")
def health():
    return jsonify({"ok": True, "commit": COMMIT, "redis": redis_ok(), "pg": bool(pg), "model": active_model(), "openai": bool(OPENAI_KEY)})

@app.get("/api/metrics")
def metrics():
    scope = client_scope()
    allowed, remaining, reset = rate_limit_check(scope)
    return jsonify({"rate_limit":{"allowed":allowed,"remaining":remaining,"reset":reset},"model": active_model(),"pg": bool(pg)})

# ---------- Auth (login / refresh) ----------
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
        # also allow Bearer refresh
        auth = request.headers.get("Authorization","")
        if auth.startswith("Bearer "): token = auth.split(" ",1)[1]
    if not token:
        return jsonify({"error":"missing_refresh_token"}), 400
    import jwt
    try:
        data = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
        if data.get("typ") != "refresh": raise Exception("wrong_token_type")
        username = data.get("sub") or "guest"
        role = data.get("role") or "user"
        return jsonify({"access_token": make_access(username, role), "user":{"username":username,"role":role}})
    except Exception as e:
        return jsonify({"error":"invalid_refresh","detail": str(e)}), 401

# ---------- Models ----------
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

# ---------- Chat (non-stream with tools) ----------
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

# ---------- Streaming (legacy & tools) ----------
def sse_line(obj: Dict[str,Any]) -> str: return f"data: {json.dumps(obj, ensure_ascii=False)}\n\n"

@app.get("/api/chat/stream-tools")
def api_chat_stream_tools():
    message = (request.args.get("message") or "").strip()
    username = request.args.get("username") or "guest"
    model = request.args.get("model") or active_model(username)
    if not message: return jsonify({"error":"missing_message"}), 400

    def generate():
        # Cheap stream simulation for dev; for full tool streaming you'd stitch similar to previous version.
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
        last = time.time()
        for chunk in stream:
            if time.time() - last > 10:
                yield ":keepalive\n\n"; last = time.time()
            part = ""
            try: part = chunk.choices[0].delta.content or ""
            except Exception: pass
            if part:
                final.append(part)
                yield sse_line({"type":"delta","delta": part})
        yield sse_line({"type":"done"})
        append_history(username, message, "".join(final))
    return Response(stream_with_context(generate()), headers={"Content-Type":"text/event-stream","Cache-Control":"no-cache","Connection":"keep-alive","X-Accel-Buffering":"no"})

@app.get("/api/chat/stream")
def api_chat_stream_plain():
    # kept for compatibility
    return api_chat_stream_tools()

# ---------- History ----------
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

# ---------- RAG APIs ----------
@app.post("/api/rag/index")
def api_rag_index():
    data = request.get_json(silent=True) or {}
    username = (data.get("username") or "guest").strip() or "guest"
    docs = data.get("docs")
    if not isinstance(docs, list) or not docs: return jsonify({"error":"missing_docs"}), 400
    res = rag_index(username, docs)
    return jsonify(res)

@app.post("/api/rag/query")
def api_rag_query():
    data = request.get_json(silent=True) or {}
    username = (data.get("username") or "guest").strip() or "guest"
    query = (data.get("query") or "").strip()
    top_k = int(data.get("top_k") or 4)
    if not query: return jsonify({"error":"missing_query"}), 400
    return jsonify(rag_search(username, query, top_k))

# ---------- Upload (JWT access required) ----------
@app.post("/api/upload")
def upload_index():
    user = require_access(role=None)
    if not user: return jsonify({"error":"unauthorized"}), 401
    username = user.get("sub") or "guest"
    if "files" not in request.files: return jsonify({"error": "no_files"}), 400
    files = request.files.getlist("files")
    if not files: return jsonify({"error":"no_files"}), 400

    docs=[]; total_chunks=0
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
        elif ext == ".docx": text = _read_docx(data)
        elif ext in {".html",".htm"}: text = _read_html(data)
        if not text: continue
        for idx, ch in enumerate(_chunk_text(text)):
            docs.append({"id": f"{fname}-{idx}", "text": ch, "metadata": {"filename": fname, "chunk": idx}})
            total_chunks += 1

    if not docs: return jsonify({"ok": False, "reason": "no_text_extracted"}), 400
    res = rag_index(username, docs)
    return jsonify({"ok": True, "backend": res.get("backend"), "indexed_docs": res.get("count", 0), "chunks": total_chunks})

# ---------- Admin (role-guard via access token OR legacy bearer) ----------
def require_admin(req) -> bool:
    data = require_access(role="admin")
    if data: return True
    if not ADMIN_TOKEN: return False
    auth = req.headers.get("Authorization", "")
    if not auth.startswith("Bearer "): return False
    return secrets.compare_digest(auth.split(" ",1)[1].strip(), ADMIN_TOKEN)

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

# ---------- Static ----------
@app.get("/static/<path:filename>")
def static_files(filename):
    return send_from_directory(app.static_folder, filename)

# ---------- API-friendly errors ----------
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

























