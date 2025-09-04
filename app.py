import os
import json
from flask import Flask, request, jsonify
from flask_cors import CORS
from dotenv import load_dotenv

# ---------------------------
# Boot
# ---------------------------
load_dotenv()  # loads .env when running locally

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})

# ---------------------------
# OpenAI client (optional)
# ---------------------------
def make_openai():
    """
    Return an OpenAI client if OPENAI_API_KEY is present; else None.
    """
    key = os.getenv("OPENAI_API_KEY", "").strip()
    if not key:
        return None, False
    try:
        from openai import OpenAI
        client = OpenAI(api_key=key)
        return client, True
    except Exception:
        return None, False

# ---------------------------
# Helpers
# ---------------------------
SYSTEM_PROMPT = (
    "You are Friday, a calm, clear, Einstein-level reasoning assistant. "
    "You solve real-world problems, build stepwise plans, and call out assumptions. "
    "When asked to plan, produce: (1) Problem summary, (2) Plan in 3–5 concrete steps, "
    "(3) Prioritize the highest-leverage step first, (4) Retest/measure after each step, and iterate."
)

def local_brain_answer(user_message: str) -> str:
    """
    Deterministic local fallback (no OpenAI). Gives a short, structured plan.
    """
    msg = user_message.strip()
    if not msg:
        msg = "Help me move forward on my goal."
    plan = [
        "Plan: break the problem into 3–5 concrete steps",
        "Prioritize the highest-leverage step first",
        "Retest/measure after each step and iterate",
    ]
    return f"OpenAI unavailable; giving a fast local answer.\n\nProblem summary: {msg}\n" + "\n".join(plan)

# ---------------------------
# Routes
# ---------------------------
@app.get("/health")
def health():
    client, ok = make_openai()
    model = "gpt-4o-mini"
    return jsonify({"ok": True, "status": "running", "debug": {"key_present": ok, "model": model}})

@app.post("/chat")
def chat():
    try:
        data = request.get_json(force=True, silent=False) or {}
        user_message = (data.get("message") or "").strip()
        if not user_message:
            return jsonify({"ok": False, "error": "Missing 'message' in JSON body."}), 400

        # Try OpenAI first
        client, have_key = make_openai()
        if have_key and client:
            try:
                # Chat Completions (responses API)
                completion = client.chat.completions.create(
                    model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
                    messages=[
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": user_message},
                    ],
                    temperature=0.3,
                )
                reply = completion.choices[0].message.content
                return jsonify({"ok": True, "reply": reply, "used_openai": True})
            except Exception as e:
                # Fall back to local if OpenAI errors (bad key, quota, network, etc.)
                reply = local_brain_answer(user_message)
                return jsonify({
                    "ok": True,
                    "reply": reply,
                    "used_openai": False,
                    "debug": {"fallback_reason": repr(e)}
                })

        # No key present → local fallback
        reply = local_brain_answer(user_message)
        return jsonify({"ok": True, "reply": reply, "used_openai": False})

    except Exception as e:
        return jsonify({"ok": False, "error": "Unhandled error in /chat", "trace": repr(e)}), 500

# ---------------------------
# Local dev entrypoint
# ---------------------------
if __name__ == "__main__":
    # Local dev run: python app.py
    app.run(host="127.0.0.1", port=5000, debug=True)



































