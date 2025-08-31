# app.py
import os, io, json, time, math, secrets, hashlib, uuid, csv
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple

# -------- env (local only)
try:
    from dotenv import load_dotenv
    if os.getenv("FLASK_ENV","").lower() != "production":
        load_dotenv(override=False)
except Exception:
    pass

from flask import (
    Flask, jsonify, request, send_from_directory,
    Response, stream_with_context, make_response
)
from flask_cors import CORS
from flask_compress import Compress

# -------- app core
app = Flask(__name__, static_folder="static", template_folder="templates")
Compress(app)
CORS(app, resources={r"/*": {"origins": [o.strip() for o in os.getenv("CORS_ALLOW_ORIGINS","*").split(",")]}})

COMMIT       = (os.getenv("RENDER_GIT_COMMIT","")[:7] or os.getenv("COMMIT","") or "dev")
OPENAI_KEY   = os.getenv("OPENAI_API_KEY","")
DEFAULT_MODEL= os.getenv("OPENAI_MODEL","gpt-4o-mini")

EMBED_MODEL  = os.getenv("EMBED_MODEL", "text-embedding-3-small")
EMBED_DIM    = int(os.getenv("EMBED_DIM", "1536"))

PROJECT_DEFAULT = os.getenv("PROJECT_DEFAULT","default")

RL_WINDOW = int(os.getenv("RATE_LIMIT_WINDOW_SECONDS", "60"))
RL_MAX    = int(os.getenv("RATE_LIMIT_MAX", "60"))

FALLBACK_MODELS = [m.strip() for m in os.getenv("FALLBACK_MODELS","gpt-4o,gpt-4o-mini,o3-mini").split(",")]
OPENAI_TIMEOUT  = int(os.getenv("TIMEOUT_OPENAI_MS","12000"))

PROMPT_PRESETS = {
    "concise": "You are Friday: brief, clear, no fluff.",
    "teacher": "You are Friday the Coach: explain like I'm 5, step-by-step, with tiny examples.",
    "analyst": "You are Friday the Analyst: structured, bullet points, cite assumptions.",
    "drill":   "You are Friday the Drill Sergeant: motivating, blunt, but respectful. Keep it tight.",
}
SYSTEM_PROMPT_DEFAULT = os.getenv("PROMPT_SYSTEM", PROMPT_PRESETS["concise"])

# -------- security headers
@app.after_request
def _secure_headers(resp):
    resp.headers["X-Content-Type-Options"] = "nosniff"
    resp.headers["X-Frame-Options"] = "DENY"
    resp.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    resp.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
    # same-origin calls, so this is fine
    resp.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "script-src 'self'; style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data:; connect-src 'self';"
    )
    if request.headers.get("X-Forwarded-Proto","") == "https":
        resp.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains; preload"
    return resp

# -------- logging
import time as _t
@app.before_request
def _start_timer(): request._t0 = _t.time()

@app.after_request
def _log_req(resp):
    try:
        dur_ms = int((_t.time() - getattr(request, "_t0", _t.time()))*1000)
        line = {
            "ts": int(_t.time()), "commit": COMMIT,
            "method": request.method, "path": request.path,
            "status": resp.status_code, "ms": dur_ms,
            "ip": (request.headers.get("X-Forwarded-For","").split(",")[0] or request.remote_addr),
        }
        print(json.dumps(line))
    except Exception:
        pass
    return resp

# -------- Redis (history/RL/cache & default RAG)
r = None
try:
    REDIS_URL = os.getenv("REDIS_URL","")
    if REDIS_URL:
        import redis
        r = redis.from_url(REDIS_URL, decode_responses=True)
except Exception:
    r = None

def redis_ok() -> bool:
    if not r: return False
    try: r.ping(); return True
    except Exception: return False

def k_history(u, proj): return f"hist:{u}:{proj}"
def k_rl(scope):        return f"rl:{scope}"
def k_user_preset(u):   return f"user:{u}:preset"
def k_user_model(u):    return f"user:{u}:model"
def k_cache(pfx, k):    return f"cache:{pfx}:{k}"

# RAG keys (redis)
def k_rag_docs(u,proj):   return f"rag:{u}:{proj}:docs"   # list of chunk rows
def k_rag_files(u,proj):  return f"rag:{u}:{proj}:files"  # hash: file_id -> meta json

def client_scope() -> str:
    uname = request.args.get("username") or ((request.json or {}).get("username") if request.is_json else None)
    proj  = request.args.get("project")  or ((request.json or {}).get("project")  if request.is_json else None)
    if uname or proj: return f"user:{uname or 'guest'}:{proj or PROJECT_DEFAULT}"
    fwd = request.headers.get("X-Forwarded-For","") or request.remote_addr or "unknown"
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

def set_user_preset(username: str, preset: str):
    if r: r.set(k_user_preset(username), preset, ex=60*60*24*30)

def get_user_preset(username: str) -> str:
    if r:
        p = r.get(k_user_preset(username))
        if p and p in PROMPT_PRESETS: return p
    return "concise"

def set_user_model(username: str, model: str):
    if r: r.set(k_user_model(username), model, ex=60*60*24*30)

def get_user_model(username: str) -> str:
    if r:
        m = r.get(k_user_model(username))
        if m: return m
    return DEFAULT_MODEL

