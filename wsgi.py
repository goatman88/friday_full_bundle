# src/wsgi.py
# Force-load our guard before importing the app
import sitecustomize  # noqa: F401

# Now import your Flask app
from app import app  # this must define `app = Flask(__name__)`
from app import app
if __name__ == "__main__":
    app.run()
