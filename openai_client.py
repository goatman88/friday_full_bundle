# src/openai_client.py
import os
import httpx
from openai import OpenAI

def make_openai_client() -> OpenAI:
    """
    Create an OpenAI v1 client. If a proxy is configured, we pass an httpx client
    via http_client=... (the supported way in openai>=1.x).

    ENV
    ----
    OPENAI_API_KEY        (required)
    OUTBOUND_HTTP_PROXY   (optional, preferred if you need a proxy)
    HTTPS_PROXY / HTTP_PROXY (optional, also supported)
    """
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not set")

    proxy = (
        os.getenv("OUTBOUND_HTTP_PROXY")
        or os.getenv("HTTPS_PROXY")
        or os.getenv("HTTP_PROXY")
    )

    if proxy:
        client = httpx.Client(
            proxies=proxy,
            timeout=httpx.Timeout(20.0, connect=10.0, read=20.0),
            transport=httpx.HTTPTransport(retries=3),
        )
        return OpenAI(api_key=api_key, http_client=client)

    return OpenAI(api_key=api_key)