def append_history(username: str, project: str, message: str, reply: str):
    if not r: return
    r.rpush(k_history(username, project), json.dumps({"ts": time.time(), "message": message, "reply": reply}))
    r.ltrim(k_history(username, project), -500, -1)

def get_history(username: str, project: str, limit: int=200) -> List[Dict[str,Any]]:
    if not r: return []
    items = r.lrange(k_history(username, project), max(-limit, -500), -1)
    out=[]
    for raw in items:
        try: out.append(json.loads(raw))
        except Exception: pass
    return out

def clear_history(username: str, project: str) -> int:
    if not r: return 0
    return r.delete(k_history(username, project)) or 0

# -------- embeddings + moderation
def embed_texts(texts: List[str], model: Optional[str]=None) -> List[List[float]]:
    model = model or EMBED_MODEL
    if not OPENAI_KEY:
        # fallback dev vec
        def cheap_vec(s: str, dim=64):
            v=[0.0]*dim
            for i,ch in enumerate(s.encode()):
                v[i%dim]+= (ch%13)/13.0
            n=math.sqrt(sum(x*x for x in v)) or 1.0
            return [x/n for x in v]
        return [cheap_vec(t) for t in texts]
    from openai import OpenAI
    client = OpenAI(api_key=OPENAI_KEY, timeout=OPENAI_TIMEOUT/1000.0)
    res = client.embeddings.create(model=model, input=texts)
    return [d.embedding for d in res.data]

def moderate_text(text: str) -> bool:
    if not OPENAI_KEY: return True
    try:
        from openai import OpenAI
        client = OpenAI(api_key=OPENAI_KEY, timeout=OPENAI_TIMEOUT/1000.0)
        m = client.moderations.create(model="omni-moderation-latest", input=text)
        return not bool(m.results[0].flagged)
    except Exception:
        return True

def safe_chat(messages, temperature=0.6, tools=None, tool_choice="auto"):
    if not OPENAI_KEY:
        return {"text":"(dev echo) no OPENAI_API_KEY", "usage":None, "model_used":"dev"}
    from openai import OpenAI
    client = OpenAI(api_key=OPENAI_KEY, timeout=OPENAI_TIMEOUT/1000.0)
    tried=[]
    pref = DEFAULT_MODEL
    order = [pref] + [m for m in FALLBACK_MODELS if m != pref]
    for m in order:
        try:
            r = client.chat.completions.create(model=m, messages=[x for x in messages if "username" not in x], tools=tools, tool_choice=tool_choice, temperature=temperature)
            txt = (r.choices[0].message.content or "").strip()
            return {"text": txt, "usage": getattr(r,"usage",None), "model_used": m}
        except Exception as e:
            tried.append(f"{m}:{e}")
            continue
    return {"text":"Upstream busy, try again shortly.", "errors": tried, "model_used": order[-1]}

# -------- token chunker
def _tok_chunk(text: str, target=900, overlap=200) -> List[str]:
    text = (text or "").strip()
    if not text: return []
    try:
        import tiktoken
        enc = tiktoken.get_encoding("o200k_base")
        toks = enc.encode(text)
        out=[]
        i=0
        step = max(1, target-overlap)
        while i < len(toks):
            seg = toks[i:i+target]
            out.append(enc.decode(seg))
            i += step
        return out
    except Exception:
        out=[]; i=0; size= target*4; step=max(1,size-overlap*4)
        while i < len(text):
            out.append(text[i:i+size]); i+=step
        return out

# -------- PDF reading (tables + per-page)
def _read_pdf_pages(raw: bytes) -> List[Dict[str,Any]]:
    # Try pdfplumber (tables + text), fall back to pypdf (text only)
    try:
        import pdfplumber
        pages=[]
        with pdfplumber.open(io.BytesIO(raw)) as pdf:
            for idx, page in enumerate(pdf.pages, start=1):
                txt = (page.extract_text() or "").strip()
                # try tables
                try:
                    tables = page.extract_tables() or []
                    for t in tables:
                        if not t: continue
                        rows = [" | ".join((c or "").strip() for c in row) for row in t if any(row)]
                        if rows:
                            txt += "\n\nTABLE:\n" + "\n".join(rows)
                except Exception:
                    pass
                pages.append({"page": idx, "text": txt})
        return pages
    except Exception:
        try:
            from pypdf import PdfReader
            reader = PdfReader(io.BytesIO(raw))
            out=[]
            for i, p in enumerate(reader.pages, start=1):
                out.append({"page": i, "text": (p.extract_text() or "").strip()})
            return out
        except Exception:
            return []

# -------- cache helpers (redis)
def cache_get(prefix: str, key: str):
    if not r: return None
    return r.get(k_cache(prefix, key))

def cache_set(prefix: str, key: str, value: Any, ttl: int = 300):
    if not r: return
    r.setex(k_cache(prefix, key), ttl, json.dumps(value))

# -------- tiny tools
def http_get(url: str, params: Dict[str,Any], timeout=8, tries=3):
    import requests
    last=None
    for i in range(tries):
        try:
            res = requests.get(url, params=params, timeout=timeout)
            if res.status_code >= 500: raise Exception(f"{res.status_code}")
            return res
        except Exception as e:
            last=e; time.sleep(0.35*(2**i))
    raise last or RuntimeError("http_get failed")

