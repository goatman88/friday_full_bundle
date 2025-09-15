# wsgi.py  (repo root)
from src.app import app  # your Flask app instance

# Optional: allow "python wsgi.py" locally
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080, debug=False)
