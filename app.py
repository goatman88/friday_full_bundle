# app.py
import os, io, json, time, math, secrets, hashlib, uuid, csv
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple

# ---- env (local only) -------------------------------------------------------
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

# ---- app core ---------------------------------------------------------------
app = Flask(__name__, static_folder="static", template_folder="templates")
Compress(app)
CORS(app, resources={r"/*": {"origins": [o.strip() for o in os.getenv("CORS_ALLOW_ORIGINS","https://friday-o99e.onrender.com").split(",")]}})

COMMIT = (os.getenv("RENDER_GIT_COMMIT","")[:7] or os.getenv("COMMIT","") or "dev")
OPENAI_KEY = os.getenv("OPENAI_API_KEY","")
DEFAULT_MODEL = os.getenv("OPENAI_MODEL","gpt-4o-mini")

# prompt presets (can be changed per user via UI)
PROMPT_PRESETS = {
    "concise": "You are Friday: brief, clear, no fluff.",
    "teacher": "You are Friday the Coach: explain like I'm 5, step-by-step, with tiny examples.",
    "analyst": "You are Friday the Analyst: structured, bullet points, cite assumptions.",
    "drill":   "You are Friday the Drill Sergeant: motivating, blunt, but respectful. Keep it tight.",
}
SYSTEM_PROMPT_DEFAULT = os.getenv("PROMPT_SYSTEM", PROMPT_PRESETS["concise"])

EMBED_MODEL = os.getenv("EMBED_MODEL", "text-embedding-3-small")
EMBED_DIM = int(os.getenv("EMBED_DIM", "1536"))

# rate limit
RL_WINDOW = int(os.getenv("RATE_LIMIT_WINDOW_SECONDS", "60"))
RL_MAX    = int(os.getenv("RATE_LIMIT_MAX", "60"))

# OpenAI safety + fallback
FALLBACK_MODELS = [m.strip() for m in os.getenv("FALLBACK_MODELS","gpt-4o,gpt-4o-mini,o3-mini").split(",")]
OPENAI_TIMEOUT  = int(os.getenv("TIMEOUT_OPENAI_MS","12000"))

# ---- security headers -------------------------------------------------------
@app.after_request
def _secure_headers(resp):
    resp.headers["X-Content-Type-Options"] = "nosniff"
    resp.headers["X-Frame-Options"] = "DENY"
    resp.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    resp.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
    resp.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "script-src 'self'; "
        "style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data:; "
        "connect-src 'self' https://friday-o99e.onrender.com;"
    )
    if request.headers.get("X-Forwarded-Proto","") == "https":
        resp.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains; preload"
    return resp

# ---- structured request logging --------------------------------------------
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

# ---- Redis (history + RL + cache + vectors + files) -------------------------
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

def k_history(u):   return f"hist:{u}"
def k_rl(scope):    return f"rl:{scope}"
def k_user_preset(u): return f"user:{u}:preset"
def k_user_model(u):  return f"user:{u}:model"
def k_cache(pfx, k):  return f"cache:{pfx}:{k}"
def k_rag_docs(u):    return f"rag:{u}:docs"   # list of doc rows (chunks)
def k_rag_files(u):   return f"rag:{u}:files"  # hash: file_id -> meta json

def client_scope() -> str:
    uname = request.args.get("username") or ((request.json or {}).get("username") if request.is_json else None)
    if uname: return f"user:{uname}"
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

def append_history(username: str, message: str, reply: str):
    if not r: return
    r.rpush(k_history(username), json.dumps({"ts": time.time(), "message": message, "reply": reply}))
    r.ltrim(k_history(username), -500, -1)

def get_history(username: str, limit: int=200) -> List[Dict[str,Any]]:
    if not r: return []
    items = r.lrange(k_history(username), max(-limit, -500), -1)
    out=[]
    for raw in items:
        try: out.append(json.loads(raw))
        except Exception: pass
    return out

def clear_history(username: str) -> int:
    if not r: return 0
    return r.delete(k_history(username)) or 0

# ---- Token-aware chunking ---------------------------------------------------
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

