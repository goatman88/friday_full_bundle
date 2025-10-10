from flask import Flask
from routes_chat import bp as chat_bp

def create_app():
    app = Flask(__name__)
    app.register_blueprint(chat_bp)
    return app

app = create_app()

if __name__ == "__main__":
    # Expose on LAN so your phone can reach it
    app.run(host="0.0.0.0", port=8000)
