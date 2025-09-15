# This is the module waitress will import:
# Start Command:  waitress-serve --listen=0.0.0.0:$PORT wsgi:app

from app import create_app

app = create_app()


