from app import app

# Expose Flask app for waitress/gunicorn
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)