def tool_weather(city: str) -> Dict[str,Any]:
    if not city: return {"ok": False, "reason":"missing_city"}
    h=hashlib.sha256(city.strip().lower().encode()).hexdigest()
    c = cache_get("wx", h)
    if c:
        try: return json.loads(c)
        except Exception: pass
    try:
        g = http_get("https://geocoding-api.open-meteo.com/v1/search", {"name": city, "count": 1})
        gd = g.json() or {}
        if not gd.get("results"): return {"ok": False, "reason":"not_found"}
        lat = gd["results"][0]["latitude"]; lon = gd["results"][0]["longitude"]
        name= gd["results"][0]["name"]; country= gd["results"][0].get("country","")
        w = http_get("https://api.open-meteo.com/v1/forecast", {"latitude": lat, "longitude": lon, "current_weather":"true"})
        cw = (w.json() or {}).get("current_weather") or {}
        out={"ok": True, "city": f"{name}, {country}".strip(", "), "temperature_c": cw.get("temperature"), "windspeed_kmh": cw.get("windspeed")}
        cache_set("wx", h, out, 180)
        return out
    except Exception as e:
        return {"ok": False, "reason": str(e)}

def tool_web(query: str) -> Dict[str,Any]:
    if not query: return {"ok": False, "reason":"missing_query"}
    h=hashlib.sha256(query.strip().lower().encode()).hexdigest()
    c = cache_get("ddg", h)
    if c:
        try: return json.loads(c)
        except Exception: pass
    try:
        res = http_get("https://api.duckduckgo.com/", {"q": query, "format": "json", "no_html": 1, "skip_disambig": 1})
        data = res.json() or {}
        out = {"ok": True, "heading": data.get("Heading"), "summary": data.get("AbstractText"),
               "related": [{"Text": t.get("Text"), "FirstURL": t.get("FirstURL")}
                           for t in (data.get("RelatedTopics") or []) if isinstance(t, dict)][:5]}
        cache_set("ddg", h, out, 300)
        return out
    except Exception as e:
        return {"ok": False, "reason": str(e)}

# -------- tool schema (add project)
OPENAI_TOOLS = [
    {"type":"function","function":{"name":"get_weather","description":"Get current weather for a city.","parameters":{"type":"object","properties":{"city":{"type":"string"}},"required":["city"]}}},
    {"type":"function","function":{"name":"web_search","description":"DuckDuckGo instant answer","parameters":{"type":"object","properties":{"query":{"type":"string"}},"required":["query"]}}},
    {"type":"function","function":{"name":"rag_search","description":"Search user's indexed docs","parameters":{"type":"object","properties":{"username":{"type":"string"},"project":{"type":"string"},"query":{"type":"string"},"top_k":{"type":"integer","minimum":1,"maximum":10}},"required":["username","query"]}}}
]

# -------- RAG backends: Redis OR Postgres/pgvector
def _cos(a: List[float], b: List[float]) -> float:
    s=sum(x*y for x,y in zip(a,b))
    na=math.sqrt(sum(x*x for x in a)) or 1.0
    nb=math.sqrt(sum(x*x for x in b)) or 1.0
    return s/(na*nb)

# PG init (optional)
PG_URL = os.getenv("PG_URL","").strip()
PG_ENABLED = False
try:
    if PG_URL:
        import psycopg  # psycopg3
        PG_ENABLED = True
        def pg_conn():
            return psycopg.connect(PG_URL, autocommit=True)
        def pg_ok():
            try:
                with pg_conn() as c, c.cursor() as cur:
                    cur.execute("SELECT 1;")
                return True
            except Exception:
                return False
        def pg_init():
            with pg_conn() as c, c.cursor() as cur:
                cur.execute("CREATE EXTENSION IF NOT EXISTS vector;")
                cur.execute(f"""
                CREATE TABLE IF NOT EXISTS rag_docs (
                  id        TEXT PRIMARY KEY,
                  username  TEXT NOT NULL,
                  project   TEXT NOT NULL,
                  file_id   TEXT NOT NULL,
                  filename  TEXT NOT NULL,
                  page      INTEGER,
                  chunk     INTEGER,
                  text      TEXT NOT NULL,
                  embedding VECTOR({EMBED_DIM}),
                  ts        BIGINT NOT NULL
                );""")
                # meta indexes
                cur.execute("CREATE INDEX IF NOT EXISTS idx_rag_docs_user_proj ON rag_docs(username, project);")
                cur.execute("CREATE INDEX IF NOT EXISTS idx_rag_docs_file ON rag_docs(username, project, file_id);")
                # vector index (cosine)
                cur.execute("CREATE INDEX IF NOT EXISTS idx_rag_docs_vec ON rag_docs USING ivfflat (embedding vector_cosine_ops) WITH (lists=100);")
        if PG_ENABLED and pg_ok(): pg_init()
except Exception:
    PG_ENABLED = False

def _vec_literal(vec: List[float]) -> str:
    # format for pgvector: '[v1,v2,...]'
    return "[" + ",".join(f"{x:.6f}" for x in vec) + "]"

