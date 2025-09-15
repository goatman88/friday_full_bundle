# src/wsgi.py
# WSGI module that waitress (or gunicorn) imports.
from src.app import create_app
app = create_app()