# ---- OpenAI wrappers --------------------------------------------------------
def embed_texts(texts: List[str], model: Optional[str]=None) -> List[List[float]]:
    model = model or EMBED_MODEL
    if not OPENAI_KEY:
        # cheap local vector for dev mode
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
    pref = get_user_model(messages[0].get("username","guest")) if isinstance(messages, list) else DEFAULT_MODEL
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

# ---- tiny similarity + RAG store -------------------------------------------
def _cos(a: List[float], b: List[float]) -> float:
    s=sum(x*y for x,y in zip(a,b))
    na=math.sqrt(sum(x*x for x in a)) or 1.0
    nb=math.sqrt(sum(x*x for x in b)) or 1.0
    return s/(na*nb)

def rag_index(username: str, file_id: str, filename: str, chunks: List[str]) -> int:
    """Index all chunks for a file; write docs list + files hash."""
    if not r: return 0
    vecs = embed_texts(chunks)
    pipe = r.pipeline()
    added = 0
    for i, (txt, vec) in enumerate(zip(chunks, vecs)):
        row = {
            "id": secrets.token_urlsafe(6),
            "text": txt,
            "meta": {"filename": filename, "chunk": i, "file_id": file_id},
            "vec": vec
        }
        pipe.rpush(k_rag_docs(username), json.dumps(row))
        added += 1
    pipe.execute()
    # trim list, then update file meta
    r.ltrim(k_rag_docs(username), -5000, -1)
    meta = {"file_id": file_id, "filename": filename, "chunks": added, "ts": int(time.time())}
    r.hset(k_rag_files(username), file_id, json.dumps(meta))
    return added

def rag_search(username: str, query: str, top_k=4) -> Dict[str,Any]:
    if not r: return {"ok": False, "reason":"no_redis"}
    qv = embed_texts([query])[0]
    items = r.lrange(k_rag_docs(username), 0, -1)
    scored=[]
    for raw in items:
        try:
            row=json.loads(raw); sc=_cos(qv, row.get("vec") or [])
            scored.append((sc,row))
        except Exception:
            pass
    scored.sort(key=lambda t:t[0], reverse=True)
    matches=[{"score": round(s,4), "id": x["id"], "text": x["text"], "metadata": x.get("meta",{})} for s,x in scored[:top_k]]
    return {"ok": True, "matches": matches, "backend":"redis", "total": len(items)}

def rag_list(username: str, limit=50) -> Dict[str,Any]:
    if not r: return {"ok": False, "reason":"no_redis"}
    total = r.llen(k_rag_docs(username))
    sample = r.lrange(k_rag_docs(username), max(-limit, -total), -1)
    rows=[]
    for raw in sample:
        try:
            row=json.loads(raw)
            rows.append({"id":row.get("id"), "text":(row.get("text","")[:160]+"…") if len(row.get("text",""))>160 else row.get("text",""),
                         "metadata": row.get("meta",{})})
        except Exception:
            pass
    # files inventory
    files = {}
    try:
        raw_map = r.hgetall(k_rag_files(username)) or {}
        for fid, meta in raw_map.items():
            try: files[fid] = json.loads(meta)
            except Exception: pass
    except Exception:
        files = {}
    return {"ok": True, "total": total, "sample": rows, "files": list(files.values())}

def rag_clear(username: str) -> int:
    if not r: return 0
    n = r.delete(k_rag_docs(username))
    r.delete(k_rag_files(username))
    return n or 0

def rag_delete_file(username: str, file_id: str) -> Dict[str,Any]:
    """Remove all chunks with meta.file_id == file_id; rewrite list; drop file meta."""
    if not r: return {"ok": False, "error":"no_redis"}
    all_items = r.lrange(k_rag_docs(username), 0, -1)
    keep=[]
    removed=0
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
    pipe.delete(k_rag_docs(username))
    if keep:
        pipe.rpush(k_rag_docs(username), *keep)
    pipe.hdel(k_rag_files(username), file_id)
    pipe.execute()
    return {"ok": True, "removed": removed}