def rag_index_pg(username: str, project: str, file_id: str, filename: str, chunks: List[Dict[str,Any]]) -> int:
    if not PG_ENABLED: return 0
    vecs = embed_texts([c["text"] for c in chunks])
    ts = int(time.time())
    rows = list(zip(chunks, vecs))
    added=0
    with pg_conn() as c, c.cursor() as cur:
        for i,(ck,v) in enumerate(rows):
            cid = secrets.token_urlsafe(8)
            page = ck.get("page")
            chunk_idx = ck.get("chunk", i)
            cur.execute(
                f"""INSERT INTO rag_docs (id, username, project, file_id, filename, page, chunk, text, embedding, ts)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s, %s::vector({EMBED_DIM}), %s)
                """,
                (cid, username, project, file_id, filename, page, chunk_idx, ck["text"], _vec_literal(v), ts)
            )
            added += 1
    return added

def rag_search_pg(username: str, project: str, query: str, top_k=4) -> Dict[str,Any]:
    if not PG_ENABLED:
        return {"ok": False, "reason":"pg_disabled"}
    qv = embed_texts([query])[0]
    lit = _vec_literal(qv)
    rows=[]
    with pg_conn() as c, c.cursor() as cur:
        cur.execute(
            f"""SELECT id, file_id, filename, page, chunk, text, (embedding <=> { '%s' }::vector({EMBED_DIM})) AS cos_dist
                FROM rag_docs
                WHERE username=%s AND project=%s
                ORDER BY embedding <=> { '%s' }::vector({EMBED_DIM})
                LIMIT %s;""",
            (lit, username, project, lit, top_k)
        )
        for id_, file_id, fn, page, chunk, text, dist in cur.fetchall():
            rows.append({"id": id_, "text": text, "metadata": {"file_id": file_id, "filename": fn, "page": page, "chunk": chunk}, "score": round(1.0 - float(dist), 4)})
    return {"ok": True, "matches": rows, "backend":"pgvector", "total": None}

def rag_list_pg(username: str, project: str, limit=50) -> Dict[str,Any]:
    out=[]
    files=[]
    with pg_conn() as c, c.cursor() as cur:
        cur.execute("SELECT count(*) FROM rag_docs WHERE username=%s AND project=%s;", (username, project))
        total = int(cur.fetchone()[0])
        cur.execute("""SELECT id, file_id, filename, page, chunk, left(text, 240)
                       FROM rag_docs WHERE username=%s AND project=%s
                       ORDER BY ts DESC LIMIT %s;""", (username, project, limit))
        for id_, fid, fn, page, chunk, txt in cur.fetchall():
            out.append({"id": id_, "text": txt, "metadata":{"file_id":fid,"filename":fn,"page":page,"chunk":chunk}})
        cur.execute("""SELECT file_id, filename, count(*), max(ts)
                       FROM rag_docs WHERE username=%s AND project=%s
                       GROUP BY file_id, filename
                       ORDER BY max(ts) DESC;""", (username, project))
        for fid, fn, cnt, ts in cur.fetchall():
            files.append({"file_id": fid, "filename": fn, "chunks": int(cnt), "ts": int(ts)})
    return {"ok": True, "total": total, "sample": out, "files": files}

def rag_delete_file_pg(username: str, project: str, file_id: str) -> Dict[str,Any]:
    with pg_conn() as c, c.cursor() as cur:
        cur.execute("WITH del AS (DELETE FROM rag_docs WHERE username=%s AND project=%s AND file_id=%s RETURNING 1) SELECT count(*) FROM del;", (username, project, file_id))
        n = int(cur.fetchone()[0])
    return {"ok": True, "removed": n}

def rag_clear_pg(username: str, project: str) -> int:
    with pg_conn() as c, c.cursor() as cur:
        cur.execute("WITH del AS (DELETE FROM rag_docs WHERE username=%s AND project=%s RETURNING 1) SELECT count(*) FROM del;", (username, project))
        return int(cur.fetchone()[0])

# ---- Redis RAG (existing)
def rag_index_redis(username: str, project: str, file_id: str, filename: str, chunks: List[Dict[str,Any]]) -> int:
    if not r: return 0
    vecs = embed_texts([c["text"] for c in chunks])
    pipe = r.pipeline()
    added=0
    for i,(ck,vec) in enumerate(zip(chunks, vecs)):
        row = {
            "id": secrets.token_urlsafe(6),
            "text": ck["text"],
            "meta": {"filename": filename, "chunk": ck.get("chunk", i), "file_id": file_id, "page": ck.get("page")},
            "vec": vec
        }
        pipe.rpush(k_rag_docs(username, project), json.dumps(row))
        added += 1
    pipe.execute()
    r.ltrim(k_rag_docs(username, project), -5000, -1)
    meta = {"file_id": file_id, "filename": filename, "chunks": added, "ts": int(time.time())}
    r.hset(k_rag_files(username, project), file_id, json.dumps(meta))
    return added

