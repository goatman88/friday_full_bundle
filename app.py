# app.py
import os, json, time, math, secrets
from datetime import datetime
from typing import List, Dict, Any, Optional, Generator, Tuple

# --- Load .env locally only ---
try:
    from dotenv import load_dotenv
    if (os.getenv("FLASK_ENV", "").lower() != "production"):
        load_dotenv(override=False)
except Exception:
    pass

from flask import (
    Flask, jsonify, request, send_from_directory,
    Response, stream_with_context
)
from flask_cors import CORS
import requests

# ---------- Optional Sentry ----------
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
    # don’t crash if sentry not installed
    pass

# ---------- App & config ----------
app = Flask(__name__, static_folder="static", template_folder="templates")
CORS(app)

COMMIT = (os.getenv("RENDER_GIT_COMMIT", "")[:7] or os.getenv("COMMIT", "") or "dev")
OPENAI_KEY = os.getenv("OPENAI_API_KEY", "")
DEFAULT_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
ADMIN_TOKEN = os.getenv("ADMIN_TOKEN", "")

# Embeddings (for RAG)
EMBED_MODEL = os.getenv("EMBED_MODEL", "text-embedding-3-small")

# Rate limit defaults (global, simple)
RL_WINDOW = int(os.getenv("RATE_LIMIT_WINDOW_SECONDS", "60"))  # seconds
RL_MAX = int(os.getenv("RATE_LIMIT_MAX", "60"))                # requests per window

# ---------- Redis (history, rate-limit, RAG store) ----------
r = None
try:
    REDIS_URL = os.getenv("REDIS_URL", "")
    if REDIS_URL:
        import redis  # pip install redis>=5
        r = redis.from_url(REDIS_URL, decode_responses=True)
except Exception:
    r = None

def redis_ok() -> bool:
    if not r: return False
    try: r.ping(); return True
    except Exception: return False

# ---------- Keys & helpers ----------
def k_history(username: str) -> str: return f"hist:{username}"
def k_model_active() -> str: return "model:active"
def k_user_model(username: str) -> str: return f"user:{username}:model"
def k_admin_code(code: str) -> str: return f"admin:code:{code}"
def k_user_authed(username: str) -> str: return f"user:{username}:authed"

def k_rl(scope: str) -> str: return f"rl:{scope}"
def k_rag_docs(username: str) -> str: return f"rag:{username}:docs"  # list of JSON {id,text,meta,vec}

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
    entry = {"ts": time.time(), "username": username, "message": message, "reply": reply}
    r.rpush(k_history(username), json.dumps(entry))
    r.ltrim(k_history(username), -500, -1)

def get_history(username: str, limit: int = 200) -> List[Dict[str, Any]]:
    if not r: return []
    entries = r.lrange(k_history(username), max(-limit, -500), -1)
    out: List[Dict[str, Any]] = []
    for raw in entries:
        try: out.append(json.loads(raw))
        except Exception: pass
    return out

def client_scope() -> str:
    """Use username if provided else IP. Good enough for basic RL."""
    uname = request.args.get("username") or (request.json or {}).get("username") if request.is_json else None
    if uname: return f"user:{uname}"
    fwd = request.headers.get("X-Forwarded-For", "") or request.remote_addr or "unknown"
    ip = fwd.split(",")[0].strip()
    return f"ip:{ip}"

def rate_limit_check(scope: str) -> Tuple[bool, int, int]:
    """
    Returns (allowed, remaining, reset_epoch_sec).
    Uses Redis INCR+EXPIRE. If no Redis, allow all.
    """
    if not r:  # soft-disable
        return (True, RL_MAX, int(time.time()) + RL_WINDOW)
    key = k_rl(scope)
    try:
        current = r.incr(key)
        ttl = r.ttl(key)
        if ttl < 0:  # no ttl yet
            r.expire(key, RL_WINDOW)
            ttl = RL_WINDOW
        remaining = max(0, RL_MAX - current)
        allowed = current <= RL_MAX
        reset = int(time.time()) + ttl
        return (allowed, remaining, reset)
    except Exception:
        return (True, RL_MAX, int(time.time()) + RL_WINDOW)