# ---- tiny cache helpers -----------------------------------------------------
def cache_get(prefix: str, key: str):
    if not r: return None
    return r.get(k_cache(prefix, key))

def cache_set(prefix: str, key: str, value: Any, ttl: int = 300):
    if not r: return
    r.setex(k_cache(prefix, key), ttl, json.dumps(value))

# ---- tools (weather / web / rag) -------------------------------------------
def http_get(url: str, params: Dict[str,Any], timeout=8, tries=3):
    import requests
    last=None
    for i in range(tries):
        try:
            res = requests.get(url, params=params, timeout=timeout)
            if res.status_code >= 500: raise Exception(f"{res.status_code}")
            return res
        except Exception as e:
            last=e; time.sleep(0.4*(2**i))
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

OPENAI_TOOLS = [
    {"type":"function","function":{"name":"get_weather","description":"Get current weather for a city.","parameters":{"type":"object","properties":{"city":{"type":"string"}},"required":["city"]}}},
    {"type":"function","function":{"name":"web_search","description":"DuckDuckGo instant answer","parameters":{"type":"object","properties":{"query":{"type":"string"}},"required":["query"]}}},
    {"type":"function","function":{"name":"rag_search","description":"Search user’s indexed docs for grounding","parameters":{"type":"object","properties":{"username":{"type":"string"},"query":{"type":"string"},"top_k":{"type":"integer","minimum":1,"maximum":10}},"required":["username","query"]}}}
]

# ---- tool planner (non-stream) with citations -------------------------------
def tool_loop(model: str, user_msg: str, username: str, preset: str, max_hops=5) -> Dict[str,Any]:
    if not moderate_text(user_msg):
        return {"reply":"I can’t help with that request.", "traces":[{"tool":"moderation","result":{"flagged": True}}]}
    sys_prompt = PROMPT_PRESETS.get(preset, SYSTEM_PROMPT_DEFAULT)

    if not OPENAI_KEY:
        traces=[]
        if "weather" in user_msg.lower():
            city = user_msg.split()[-1]
            out = tool_weather(city); traces.append({"tool":"get_weather","args":{"city":city},"result":out})
            reply = f"Temp in {out.get('city','?')}: {out.get('temperature_c','?')}°C"
            return {"reply": reply, "traces": traces, "citations":[]}

        if "search" in user_msg.lower():
            out = tool_web(user_msg); traces.append({"tool":"web_search","args":{"query":user_msg},"result":out})
            reply = out.get("summary") or out.get("heading") or "(no result)"
            return {"reply": reply, "traces": traces, "citations":[]}

        if "rag" in user_msg.lower() or "doc" in user_msg.lower():
            res = rag_search(username, user_msg, 4); traces.append({"tool":"rag_search","result":res})
            cites = [{"id":m["id"], "meta": m.get("metadata",{})} for m in res.get("matches",[])]
            return {"reply": f"Top matches: {len(cites)}", "traces":traces, "citations": cites}

        return {"reply": f"(dev echo) {user_msg}", "traces":[], "citations":[]}

    from openai import OpenAI
    client = OpenAI(api_key=OPENAI_KEY, timeout=OPENAI_TIMEOUT/1000.0)
    messages = [{"role":"system","content": sys_prompt},{"role":"user","content": user_msg, "username": username}]
    traces=[]; citations=[]; pt=0; ct=0

    for _ in range(max_hops):
        r0 = client.chat.completions.create(model=model, messages=[{"role":k,"content":v} for k,v in [(m["role"], m["content"]) for m in messages]], tools=OPENAI_TOOLS, tool_choice="auto", temperature=0.4)
        u = getattr(r0,"usage",None)
        if u: pt += int(getattr(u,"prompt_tokens",0)); ct += int(getattr(u,"completion_tokens",0))
        msg = r0.choices[0].message
        if not getattr(msg, "tool_calls", None):
            text = (msg.content or "").strip() or "(no reply)"
            if citations:
                src_lines=[]
                for i,c in enumerate(citations,1):
                    fn = c.get("meta",{}).get("filename") or c.get("id","")
                    src_lines.append(f"{i}. {fn}")
                text += "\n\nSources:\n" + "\n".join(src_lines)
            return {"reply": text, "traces": traces, "citations": citations,
                    "usage":{"prompt_tokens":pt,"completion_tokens":ct}}

        for tc in msg.tool_calls:
            name = tc.function.name
            args = json.loads(tc.function.arguments or "{}")
            if name == "get_weather":   res = tool_weather(args.get("city",""))
            elif name == "web_search":  res = tool_web(args.get("query",""))
            elif name == "rag_search":
                res = rag_search(args.get("username") or username, args.get("query",""), int(args.get("top_k") or 4))
                for m in res.get("matches",[]):
                    citations.append({"id": m["id"], "meta": m.get("metadata",{})})
            else: res = {"ok": False, "reason": f"unknown_tool:{name}"}
            traces.append({"tool":name,"args":args,"result":res})
            messages.append({"role":"assistant","content":"", "tool_calls":[tc]})
            messages.append({"role":"tool","content": json.dumps(res), "tool_call_id": tc.id, "name": name})

    return {"reply":"Planner hit hop limit. Try again with a simpler ask.", "traces":traces, "citations": citations}

