import os
import httpx
from openai import OpenAI

def make_openai_client() -> OpenAI:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not set")

    proxy = (
        os.getenv("OUTBOUND_HTTP_PROXY")
        or os.getenv("HTTPS_PROXY")
        or os.getenv("HTTP_PROXY")
    )

    print("[openai_client] init", {
        "has_api_key": bool(api_key),
        "using_custom_httpx_client": bool(proxy),
        "proxy_env": "OUTBOUND_HTTP_PROXY" if os.getenv("OUTBOUND_HTTP_PROXY") else
                     "HTTPS_PROXY" if os.getenv("HTTPS_PROXY") else
                     "HTTP_PROXY" if os.getenv("HTTP_PROXY") else None,
    })

    if proxy:
        httpx_client = httpx.Client(
            proxies=proxy,
            timeout=httpx.Timeout(20.0, connect=10.0, read=20.0),
            transport=httpx.HTTPTransport(retries=3),
        )
        return OpenAI(api_key=api_key, http_client=httpx_client)

    return OpenAI(api_key=api_key)




