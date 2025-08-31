# app.py
import os, json, time, secrets
from datetime import datetime
from typing import List, Dict, Any, Optional, Generator

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

# third-party HTTP for tools
import requests

# ---------- App & config ----------
app = Flask(__name__, static_folder="static", template_folder="templates")
CORS(app)

COMMIT = (os.getenv("RENDER_GIT_COMMIT", "")[:7] or os.getenv("COMMIT", "") or "dev")
OPENAI_KEY = os.getenv("OPENAI_API_KEY", "")
DEFAULT_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
ADMIN_TOKEN = os.getenv("ADMIN_TOKEN", "")

# ---------- Redis (persistent history, tokens) ----------
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
        "mode": mode
    })

# ---------- Models ----------
@app.get("/api/models")
def list_models():
    available = ["gpt-4o", "gpt-4o-mini", "gpt-4.1-mini", "o3-mini"]
    username = request.args.get("username") or "guest"
    return jsonify({"active": active_model(username), "available": available})

@app.post("/api/model")
def set_model_api():
    data = request.get_json(silent=True) or {}
    model = str(data.get("model", "")).strip()
    if not model:
        return jsonify({"error": "missing_model"}), 400
    set_active_model(model, username=None)  # global
    return jsonify({"active": active_model()})

# ---------- Tool implementations ----------
def tool_weather_city(city: str) -> Dict[str, Any]:
    """Get simple current weather for a city via Open-Meteo APIs."""
    try:
        # 1) geocode
        g = requests.get(
            "https://geocoding-api.open-meteo.com/v1/search",
            params={"name": city, "count": 1},
            timeout=8
        )
        g.raise_for_status()
        gdata = g.json()
        if not gdata.get("results"):
            return {"ok": False, "reason": "city_not_found"}
        lat = gdata["results"][0]["latitude"]
        lon = gdata["results"][0]["longitude"]
        name = gdata["results"][0]["name"]
        country = gdata["results"][0].get("country", "")

        # 2) current weather
        w = requests.get(
            "https://api.open-meteo.com/v1/forecast",
            params={"latitude": lat, "longitude": lon, "current_weather": "true"},
            timeout=8
        )
        w.raise_for_status()
        wdata = w.json()
        cw = wdata.get("current_weather") or {}
        return {
            "ok": True,
            "city": f"{name}, {country}".strip(", "),
            "latitude": lat,
            "longitude": lon,
            "temperature_c": cw.get("temperature"),
            "windspeed_kmh": cw.get("windspeed"),
            "time": cw.get("time"),
            "raw": cw
        }
    except Exception as e:
        return {"ok": False, "reason": str(e)}

def tool_sysinfo() -> Dict[str, Any]:
    """Simple system info for debugging."""
    return {
        "ok": True,
        "server_time_utc": datetime.utcnow().isoformat() + "Z",
        "commit": COMMIT,
        "redis": redis_ok(),
        "model": active_model()
    }

def tool_web_search_ddg(query: str) -> Dict[str, Any]:
    """Lightweight web search via DuckDuckGo Instant Answer (no API key)."""
    try:
        res = requests.get(
            "https://api.duckduckgo.com/",
            params={"q": query, "format": "json", "no_html": 1, "skip_disambig": 1},
            timeout=8
        )
        res.raise_for_status()
        data = res.json()
        abstract = data.get("AbstractText") or ""
        heading = data.get("Heading") or ""
        related = [{"Text": r.get("Text"), "FirstURL": r.get("FirstURL")}
                   for r in (data.get("RelatedTopics") or [])[:5]
                   if isinstance(r, dict) and r.get("Text") and r.get("FirstURL")]
        return {"ok": True, "heading": heading, "summary": abstract, "related": related}
    except Exception as e:
        return {"ok": False, "reason": str(e)}

# tool registry for local direct-calls (dev echo or safety)
TOOL_REGISTRY = {
    "get_weather": tool_weather_city,
    "system_info": lambda: tool_sysinfo(),
    "web_search": tool_web_search_ddg,
}