def rag_search_redis(username: str, project: str, query: str, top_k=4) -> Dict[str,Any]:
    if not r: return {"ok": False, "reason":"no_redis"}
    qv = embed_texts([query])[0]
    items = r.lrange(k_rag_docs(username, project), 0, -1)
    scored=[]
    for raw in items:
        try:
            row=json.loads(raw); sc=_cos(qv, row.get("vec") or [])
            scored.append((sc,row))
        except Exception:
            pass
    scored.sort(key=lambda t:t[0], reverse=True)
    matches=[]
    for s,x in scored[:top_k]:
        meta=x.get("meta",{})
        matches.append({"score": round(float(s),4), "id": x.get("id"), "text": x.get("text"), "metadata": meta})
    return {"ok": True, "matches": matches, "backend":"redis", "total": len(items)}

def rag_list_redis(username: str, project: str, limit=50) -> Dict[str,Any]:
    if not r: return {"ok": False, "reason":"no_redis"}
    total = r.llen(k_rag_docs(username, project))
    sample = r.lrange(k_rag_docs(username, project), max(-limit, -total), -1)
    rows=[]
    for raw in sample:
        try:
            row=json.loads(raw)
            rows.append({"id":row.get("id"), "text":(row.get("text","")[:240]), "metadata": row.get("meta",{})})
        except Exception:
            pass
    files = []
    try:
        raw_map = r.hgetall(k_rag_files(username, project)) or {}
        for fid, meta in raw_map.items():
            try: files.append(json.loads(meta))
            except Exception: pass
        files.sort(key=lambda m: m.get("ts",0), reverse=True)
    except Exception:
        files = []
    return {"ok": True, "total": total, "sample": rows, "files": files}

def rag_delete_file_redis(username: str, project: str, file_id: str) -> Dict[str,Any]:
    if not r: return {"ok": False, "error":"no_redis"}
    all_items = r.lrange(k_rag_docs(username, project), 0, -1)
    keep=[]; removed=0
    for raw in all_items:
        try:
            row=json.loads(raw)
            if row.get("meta",{}).get("file_id") == file_id:
                removed += 1
            else:
                keep.append(raw)
        except Exception:
            keep.append(raw)
    pipe = r.pipeline()
    pipe.delete(k_rag_docs(username, project))
    if keep: pipe.rpush(k_rag_docs(username, project), *keep)
    pipe.hdel(k_rag_files(username, project), file_id)
    pipe.execute()
    return {"ok": True, "removed": removed}

def rag_clear_redis(username: str, project: str) -> int:
    if not r: return 0
    n = r.delete(k_rag_docs(username, project))
    r.delete(k_rag_files(username, project))
    return n or 0

# ---- RAG dispatcher
USE_PG = bool(PG_ENABLED)

def rag_index(username: str, project: str, file_id: str, filename: str, chunks: List[Dict[str,Any]]) -> int:
    return rag_index_pg(username, project, file_id, filename, chunks) if USE_PG else rag_index_redis(username, project, file_id, filename, chunks)

def rag_search(username: str, project: str, query: str, top_k=4) -> Dict[str,Any]:
    return rag_search_pg(username, project, query, top_k) if USE_PG else rag_search_redis(username, project, query, top_k)

def rag_list(username: str, project: str, limit=50) -> Dict[str,Any]:
    return rag_list_pg(username, project, limit) if USE_PG else rag_list_redis(username, project, limit)

def rag_delete_file(username: str, project: str, file_id: str) -> Dict[str,Any]:
    return rag_delete_file_pg(username, project, file_id) if USE_PG else rag_delete_file_redis(username, project, file_id)

def rag_clear(username: str, project: str) -> int:
    return rag_clear_pg(username, project) if USE_PG else rag_clear_redis(username, project)