# ---- auto-history summarizer ------------------------------------------------
def maybe_summarize_history(username: str):
    if not r or not OPENAI_KEY: return
    items = r.lrange(k_history(username), 0, -1)
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
            model=get_user_model(username),
            messages=[
                {"role":"system","content":"Summarize this chat into a compact memory (<200 words), keep facts, goals, preferences."},
                {"role":"user","content": blob}
            ],
            temperature=0.2
        )
        summary = (resp.choices[0].message.content or "").strip()
        last20 = items[-20:]
        r.delete(k_history(username))
        r.rpush(k_history(username), json.dumps({"ts": time.time(), "message": "(memory)", "reply": summary, "memory": True}))
        for raw in last20: r.rpush(k_history(username), raw)
    except Exception:
        pass

# ---- pages ------------------------------------------------------------------
@app.get("/")
def home(): return send_from_directory(app.static_folder, "chat.html")

@app.get("/chat")
def chat_page(): return send_from_directory(app.static_folder, "chat.html")

# ---- diagnostics ------------------------------------------------------------
@app.get("/routes")
def routes():
    out=[]
    for rule in app.url_map.iter_rules():
        out.append({"endpoint": rule.endpoint, "methods": sorted(m for m in rule.methods if m in {"GET","POST","OPTIONS"}), "rule": str(rule)})
    return jsonify(sorted(out, key=lambda r: r["rule"]))

@app.get("/debug/health")
def health():
    return jsonify({"ok": True, "commit": COMMIT, "redis": redis_ok(), "model": DEFAULT_MODEL, "openai": bool(OPENAI_KEY)})

@app.get("/api/metrics")
def metrics():
    scope = client_scope()
    allowed, remaining, reset = rate_limit_check(scope)
    return jsonify({"rate_limit":{"allowed":allowed,"remaining":remaining,"reset":reset},"model": get_user_model("guest")})

# ---- models + presets -------------------------------------------------------
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

# ---- history ----------------------------------------------------------------
@app.get("/api/history")
def history_get():
    return jsonify(get_history(request.args.get("username") or "guest", limit=int(request.args.get("limit") or 200)))

@app.post("/api/history/clear")
def history_clear():
    n = clear_history((request.get_json(silent=True) or {}).get("username") or "guest")
    return jsonify({"ok": True, "cleared": bool(n)})

# ---- chat (JSON) ------------------------------------------------------------
@app.post("/api/chat")
def api_chat():
    allowed, remaining, reset = rate_limit_check(client_scope())
    if not allowed:
        return jsonify({"error":"rate_limited","retry_after": reset - int(time.time())}), 429
    data = request.get_json(force=True) or {}
    msg = (data.get("message") or "").strip()
    username = (data.get("username") or "guest").strip() or "guest"
    model = (data.get("model") or get_user_model(username)).strip()
    preset = (data.get("preset") or get_user_preset(username)).strip()

    if not msg: return jsonify({"error":"missing_message"}), 400
    out = tool_loop(model, msg, username, preset, max_hops=5)
    reply = out.get("reply","")
    append_history(username, msg, reply)
    maybe_summarize_history(username)
    return jsonify({**out, "rate_limit":{"remaining":remaining,"reset":reset}})