# OpenAI tool schemas
OPENAI_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": "Get current weather for a city name.",
            "parameters": {
                "type": "object",
                "properties": {
                    "city": {"type": "string", "description": "City name, like 'Austin' or 'Paris'."}
                },
                "required": ["city"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": "Quick web search using DuckDuckGo Instant Answer for a concise summary and a few related links.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Your search query."}
                },
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
    }
]

# ---------- Chat helpers ----------
def openai_tool_calling(model: str, user_msg: str) -> Dict[str, Any]:
    """
    Tool-aware flow:
    - If OPENAI_KEY set: use function-calling loop (max 3 tool hops)
    - Else: simple heuristic direct-call (so tools still work locally)
    Returns: { reply, traces: [ ... ] }
    """
    traces: List[Dict[str, Any]] = []

    # No key? Heuristic: trigger tools by keywords
    if not OPENAI_KEY:
        lowered = user_msg.lower()
        if "weather" in lowered or "temperature" in lowered:
            city = user_msg.split()[-1]  # hilariously naive; good enough for dev
            out = tool_weather_city(city)
            traces.append({"tool": "get_weather", "args": {"city": city}, "result": out})
            if out.get("ok"):
                t = out.get("temperature_c")
                c = out.get("city")
                reply = f"Current temp in {c} is {t}°C (dev, approximate)."
            else:
                reply = f"Couldn’t get weather: {out.get('reason','unknown')}"
            return {"reply": reply, "traces": traces}

        if "search" in lowered or "lookup" in lowered:
            q = user_msg
            out = tool_web_search_ddg(q)
            traces.append({"tool": "web_search", "args": {"query": q}, "result": out})
            if out.get("ok"):
                h = out.get("heading") or "Result"
                s = out.get("summary") or "(no summary)"
                reply = f"{h}: {s}"
            else:
                reply = f"Search failed: {out.get('reason','unknown')}"
            return {"reply": reply, "traces": traces}

        # fall back to echo
        return {"reply": f"(dev echo) {user_msg}", "traces": traces}

    # With key: real function-calling
    from openai import OpenAI
    client = OpenAI(api_key=OPENAI_KEY)

    messages: List[Dict[str, Any]] = [
        {"role": "system", "content": "You are Friday AI. Use tools when helpful, cite concise facts, and keep answers tight."},
        {"role": "user", "content": user_msg},
    ]

    for hop in range(3):
        resp = client.chat.completions.create(
            model=model,
            messages=messages,
            tools=OPENAI_TOOLS,
            tool_choice="auto",
            temperature=0.5,
        )
        msg = resp.choices[0].message

        # if the model responded normally, return it
        if not getattr(msg, "tool_calls", None):
            reply_text = (msg.content or "").strip()
            return {"reply": reply_text or "(no reply)", "traces": traces}

        # otherwise, execute tool calls
        for tc in msg.tool_calls:
            name = tc.function.name
            args = {}
            try:
                args = json.loads(tc.function.arguments or "{}")
            except Exception:
                args = {}
            # run local tool
            if name == "get_weather":
                res = tool_weather_city(args.get("city", ""))
            elif name == "web_search":
                res = tool_web_search_ddg(args.get("query", ""))
            elif name == "system_info":
                res = tool_sysinfo()
            else:
                res = {"ok": False, "reason": f"unknown_tool:{name}"}

            traces.append({"tool": name, "args": args, "result": res})

            # add tool result back to conversation
            messages.append({
                "role": "assistant",
                "tool_calls": [tc],  # echo the call we just handled
            })
            messages.append({
                "role": "tool",
                "tool_call_id": tc.id,
                "name": name,
                "content": json.dumps(res, ensure_ascii=False),
            })

    # safety fallback after hops exhausted
    return {"reply": "I tried tools but couldn’t finish. Try rephrasing.", "traces": traces}