# ---- tool planner (adds project + citations with page)
def tool_loop(model: str, user_msg: str, username: str, project: str, preset: str, max_hops=5) -> Dict[str,Any]:
    if not moderate_text(user_msg):
        return {"reply":"I can’t help with that request.", "traces":[{"tool":"moderation","result":{"flagged": True}}]}

    sys_prompt = PROMPT_PRESETS.get(preset, SYSTEM_PROMPT_DEFAULT)

    # dev mode shortcuts
    if not OPENAI_KEY:
        traces=[]; citations=[]
        if "weather" in user_msg.lower():
            city = user_msg.split()[-1]
            out = tool_weather(city); traces.append({"tool":"get_weather","args":{"city":city},"result":out})
            return {"reply": f"Temp in {out.get('city','?')}: {out.get('temperature_c','?')}°C", "traces":traces, "citations":[]}
        if "search" in user_msg.lower():
            out = tool_web(user_msg); traces.append({"tool":"web_search","args":{"query":user_msg},"result":out})
            return {"reply": out.get("summary") or out.get("heading") or "(no result)", "traces":traces, "citations":[]}
        if "rag" in user_msg.lower() or "doc" in user_msg.lower():
            res = rag_search(username, project, user_msg, 4); traces.append({"tool":"rag_search","result":res})
            cites = [{"id":m["id"], "meta": m.get("metadata",{})} for m in res.get("matches",[])]
            return {"reply": f"Top matches: {len(cites)}", "traces":traces, "citations": cites}
        return {"reply": f"(dev echo) {user_msg}", "traces":[], "citations":[]}

    from openai import OpenAI
    client = OpenAI(api_key=OPENAI_KEY, timeout=OPENAI_TIMEOUT/1000.0)
    messages = [{"role":"system","content": sys_prompt},{"role":"user","content": user_msg, "username": username, "project": project}]
    traces=[]; citations=[]; pt=0; ct=0

    for _ in range(max_hops):
        r0 = client.chat.completions.create(
            model=model,
            messages=[{"role":m["role"],"content":m["content"]} for m in messages],
            tools=OPENAI_TOOLS, tool_choice="auto", temperature=0.4)
        u = getattr(r0,"usage",None)
        if u: pt += int(getattr(u,"prompt_tokens",0)); ct += int(getattr(u,"completion_tokens",0))
        msg = r0.choices[0].message
        if not getattr(msg, "tool_calls", None):
            text = (msg.content or "").strip() or "(no reply)"
            if citations:
                src_lines=[]
                for i,c in enumerate(citations,1):
                    meta=c.get("meta",{})
                    fn = meta.get("filename") or c.get("id","")
                    pg = meta.get("page")
                    suffix = f" (p.{pg})" if pg else ""
                    src_lines.append(f"{i}. {fn}{suffix}")
                text += "\n\nSources:\n" + "\n".join(src_lines)
            return {"reply": text, "traces": traces, "citations": citations,
                    "usage":{"prompt_tokens":pt,"completion_tokens":ct}}

        for tc in msg.tool_calls:
            name = tc.function.name
            args = json.loads(tc.function.arguments or "{}")
            if name == "get_weather":   res = tool_weather(args.get("city",""))
            elif name == "web_search":  res = tool_web(args.get("query",""))
            elif name == "rag_search":
                res = rag_search(args.get("username") or username, args.get("project") or project, args.get("query",""), int(args.get("top_k") or 4))
                for m in res.get("matches",[]):
                    citations.append({"id": m["id"], "meta": m.get("metadata",{})})
            else: res = {"ok": False, "reason": f"unknown_tool:{name}"}
            traces.append({"tool":name,"args":args,"result":res})
            messages.append({"role":"assistant","content":"", "tool_calls":[tc]})
            messages.append({"role":"tool","content": json.dumps(res), "tool_call_id": tc.id, "name": name})

    return {"reply":"Planner hit hop limit. Try again with a simpler ask.", "traces":traces, "citations": citations}

# ---- auto summarizer (per project)
def maybe_summarize_history(username: str, project: str):
    if not r or not OPENAI_KEY: return
    items = r.lrange(k_history(username, project), 0, -1)
    if len(items) < 40: return
    first = items[:-20]
    try:
        convo = []
        for raw in first:
            o=json.loads(raw)
            convo.append(f"User: {o.get('message','')}\nAssistant: {o.get('reply','')}")
        blob = "\n\n".join(convo)[:8000]
        from openai import OpenAI
        client = OpenAI(api_key=OPENAI_KEY, timeout=OPENAI_TIMEOUT/1000.0)
        resp = client.chat.completions.create(
            model=DEFAULT_MODEL,
            messages=[
                {"role":"system","content":"Summarize this chat into a compact memory (<200 words), keep facts, goals, preferences."},
                {"role":"user","content": blob}
            ],
            temperature=0.2
        )
        summary = (resp.choices[0].message.content or "").strip()
        last20 = items[-20:]
        r.delete(k_history(username, project))
        r.rpush(k_history(username, project), json.dumps({"ts": time.time(), "message": "(memory)", "reply": summary, "memory": True}))
        for raw in last20: r.rpush(k_history(username, project), raw)
    except Exception:
        pass

# ---- pages
@app.get("/")
def home(): return send_from_directory(app.static_folder, "chat.html")
@app.get("/chat")
def chat_page(): return send_from_directory(app.static_folder, "chat.html")

# ---- diagnostics
@app.get("/routes")
def routes():
    out=[]
    for rule in app.url_map.iter_rules():
        out.append({"endpoint": rule.endpoint, "methods": sorted(m for m in rule.methods if m in {"GET","POST","OPTIONS"}), "rule": str(rule)})
    return jsonify(sorted(out, key=lambda r: r["rule"]))

@app.get("/debug/health")
def health():
    return jsonify({"ok": True, "commit": COMMIT, "redis": redis_ok(), "pg": PG_ENABLED, "model": DEFAULT_MODEL, "openai": bool(OPENAI_KEY)})

@app.get("/api/metrics")
def metrics():
    scope = client_scope()
    allowed, remaining, reset = rate_limit_check(scope)
    return jsonify({"rate_limit":{"allowed":allowed,"remaining":remaining,"reset":reset},"backend":"pgvector" if USE_PG else "redis"})

# ---- models + presets
@app.get("/api/models")
def list_models():
    u = request.args.get("username") or "guest"
    return jsonify({"active": get_user_model(u), "available": ["gpt-4o","gpt-4o-mini","gpt-4.1-mini","o3-mini"]})

@app.post("/api/model")
def set_model_api():
    body = request.get_json(silent=True) or {}
    u = (body.get("username") or "guest").strip() or "guest"
    m = (body.get("model") or "").strip()
    if not m: return jsonify({"error":"missing_model"}), 400
    set_user_model(u, m)
    return jsonify({"active": get_user_model(u)})

@app.get("/api/presets")
def presets_list():
    u = request.args.get("username") or "guest"
    return jsonify({"active": get_user_preset(u), "presets": list(PROMPT_PRESETS.keys())})

