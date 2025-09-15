# wsgi.py — import the Flask app instance
from src.app import app  # <- do not change this import path

if __name__ == "__main__":
    # Useful for local testing; Render will use your Start Command
    app.run(host="0.0.0.0", port=8080)
