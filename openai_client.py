# src/openai_client.py
import os
import httpx
from openai import OpenAI

def make_openai_client() -> OpenAI:
    """
    Create a v1 OpenAI client. If a proxy is configured, we wrap an httpx client
    and pass it via http_client=... (the only supported way in openai>=1.x).
    Supported env vars:
      - OUTBOUND_HTTP_PROXY   (preferred)
      - HTTPS_PROXY / HTTP_PROXY (standard)
      - OPENAI_API_KEY        (required)
    """
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not set")

    # pick a proxy if one is defined
    proxy = (
        os.getenv("OUTBOUND_HTTP_PROXY")
        or os.getenv("HTTPS_PROXY")
        or os.getenv("HTTP_PROXY")
    )

    if proxy:
        # You can tune timeouts/retries here.
        http_client = httpx.Client(
            proxies=proxy,
            timeout=httpx.Timeout(20.0, connect=10.0, read=20.0),
            transport=httpx.HTTPTransport(retries=3),
        )
        return OpenAI(api_key=api_key, http_client=http_client)
    else:
        return OpenAI(api_key=api_key)