# ---------- Pages ----------
@app.get("/")
def home():
    return send_from_directory(app.static_folder, "chat.html")

@app.get("/chat")
def chat_page():
    return send_from_directory(app.static_folder, "chat.html")

# ---------- Diagnostics ----------
@app.get("/routes")
def routes():
    table = []
    for rule in app.url_map.iter_rules():
        table.append({
            "endpoint": rule.endpoint,
            "methods": sorted(m for m in rule.methods if m in {"GET","POST","OPTIONS"}),
            "rule": str(rule),
        })
    table = sorted(table, key=lambda r: r["rule"])
    return jsonify(table)

@app.get("/debug/health")
def health():
    mode = "live" if OPENAI_KEY else "dev_echo"
    return jsonify({
        "ok": True,
        "commit": COMMIT,
        "redis": redis_ok(),
        "model": active_model(),
        "openai": bool(OPENAI_KEY),
        "mode": mode,
        "rate_limit": {
            "window_seconds": RL_WINDOW,
            "max": RL_MAX,
            "enabled": bool(r)
        }
    })

# ---------- Models ----------
@app.get("/api/models")
def list_models():
    available = ["gpt-4o", "gpt-4o-mini", "gpt-4.1-mini", "o3-mini"]
    username = request.args.get("username") or "guest"
    return jsonify({"active": active_model(username), "available": available})

@app.post("/api/model")
def set_model_api():
    allowed, remaining, reset = rate_limit_check(client_scope())
    if not allowed:
        return jsonify({"error":"rate_limited","retry_after":reset - int(time.time())}), 429

    data = request.get_json(silent=True) or {}
    model = str(data.get("model", "")).strip()
    if not model:
        return jsonify({"error": "missing_model"}), 400
    set_active_model(model, username=None)  # global
    return jsonify({"active": active_model(), "rate_limit":{"remaining":remaining,"reset":reset}})

# ---------- HTTP retry helper ----------
def http_get(url: str, params: Dict[str, Any], timeout=8, tries=3, backoff=0.6) -> requests.Response:
    last_exc = None
    for i in range(tries):
        try:
            res = requests.get(url, params=params, timeout=timeout)
            # Retry on 5xx
            if res.status_code >= 500:
                raise requests.HTTPError(f"Server {res.status_code}")
            return res
        except Exception as e:
            last_exc = e
            time.sleep(backoff * (2**i))
    raise last_exc if last_exc else RuntimeError("request failed")

# ---------- Tools (with retries/backoff) ----------
def tool_weather_city(city: str) -> Dict[str, Any]:
    try:
        g = http_get("https://geocoding-api.open-meteo.com/v1/search",
                     {"name": city, "count": 1}, timeout=8, tries=3)
        gd = g.json()
        if not gd.get("results"): return {"ok": False, "reason": "city_not_found"}
        lat = gd["results"][0]["latitude"]; lon = gd["results"][0]["longitude"]
        name = gd["results"][0]["name"]; country = gd["results"][0].get("country","")

        w = http_get("https://api.open-meteo.com/v1/forecast",
                     {"latitude": lat, "longitude": lon, "current_weather": "true"}, timeout=8, tries=3)
        wd = w.json()
        cw = wd.get("current_weather") or {}
        return {
            "ok": True, "city": f"{name}, {country}".strip(", "),
            "latitude": lat, "longitude": lon,
            "temperature_c": cw.get("temperature"), "windspeed_kmh": cw.get("windspeed"),
            "time": cw.get("time"), "raw": cw
        }
    except Exception as e:
        return {"ok": False, "reason": str(e)}

def tool_sysinfo() -> Dict[str, Any]:
    return {"ok": True, "server_time_utc": datetime.utcnow().isoformat()+"Z",
            "commit": COMMIT, "redis": redis_ok(), "model": active_model()}

