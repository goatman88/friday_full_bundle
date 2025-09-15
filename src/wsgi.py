# src/wsgi.py

from src.app import app  # import the Flask app instance

# Expose as WSGI callable
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)

