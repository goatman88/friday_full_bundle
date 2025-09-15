import os

# Basic config with sane defaults
FRIDAY_NAME = os.getenv("FRIDAY_NAME", "Friday")
API_TOKEN   = os.getenv("API_TOKEN", "")  # optional Bearer auth for write ops
ENV         = os.getenv("ENV", "prod")

# CORS
FRONTEND_ORIGIN = os.getenv("FRONTEND_ORIGIN", "*")  # replace with your site later

# OpenAI – make sure OPENAI_API_KEY is set in Render > Environment
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

# Health
COMMIT_SHA = os.getenv("RENDER_GIT_COMMIT", "")[:7]