@app.post("/api/presets")
def presets_set():
    body = request.get_json(force=True) or {}
    u = (body.get("username") or "guest").strip()
    p = (body.get("preset") or "concise").strip()
    if p not in PROMPT_PRESETS: return jsonify({"error":"unknown_preset"}), 400
    set_user_preset(u, p)
    return jsonify({"active": p})

# ---- history
@app.get("/api/history")
def history_get():
    username = request.args.get("username") or "guest"
    project  = request.args.get("project") or PROJECT_DEFAULT
    return jsonify(get_history(username, project, limit=int(request.args.get("limit") or 200)))

@app.post("/api/history/clear")
def history_clear():
    body = request.get_json(silent=True) or {}
    n = clear_history((body.get("username") or "guest"), (body.get("project") or PROJECT_DEFAULT))
    return jsonify({"ok": True, "cleared": bool(n)})

# ---- chat (JSON)
@app.post("/api/chat")
def api_chat():
    allowed, remaining, reset = rate_limit_check(client_scope())
    if not allowed:
        return jsonify({"error":"rate_limited","retry_after": reset - int(time.time())}), 429
    data = request.get_json(force=True) or {}
    msg      = (data.get("message") or "").strip()
    username = (data.get("username") or "guest").strip() or "guest"
    project  = (data.get("project")  or PROJECT_DEFAULT).strip() or PROJECT_DEFAULT
    model    = (data.get("model")    or get_user_model(username)).strip()
    preset   = (data.get("preset")   or get_user_preset(username)).strip()
    if not msg: return jsonify({"error":"missing_message"}), 400
    out = tool_loop(model, msg, username, project, preset, max_hops=5)
    reply = out.get("reply","")
    append_history(username, project, msg, reply)
    maybe_summarize_history(username, project)
    return jsonify({**out, "rate_limit":{"remaining":remaining,"reset":reset}})

# ---- chat (SSE with tool events)
def _sse(obj: Dict[str,Any]) -> str: return f"data: {json.dumps(obj, ensure_ascii=False)}\n\n"

@app.get("/api/chat/stream_tools")
def api_chat_stream_tools():
    allowed, _, _ = rate_limit_check(client_scope())
    if not allowed:
        return jsonify({"error":"rate_limited"}), 429

    message = (request.args.get("message") or "").strip()
    username= request.args.get("username") or "guest"
    project = request.args.get("project")  or PROJECT_DEFAULT
    model   = request.args.get("model")    or get_user_model(username)
    preset  = request.args.get("preset")   or get_user_preset(username)
    if not message: return jsonify({"error":"missing_message"}), 400

    def generate():
        out = tool_loop(model, message, username, project, preset, max_hops=5)
        traces = out.get("traces", [])
        for t in traces:
            yield _sse({"type":"tool_event","tool": t.get("tool"), "args": t.get("args"), "result": t.get("result")})
        reply = (out.get("reply") or "").strip() or "(no reply)"
        for ch in reply: yield _sse({"type":"delta","delta": ch}); time.sleep(0.004)
        if out.get("citations"): yield _sse({"type":"citations","citations": out["citations"]})
        if out.get("usage"):     yield _sse({"type":"usage","usage": out["usage"]})
        yield _sse({"type":"done"})
        append_history(username, project, message, reply)
        maybe_summarize_history(username, project)

    return Response(stream_with_context(generate()),
        headers={"Content-Type":"text/event-stream","Cache-Control":"no-cache","Connection":"keep-alive","X-Accel-Buffering":"no"})

# ---- RAG helpers to build chunk dicts (supports per-page)
def _mk_chunks_from_text(text: str, page: Optional[int]=None) -> List[Dict[str,Any]]:
    segs = _tok_chunk(text, target=900, overlap=200)
    out=[]
    for i, s in enumerate(segs):
        out.append({"text": s, "page": page, "chunk": i})
    return out

# ---- RAG endpoints
@app.post("/api/rag/index_text")
def rag_index_text():
    username = (request.get_json(force=True) or {}).get("username") or "guest"
    project  = (request.get_json(force=True) or {}).get("project")  or PROJECT_DEFAULT
    filename = (request.get_json(force=True) or {}).get("filename") or f"pasted-{int(time.time())}.txt"
    text     = (request.get_json(force=True) or {}).get("text") or ""
    if not text.strip(): return jsonify({"ok": False, "error":"missing_text"}), 400
    chunks = _mk_chunks_from_text(text.strip(), page=None)
    file_id = secrets.token_urlsafe(8)
    added = rag_index(username, project, file_id, filename, chunks)
    return jsonify({"ok": True, "added": added, "filename": filename, "file_id": file_id})

