# Minimal, import from module in the *current* folder (because we cd into src)
from app import app  # <- DO NOT prefix with "src."

# WSGI entry point object that Waitress will look for
# (Waitress accepts "wsgi:app" so this must be named "app")
# Nothing else needed here.