# ---- chat (stream + tool-events) -------------------------------------------
def _sse(obj: Dict[str,Any]) -> str: return f"data: {json.dumps(obj, ensure_ascii=False)}\n\n"

@app.get("/api/chat/stream_tools")
def api_chat_stream_tools():
    allowed, _, _ = rate_limit_check(client_scope())
    if not allowed:
        return jsonify({"error":"rate_limited"}), 429

    message = (request.args.get("message") or "").strip()
    username = request.args.get("username") or "guest"
    model = request.args.get("model") or get_user_model(username)
    preset = request.args.get("preset") or get_user_preset(username)
    if not message: return jsonify({"error":"missing_message"}), 400

    def generate():
        out = tool_loop(model, message, username, preset, max_hops=5)
        traces = out.get("traces", [])
        for t in traces:
            yield _sse({"type":"tool_event","tool": t.get("tool"), "args": t.get("args"), "result": t.get("result")})
        reply = (out.get("reply") or "").strip() or "(no reply)"
        for ch in reply:
            yield _sse({"type":"delta","delta": ch}); time.sleep(0.004)
        if out.get("citations"):
            yield _sse({"type":"citations","citations": out["citations"]})
        if out.get("usage"):
            yield _sse({"type":"usage","usage": out["usage"]})
        yield _sse({"type":"done"})
        append_history(username, message, reply)
        maybe_summarize_history(username)

    return Response(stream_with_context(generate()),
        headers={"Content-Type":"text/event-stream","Cache-Control":"no-cache","Connection":"keep-alive","X-Accel-Buffering":"no"})

# ---- RAG: helpers to extract text from uploads ------------------------------
def _read_pdf_bytes(b: bytes) -> str:
    try:
        from pypdf import PdfReader
        with io.BytesIO(b) as bio:
            reader = PdfReader(bio)
            parts=[]
            for page in reader.pages:
                t = page.extract_text() or ""
                parts.append(t)
            return "\n".join(parts)
    except Exception as e:
        return ""

def _read_docx_bytes(b: bytes) -> str:
    try:
        import docx  # python-docx
        with open("/tmp/_up.docx","wb") as f: f.write(b)
        d = docx.Document("/tmp/_up.docx")
        return "\n".join(p.text for p in d.paragraphs)
    except Exception:
        return ""

# ---- RAG: REST endpoints ----------------------------------------------------
@app.post("/api/rag/index_text")
def rag_index_text():
    if not r: return jsonify({"ok": False, "error":"no_redis"}), 503
    data = request.get_json(force=True) or {}
    username = (data.get("username") or "guest").strip() or "guest"
    filename = (data.get("filename") or f"pasted-{int(time.time())}.txt").strip()
    text = (data.get("text") or "").strip()
    if not text: return jsonify({"ok": False, "error":"missing_text"}), 400
    chunks = _tok_chunk(text, target=900, overlap=200)
    file_id = secrets.token_urlsafe(8)
    added = rag_index(username, file_id, filename, chunks)
    return jsonify({"ok": True, "added": added, "filename": filename, "file_id": file_id})