@app.post("/api/rag/upload")
def rag_upload():
    username = (request.form.get("username") or "guest").strip() or "guest"
    project  = (request.form.get("project")  or PROJECT_DEFAULT).strip() or PROJECT_DEFAULT
    if "files" not in request.files: return jsonify({"ok": False, "error":"missing_files"}), 400
    files = request.files.getlist("files")
    total=0; accepted={".txt",".md",".csv",".pdf",".docx"}; processed=[]

    for f in files:
        name = f.filename or f"upload-{secrets.token_urlsafe(4)}.txt"
        ext = "." + name.split(".")[-1].lower() if "." in name else ".txt"
        if ext not in accepted: continue
        rawb = f.read()
        chunks: List[Dict[str,Any]] = []
        if ext in {".txt",".md",".csv"}:
            text = rawb.decode("utf-8", errors="ignore")
            chunks = _mk_chunks_from_text(text, page=None)
        elif ext == ".pdf":
            pages = _read_pdf_pages(rawb)  # [{page:int,text:str}]
            for pg in pages:
                if not (pg.get("text") or "").strip(): continue
                chunks.extend(_mk_chunks_from_text(pg["text"], page=pg["page"]))
        elif ext == ".docx":
            try:
                import docx
                with open("/tmp/_up.docx","wb") as tmp: tmp.write(rawb)
                d = docx.Document("/tmp/_up.docx")
                text = "\n".join(p.text for p in d.paragraphs)
                chunks = _mk_chunks_from_text(text, page=None)
            except Exception:
                chunks = []

        if not chunks:
            processed.append({"filename":name, "added":0, "note":"no text extracted"})
            continue

        file_id = secrets.token_urlsafe(8)
        added = rag_index(username, project, file_id, name, chunks)
        total += added
        processed.append({"filename": name, "file_id": file_id, "added": added})

    return jsonify({"ok": True, "added": total, "files": processed, "backend": "pgvector" if USE_PG else "redis"})

@app.get("/api/rag/search")
def rag_http_search():
    username = (request.args.get("username") or "guest").strip() or "guest"
    project  = (request.args.get("project")  or PROJECT_DEFAULT).strip() or PROJECT_DEFAULT
    query    = (request.args.get("query") or "").strip()
    k        = int(request.args.get("k") or 4)
    if not query: return jsonify({"ok": False, "error":"missing_query"}), 400
    res = rag_search(username, project, query, k)
    return jsonify(res)

@app.get("/api/rag/list")
def rag_http_list():
    username = (request.args.get("username") or "guest").strip() or "guest"
    project  = (request.args.get("project")  or PROJECT_DEFAULT).strip() or PROJECT_DEFAULT
    lim      = int(request.args.get("limit") or 50)
    return jsonify(rag_list(username, project, lim))

@app.get("/api/rag/files")
def rag_http_files():
    username = (request.args.get("username") or "guest").strip() or "guest"
    project  = (request.args.get("project")  or PROJECT_DEFAULT).strip() or PROJECT_DEFAULT
    data = rag_list(username, project, limit=1_000)
    return jsonify({"ok": True, "files": data.get("files",[]) })

@app.post("/api/rag/delete_file")
def rag_http_delete_file():
    body     = request.get_json(force=True) or {}
    username = (body.get("username") or "guest").strip() or "guest"
    project  = (body.get("project")  or PROJECT_DEFAULT).strip() or PROJECT_DEFAULT
    file_id  = (body.get("file_id")  or "").strip()
    if not file_id: return jsonify({"ok": False, "error":"missing_file_id"}), 400
    res = rag_delete_file(username, project, file_id)
    return jsonify(res)

@app.post("/api/rag/clear")
def rag_http_clear():
    body     = request.get_json(silent=True) or {}
    username = (body.get("username") or "guest")
    project  = (body.get("project")  or PROJECT_DEFAULT)
    n = rag_clear(username, project)
    return jsonify({"ok": True, "cleared": bool(n), "removed": n})

@app.get("/api/rag/export_csv")
def rag_export_csv():
    username = (request.args.get("username") or "guest").strip() or "guest"
    project  = (request.args.get("project")  or PROJECT_DEFAULT).strip() or PROJECT_DEFAULT
    data = rag_list(username, project, limit=50_000)
    # stream CSV
    si = io.StringIO()
    w = csv.writer(si)
    w.writerow(["id","file_id","filename","page","chunk","text"])
    # best-effort: list() sample may be subset; fetch all when possible:
    if USE_PG:
        with pg_conn() as c, c.cursor() as cur:
            cur.execute("""SELECT id,file_id,filename,page,chunk,text FROM rag_docs
                           WHERE username=%s AND project=%s ORDER BY ts;""",(username, project))
            for row in cur.fetchall(): w.writerow(row)
    else:
        # redis has only the list; walk it
        items = r.lrange(k_rag_docs(username, project), 0, -1) if r else []
        for raw in items:
            try:
                o=json.loads(raw); meta=o.get("meta",{})
                w.writerow([o.get("id",""), meta.get("file_id",""), meta.get("filename",""), meta.get("page"), meta.get("chunk"), (o.get("text","") or "").replace("\n"," ")])
            except Exception: pass

    out = make_response(si.getvalue())
    out.headers["Content-Type"] = "text/csv; charset=utf-8"
    out.headers["Content-Disposition"] = f'attachment; filename="{username}-{project}-rag.csv"'
    return out

# ---- static passthrough
@app.get("/static/<path:filename>")
def static_files(filename):
    return send_from_directory(app.static_folder, filename)

# ---- errors
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
    port = int(os.getenv("PORT","5000"))
    app.run(host="0.0.0.0", port=port, debug=(os.getenv("FLASK_ENV","").lower()!="production"), threaded=True)

