def tool_web_search_ddg(query: str) -> Dict[str, Any]:
    try:
        res = http_get("https://api.duckduckgo.com/",
                       {"q": query, "format": "json", "no_html": 1, "skip_disambig": 1},
                       timeout=8, tries=3)
        data = res.json()
        abstract = data.get("AbstractText") or ""
        heading = data.get("Heading") or ""
        related = [{"Text": r.get("Text"), "FirstURL": r.get("FirstURL")}
                   for r in (data.get("RelatedTopics") or [])[:5]
                   if isinstance(r, dict) and r.get("Text") and r.get("FirstURL")]
        return {"ok": True, "heading": heading, "summary": abstract, "related": related}
    except Exception as e:
        return {"ok": False, "reason": str(e)}

# ---------- RAG: embeddings via OpenAI ----------
def embed_texts(texts: List[str]) -> List[List[float]]:
    if not OPENAI_KEY:
        # Dev fallback: deterministic tiny hash embedding (terrible but unblocks flow)
        def cheap_vec(s: str, dim=64):
            v = [0.0]*dim
            for i,ch in enumerate(s.encode("utf-8")):
                v[i % dim] += (ch % 13) / 13.0
            # L2 normalize
            norm = math.sqrt(sum(x*x for x in v)) or 1.0
            return [x/norm for x in v]
        return [cheap_vec(t) for t in texts]

    from openai import OpenAI
    client = OpenAI(api_key=OPENAI_KEY)
    resp = client.embeddings.create(model=EMBED_MODEL, input=texts)
    return [d.embedding for d in resp.data]

def cosine(a: List[float], b: List[float]) -> float:
    if not a or not b: return 0.0
    s = sum(x*y for x,y in zip(a,b))
    na = math.sqrt(sum(x*x for x in a)) or 1.0
    nb = math.sqrt(sum(x*x for x in b)) or 1.0
    return s/(na*nb)