def openai_nonstream_reply(model: str, message: str) -> str:
    if not OPENAI_KEY:
        return f"(dev echo) {message}"
    try:
        from openai import OpenAI
        client = OpenAI(api_key=OPENAI_KEY)
        resp = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "You are Friday AI. Be concise, friendly, and helpful."},
                {"role": "user", "content": message}
            ],
            temperature=0.6,
        )
        return (resp.choices[0].message.content or "").strip()
    except Exception as e:
        return f"[upstream_error] {e}"

# ---------- Chat (non-stream, tool-aware) ----------
@app.post("/api/chat")
def api_chat():
    data = request.get_json(force=True, silent=True) or {}
    message = str(data.get("message", "")).strip()
    username = str(data.get("username") or "guest")
    model = str(data.get("model") or active_model(username))
    use_tools = bool(data.get("tools", True))  # default ON

    if not message:
        return jsonify({"error": "missing_message"}), 400

    if use_tools:
        result = openai_tool_calling(model, message)
        reply = result.get("reply", "")
        traces = result.get("traces", [])
    else:
        reply = openai_nonstream_reply(model, message)
        traces = []

    append_history(username, message, reply)
    return jsonify({"reply": reply, "traces": traces})

# ---------- Chat (STREAMING over SSE; no tools in stream path) ----------
def sse_event(payload: Dict[str, Any]) -> str:
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"

def stream_openai(model: str, message: str) -> Generator[str, None, str]:
    final_text = []
    if not OPENAI_KEY:
        demo = f"(dev echo) {message}"
        for ch in demo:
            final_text.append(ch)
            yield sse_event({"delta": ch})
            time.sleep(0.01)
        yield sse_event({"done": True})
        return "".join(final_text)

    from openai import OpenAI
    client = OpenAI(api_key=OPENAI_KEY)
    try:
        stream = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "You are Friday AI. Be concise, friendly, and helpful."},
                {"role": "user", "content": message}
            ],
            temperature=0.6,
            stream=True,
        )
        last_heartbeat = time.time()
        for chunk in stream:
            if time.time() - last_heartbeat > 10:
                yield ":keepalive\n\n"
                last_heartbeat = time.time()
            part = ""
            try:
                part = chunk.choices[0].delta.content or ""
            except Exception:
                part = ""
            if part:
                final_text.append(part)
                yield sse_event({"delta": part})
        yield sse_event({"done": True})
        return "".join(final_text)
    except Exception as e:
        yield sse_event({"error": str(e)})
        yield sse_event({"done": True})
        return f"[upstream_error] {e}"

@app.get("/api/chat/stream")
def api_chat_stream():
    message = (request.args.get("message") or "").strip()
    username = request.args.get("username") or "guest"
    model = request.args.get("model") or active_model(username)
    if not message:
        return jsonify({"error": "missing_message"}), 400

    @stream_with_context
    def generate():
        for chunk in stream_openai(model, message):
            yield chunk
        nonstream = openai_nonstream_reply(model, message)
        append_history(username, message, nonstream)

    headers = {
        "Content-Type": "text/event-stream",
        "Cache-Control": "no-cache, no-transform",
        "Connection": "keep-alive",
        "X-Accel-Buffering": "no",
    }
    return Response(generate(), headers=headers)

# ---------- History ----------
@app.get("/api/history")
def get_history_api():
    username = request.args.get("username") or "guest"
    items = get_history(username, limit=int(request.args.get("limit") or 200))
    return jsonify(items)

@app.get("/api/history/export")
def export_history():
    username = request.args.get("username") or "guest"
    items = get_history(username, limit=1000)
    payload = json.dumps(items, indent=2, ensure_ascii=False)
    return Response(
        payload, mimetype="application/json",
        headers={"Content-Disposition": f'attachment; filename="history_{username}.json"'}
    )

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
        r.set(k_admin_code(code), "1", ex=60*60*24)  # 24h
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




