@app.post("/api/rag/upload")
def rag_upload():
    """multipart form: username, files[] (.txt/.md/.csv/.pdf/.docx)"""
    if not r: return jsonify({"ok": False, "error":"no_redis"}), 503
    username = (request.form.get("username") or "guest").strip() or "guest"
    if "files" not in request.files: return jsonify({"ok": False, "error":"missing_files"}), 400
    files = request.files.getlist("files")
    total_added=0; accepted_ext={".txt",".md",".csv",".pdf",".docx"}
    processed=[]

    for f in files:
        name = f.filename or f"upload-{secrets.token_urlsafe(4)}.txt"
        ext = "." + name.split(".")[-1].lower() if "." in name else ".txt"
        if ext not in accepted_ext:
            continue
        rawb = f.read()
        text = ""
        if ext in {".txt",".md",".csv"}:
            text = rawb.decode("utf-8", errors="ignore")
        elif ext == ".pdf":
            text = _read_pdf_bytes(rawb)
        elif ext == ".docx":
            text = _read_docx_bytes(rawb)

        text = (text or "").strip()
        if not text: 
            processed.append({"filename":name, "added":0, "note":"no text extracted"})
            continue
        chunks = _tok_chunk(text, target=900, overlap=200)
        file_id = secrets.token_urlsafe(8)
        added = rag_index(username, file_id, name, chunks)
        total_added += added
        processed.append({"filename": name, "file_id": file_id, "added": added})

    return jsonify({"ok": True, "added": total_added, "files": processed})

@app.get("/api/rag/search")
def rag_http_search():
    if not r: return jsonify({"ok": False, "error":"no_redis"}), 503
    username = (request.args.get("username") or "guest").strip() or "guest"
    query = (request.args.get("query") or "").strip()
    k = int(request.args.get("k") or 4)
    if not query: return jsonify({"ok": False, "error":"missing_query"}), 400
    res = rag_search(username, query, k)
    return jsonify(res)

@app.get("/api/rag/list")
def rag_http_list():
    if not r: return jsonify({"ok": False, "error":"no_redis"}), 503
    username = (request.args.get("username") or "guest").strip() or "guest"
    lim = int(request.args.get("limit") or 50)
    return jsonify(rag_list(username, lim))

@app.get("/api/rag/files")
def rag_http_files():
    if not r: return jsonify({"ok": False, "error":"no_redis"}), 503
    username = (request.args.get("username") or "guest").strip() or "guest"
    raw = r.hgetall(k_rag_files(username)) or {}
    out=[]
    for fid, meta in raw.items():
        try: out.append(json.loads(meta))
        except Exception: pass
    out.sort(key=lambda m: m.get("ts",0), reverse=True)
    return jsonify({"ok": True, "files": out})

@app.post("/api/rag/delete_file")
def rag_http_delete_file():
    if not r: return jsonify({"ok": False, "error":"no_redis"}), 503
    body = request.get_json(force=True) or {}
    username = (body.get("username") or "guest").strip() or "guest"
    file_id = (body.get("file_id") or "").strip()
    if not file_id: return jsonify({"ok": False, "error":"missing_file_id"}), 400
    res = rag_delete_file(username, file_id)
    return jsonify(res)

@app.post("/api/rag/clear")
def rag_http_clear():
    if not r: return jsonify({"ok": False, "error":"no_redis"}), 503
    username = (request.get_json(silent=True) or {}).get("username") or "guest"
    n = rag_clear(username)
    return jsonify({"ok": True, "cleared": bool(n), "removed": n})

@app.get("/api/rag/export_csv")
def rag_export_csv():
    if not r: return jsonify({"ok": False, "error":"no_redis"}), 503
    username = (request.args.get("username") or "guest").strip() or "guest"
    items = r.lrange(k_rag_docs(username), 0, -1)
    si = io.StringIO()
    w = csv.writer(si)
    w.writerow(["id","file_id","filename","chunk","text"])
    for raw in items:
        try:
            row=json.loads(raw)
            meta=row.get("meta",{})
            w.writerow([row.get("id",""), meta.get("file_id",""), meta.get("filename",""), meta.get("chunk",""), row.get("text","").replace("\n"," ")])
        except Exception:
            pass
    out = make_response(si.getvalue())
    out.headers["Content-Type"] = "text/csv; charset=utf-8"
    out.headers["Content-Disposition"] = f'attachment; filename="{username}-rag.csv"'
    return out

# ---- static passthrough -----------------------------------------------------
@app.get("/static/<path:filename>")
def static_files(filename):
    return send_from_directory(app.static_folder, filename)

# ---- errors -----------------------------------------------------------------
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
