def rag_index(username: str, docs: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    docs: [{id, text, metadata?}]
    Stored in Redis list k_rag_docs(username) as JSON with 'vec'.
    """
    if not r:
        return {"ok": False, "reason": "redis_unavailable"}
    texts = [d.get("text","") for d in docs]
    vecs = embed_texts(texts)
    pipe = r.pipeline()
    for d, v in zip(docs, vecs):
        row = {"id": d.get("id") or secrets.token_urlsafe(6),
               "text": d.get("text",""),
               "meta": d.get("metadata", {}),
               "vec": v}
        pipe.rpush(k_rag_docs(username), json.dumps(row))
    pipe.execute()
    # keep last 2000 chunks
    r.ltrim(k_rag_docs(username), -2000, -1)
    return {"ok": True, "count": len(docs)}

def rag_search(username: str, query: str, top_k: int = 4) -> Dict[str, Any]:
    if not r: return {"ok": False, "reason": "redis_unavailable"}
    items = r.lrange(k_rag_docs(username), 0, -1)
    if not items: return {"ok": True, "matches": []}
    qvec = embed_texts([query])[0]
    scored = []
    for raw in items:
        try:
            row = json.loads(raw)
            sim = cosine(qvec, row.get("vec") or [])
            scored.append((sim, row))
        except Exception:
            pass
    scored.sort(key=lambda t: t[0], reverse=True)
    matches = [{"score": round(s,4), "id": r0["id"], "text": r0["text"], "metadata": r0.get("meta", {})}
               for s, r0 in scored[:max(1, min(top_k, 10))]]
    return {"ok": True, "matches": matches}

# Expose RAG as a tool
def tool_rag_search(username: str, query: str, top_k: int = 4) -> Dict[str, Any]:
    return rag_search(username, query, top_k)

# ---------- OpenAI tool schemas (including RAG) ----------
OPENAI_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": "Get current weather for a city name.",
            "parameters": {
                "type": "object",
                "properties": {"city": {"type": "string"}},
                "required": ["city"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": "Quick web search using DuckDuckGo Instant Answer.",
            "parameters": {
                "type": "object",
                "properties": {"query": {"type": "string"}},
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "system_info",
            "description": "Return server/system info and current active model.",
            "parameters": {"type": "object", "properties": {}}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "rag_search",
            "description": "Search the user's indexed documents and return the top matches for grounding.",
            "parameters": {
                "type": "object",
                "properties": {
                    "username": {"type": "string"},
                    "query": {"type": "string"},
                    "top_k": {"type": "integer", "minimum": 1, "maximum": 10}
                },
                "required": ["username", "query"]
            }
        }
    }
]

# ---------- Basic non-stream tool loop ----------
def openai_tool_calling(model: str, user_msg: str, username: str) -> Dict[str, Any]:
    # dev heuristics
    if not OPENAI_KEY:
        lw = user_msg.lower()
        if "weather" in lw:
            city = user_msg.split()[-1]
            out = tool_weather_city(city)
            if out.get("ok"):
                return {"reply": f"Temp in {out['city']}: {out['temperature_c']}°C",
                        "traces":[{"tool":"get_weather","args":{"city":city},"result":out}]}
            return {"reply": f"Weather failed: {out.get('reason','unknown')}", "traces":[]}
        if "search" in lw:
            out = tool_web_search_ddg(user_msg)
            if out.get("ok"):
                return {"reply": (out.get("summary") or out.get("heading") or "(no result)"),
                        "traces":[{"tool":"web_search","args":{"query":user_msg},"result":out}]}
        if "rag" in lw or "doc" in lw:
            out = rag_search(username, user_msg, 4)
            return {"reply": f"Top matches: {len(out.get('matches',[]))}", "traces":[{"tool":"rag_search","result":out}]}
        return {"reply": f"(dev echo) {user_msg}", "traces":[]}

    from openai import OpenAI
    client = OpenAI(api_key=OPENAI_KEY)
    messages = [
        {"role": "system", "content": "You are Friday AI. Use tools when helpful and keep answers tight."},
        {"role": "user", "content": user_msg},
    ]
    traces: List[Dict[str, Any]] = []

    for _ in range(3):
        resp = client.chat.completions.create(
            model=model, messages=messages, tools=OPENAI_TOOLS, tool_choice="auto", temperature=0.5
        )
        msg = resp.choices[0].message
        if not getattr(msg, "tool_calls", None):
            return {"reply": (msg.content or "").strip() or "(no reply)", "traces": traces}

        for tc in msg.tool_calls:
            name = tc.function.name
            args = json.loads(tc.function.arguments or "{}")
            if name == "get_weather":
                res = tool_weather_city(args.get("city",""))
            elif name == "web_search":
                res = tool_web_search_ddg(args.get("query",""))
            elif name == "system_info":
                res = tool_sysinfo()
            elif name == "rag_search":
                res = tool_rag_search(args.get("username") or username, args.get("query",""), int(args.get("top_k") or 4))
            else:
                res = {"ok": False, "reason": f"unknown_tool:{name}"}
            traces.append({"tool": name, "args": args, "result": res})
            messages.append({"role": "assistant", "tool_calls": [tc]})
            messages.append({"role": "tool", "tool_call_id": tc.id, "name": name, "content": json.dumps(res)})
    return {"reply": "I tried tools but couldn’t finish. Try rephrasing.", "traces": traces}

# ---------- Non-stream chat (tools) ----------
@app.post("/api/chat")
def api_chat():
    allowed, remaining, reset = rate_limit_check(client_scope())
    if not allowed:
        return jsonify({"error":"rate_limited","retry_after":reset - int(time.time())}), 429

    data = request.get_json(force=True, silent=True) or {}
    message = str(data.get("message", "")).strip()
    username = str(data.get("username") or "guest")
    model = str(data.get("model") or active_model(username))
    use_tools = bool(data.get("tools", True))
    if not message:
        return jsonify({"error": "missing_message"}), 400

    if use_tools:
        result = openai_tool_calling(model, message, username)
        reply = result.get("reply",""); traces = result.get("traces",[])
    else:
        reply = f"(dev echo) {message}"
        if OPENAI_KEY:
            try:
                from openai import OpenAI
                client = OpenAI(api_key=OPENAI_KEY)
                r0 = client.chat.completions.create(
                    model=model,
                    messages=[{"role":"system","content":"You are Friday AI."},{"role":"user","content": message}],
                    temperature=0.6
                )
                reply = (r0.choices[0].message.content or "").strip() or reply
            except Exception as e:
                reply = f"[upstream_error] {e}"
        traces = []

    append_history(username, message, reply)
    return jsonify({"reply": reply, "traces": traces, "rate_limit":{"remaining":remaining,"reset":reset}})

# ---------- SSE helpers (heartbeats) ----------
def sse(payload: Dict[str, Any]) -> str:
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"

def yield_heartbeat(last_hb: float, interval: float = 10.0) -> float:
    now = time.time()
    if now - last_hb > interval:
        yield ":keepalive\n\n"
        return now
    return last_hb

# ---------- Stream+Tools (SSE) ----------
@app.get("/api/chat/stream-tools")
def api_chat_stream_tools():
    allowed, remaining, reset = rate_limit_check(client_scope())
    if not allowed:
        return jsonify({"error":"rate_limited","retry_after":reset - int(time.time())}), 429

    user_msg = (request.args.get("message") or "").strip()
    username = request.args.get("username") or "guest"
    model = request.args.get("model") or active_model(username)
    if not user_msg:
        return jsonify({"error": "missing_message"}), 400

    @stream_with_context
    def generate():
        final_text_all = []
        if not OPENAI_KEY:
            demo = f"(dev echo) {user_msg}"
            for ch in demo: final_text_all.append(ch); yield sse({"type":"delta","delta": ch}); time.sleep(0.01)
            yield sse({"type":"done"})
            append_history(username, user_msg, "".join(final_text_all))
            return

        from openai import OpenAI
        client = OpenAI(api_key=OPENAI_KEY)
        messages: List[Dict[str, Any]] = [
            {"role":"system","content":"You are Friday AI. Call tools judiciously and keep answers tight."},
            {"role":"user","content": user_msg},
        ]

        for hop in range(3):
            stream = client.chat.completions.create(
                model=model, messages=messages, tools=OPENAI_TOOLS,
                tool_choice="auto", temperature=0.5, stream=True
            )
            tool_calls: Dict[int, Dict[str, Any]] = {}
            last_hb = time.time()

            try:
                for chunk in stream:
                    last_hb = (yield from (hb for hb in [yield_heartbeat(last_hb)] if hb is not None)) or last_hb
                    choice = chunk.choices[0]
                    delta = getattr(choice, "delta", None)

                    if delta and getattr(delta, "content", None):
                        piece = delta.content
                        final_text_all.append(piece)
                        yield sse({"type":"delta","delta": piece})

                    tcs = getattr(delta, "tool_calls", None)
                    if tcs:
                        for tc in tcs:
                            idx = getattr(tc, "index", 0)
                            tool_calls.setdefault(idx, {"id": None, "type":"function", "function":{"name": None, "arguments": ""}})
                            if getattr(tc, "id", None):
                                tool_calls[idx]["id"] = tc.id
                            fn = getattr(tc, "function", None)
                            if fn:
                                if getattr(fn, "name", None):
                                    tool_calls[idx]["function"]["name"] = fn.name
                                    yield sse({"type":"tool_call","name": fn.name})
                                if getattr(fn, "arguments", None):
                                    tool_calls[idx]["function"]["arguments"] += fn.arguments
            except Exception as e:
                yield sse({"type":"error","error": str(e)})
                yield sse({"type":"done"})
                append_history(username, user_msg, "".join(final_text_all) or f"[upstream_error] {e}")
                return

            if tool_calls:
                messages.append({"role":"assistant", "tool_calls": [
                    {
                        "id": call.get("id") or f"tc_{hop}_{idx}",
                        "type": "function",
                        "function": {
                            "name": call["function"]["name"],
                            "arguments": json.dumps(json.loads(call["function"]["arguments"] or "{}"))
                        }
                    }
                    for idx, call in sorted(tool_calls.items())
                ]})

                # Execute
                for idx, call in sorted(tool_calls.items()):
                    name = call["function"]["name"]
                    try:
                        args = json.loads(call["function"]["arguments"] or "{}")
                    except Exception:
                        args = {}

                    if name == "get_weather":
                        result = tool_weather_city(args.get("city",""))
                    elif name == "web_search":
                        result = tool_web_search_ddg(args.get("query",""))
                    elif name == "system_info":
                        result = tool_sysinfo()
                    elif name == "rag_search":
                        result = tool_rag_search(args.get("username") or username, args.get("query",""), int(args.get("top_k") or 4))
                    else:
                        result = {"ok": False, "reason": f"unknown_tool:{name}"}

                    yield sse({"type":"tool_result","name": name, "args": args, "result": result})
                    messages.append({
                        "role":"tool",
                        "tool_call_id": call.get("id") or f"tc_{hop}_{idx}",
                        "name": name,
                        "content": json.dumps(result, ensure_ascii=False)
                    })
                # loop again to let model integrate
                continue

            # no tool calls → done
            break

        yield sse({"type":"done"})
        final_text = "".join(final_text_all).strip() or "(no reply)"
        append_history(username, user_msg, final_text)

    headers = {
        "Content-Type": "text/event-stream",
        "Cache-Control": "no-cache, no-transform",
        "Connection": "keep-alive",
        "X-Accel-Buffering": "no",
    }
    return Response(generate(), headers=headers)

# ---------- Legacy streaming (no tools) ----------
def sse_event(payload: Dict[str, Any]) -> str:
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"

def stream_openai_plain(model: str, message: str) -> Generator[str, None, str]:
    final_text = []
    if not OPENAI_KEY:
        demo = f"(dev echo) {message}"
        for ch in demo: final_text.append(ch); yield sse_event({"delta": ch}); time.sleep(0.01)
        yield sse_event({"done": True}); return "".join(final_text)

    from openai import OpenAI
    client = OpenAI(api_key=OPENAI_KEY)
    stream = client.chat.completions.create(
        model=model,
        messages=[{"role":"system","content":"You are Friday AI."},{"role":"user","content": message}],
        temperature=0.6, stream=True
    )
    last_hb = time.time()
    for chunk in stream:
        last_hb = (yield from (hb for hb in [yield_heartbeat(last_hb)] if hb is not None)) or last_hb
        part = ""
        try: part = chunk.choices[0].delta.content or ""
        except Exception: part = ""
        if part:
            final_text.append(part)
            yield sse_event({"delta": part})
    yield sse_event({"done": True})
    return "".join(final_text)

@app.get("/api/chat/stream")
def api_chat_stream_plain():
    allowed, remaining, reset = rate_limit_check(client_scope())
    if not allowed:
        return jsonify({"error":"rate_limited","retry_after":reset - int(time.time())}), 429

    message = (request.args.get("message") or "").strip()
    username = request.args.get("username") or "guest"
    model = request.args.get("model") or active_model(username)
    if not message:
        return jsonify({"error": "missing_message"}), 400

    @stream_with_context
    def generate():
        for chunk in stream_openai_plain(model, message):
            yield chunk
        # Quick non-stream copy for history
        final_copy = f"(dev echo) {message}"
        if OPENAI_KEY:
            from openai import OpenAI
            client = OpenAI(api_key=OPENAI_KEY)
            try:
                r0 = client.chat.completions.create(
                    model=model,
                    messages=[{"role":"system","content":"You are Friday AI."},{"role":"user","content": message}],
                    temperature=0.6
                )
                final_copy = (r0.choices[0].message.content or "").strip() or final_copy
            except Exception:
                pass
        append_history(username, message, final_copy)

    headers = {
        "Content-Type": "text/event-stream",
        "Cache-Control": "no-cache, no-transform",
        "Connection": "keep-alive",
        "X-Accel-Buffering": "no",
    }
    return Response(generate(), headers=headers)

# ---------- RAG API ----------
@app.post("/api/rag/index")
def api_rag_index():
    allowed, remaining, reset = rate_limit_check(client_scope())
    if not allowed:
        return jsonify({"error":"rate_limited","retry_after":reset - int(time.time())}), 429

    data = request.get_json(silent=True) or {}
    username = str(data.get("username") or "guest")
    docs = data.get("docs")
    if not isinstance(docs, list) or not docs:
        return jsonify({"error":"missing_docs"}), 400
    res = rag_index(username, docs)
    return jsonify(res)

@app.post("/api/rag/query")
def api_rag_query():
    allowed, remaining, reset = rate_limit_check(client_scope())
    if not allowed:
        return jsonify({"error":"rate_limited","retry_after":reset - int(time.time())}), 429

    data = request.get_json(silent=True) or {}
    username = str(data.get("username") or "guest")
    query = str(data.get("query") or "").strip()
    top_k = int(data.get("top_k") or 4)
    if not query:
        return jsonify({"error":"missing_query"}), 400
    res = rag_search(username, query, top_k)
    return jsonify(res)

# ---------- Admin: mint & redeem ----------
def require_admin(req) -> bool:
    if not ADMIN_TOKEN: return False
    auth = req.headers.get("Authorization", "")
    if not auth.startswith("Bearer "): return False
    bearer = auth.split(" ", 1)[1].strip()
    return secrets.compare_digest(bearer, ADMIN_TOKEN)

@app.post("/api/admin/mint")
def admin_mint():
    if not require_admin(request):
        return jsonify({"error": "unauthorized"}), 401
    if not r:
        return jsonify({"error": "redis_unavailable"}), 503
    data = request.get_json(silent=True) or {}
    count = max(1, min(int(data.get("count") or 1), 20))
    tokens: List[str] = []
    for _ in range(count):
        code = secrets.token_urlsafe(8)
        r.set(k_admin_code(code), "1", ex=60*60*24)
        tokens.append(code)
    return jsonify({"tokens": tokens, "ttl_hours": 24})

@app.post("/api/auth/redeem")
def auth_redeem():
    if not r:
        return jsonify({"error": "redis_unavailable"}), 503
    data = request.get_json(silent=True) or {}
    code = str(data.get("code", "")).strip()
    username = str(data.get("username") or "guest")
    if not code:
        return jsonify({"error": "missing_code"}), 400
    key = k_admin_code(code)
    if not r.get(key):
        return jsonify({"success": False, "reason": "invalid_or_expired"}), 400
    r.delete(key)
    r.set(k_user_authed(username), "1", ex=60*60*24*30)
    return jsonify({"success": True, "user": username})

# ---------- Static passthrough ----------
@app.get("/static/<path:filename>")
def static_files(filename):
    return send_from_directory(app.static_folder, filename)

# ---------- API-friendly errors ----------
@app.errorhandler(404)
def not_found(_):
    if request.path.startswith("/api/"):
        return jsonify({"error": "not_found", "path": request.path}), 404
    return "Not Found", 404

@app.errorhandler(405)
def method_not_allowed(_):
    if request.path.startswith("/api/"):
        return jsonify({"error": "method_not_allowed", "path": request.path}), 405
    return "Method Not Allowed", 405

if __name__ == "__main__":
    port = int(os.getenv("PORT", "5000"))
    app.run(
        host="0.0.0.0",
        port=port,
        debug=(os.getenv("FLASK_ENV","").lower()!="production"),
        threaded=True
    )






















