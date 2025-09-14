# src/sitecustomize.py
"""
Intercept OpenAI() constructor to detect accidental 'proxies=' usage.
This runs automatically on interpreter start if it's on PYTHONPATH.
"""

import traceback
import sys

try:
    # Import the real class first
    from openai import OpenAI as _RealOpenAI
    import openai as _openai_module
except Exception as e:
    print("[sitecustomize] Could not import openai yet:", repr(e), file=sys.stderr)
else:
    def _OpenAI_wrapper(*args, **kwargs):
        # Log keys to prove what’s being passed
        print("[sitecustomize] OpenAI() called; kwargs keys:", list(kwargs.keys()), file=sys.stderr)
        if "proxies" in kwargs:
            # Loud, actionable message + full stack to the logs
            print("[sitecustomize][FATAL] Someone passed proxies= to OpenAI(). This SDK does NOT accept that kwarg.", file=sys.stderr)
            print("[sitecustomize] kwargs:", kwargs, file=sys.stderr)
            traceback.print_stack(limit=50, file=sys.stderr)
            raise TypeError("Do not pass proxies= to OpenAI(); use httpx.Client(..., proxies=...) and pass http_client= instead.")
        return _RealOpenAI(*args, **kwargs)

    # Monkeypatch the module’s symbol so any "from openai import OpenAI" after this uses our guard
    _openai_module.OpenAI = _OpenAI_wrapper
    print("[sitecustomize] Guard installed: OpenAI() wrapper active", file=sys.stderr)
