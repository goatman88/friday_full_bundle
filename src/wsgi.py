"""
WSGI entrypoint for Render/Waitress.

We load the Flask app object from src/app.py and re-expose it as `app`
so `waitress-serve src.wsgi:app` works.
"""
from .app import app as app  # noqa: F401  (re-export for waitress)

# Optional: run locally with `python -m src.wsgi`
if __name__ == "__main__":
    import os
    from waitress import serve

    port = int(os.environ.get("PORT", "8080"))
    serve(app, listen=f"0.0.0.0:{port}")
