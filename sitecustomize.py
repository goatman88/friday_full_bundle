# src/sitecustomize.py
import traceback, sys
try:
    from openai import OpenAI as _RealOpenAI
    import openai as _openai_module
except Exception as e:
    print("[sitecustomize] Could not import openai yet:", repr(e), file=sys.stderr)
else:
    def _OpenAI_wrapper(*args, **kwargs):
        print("[sitecustomize] OpenAI() called; kwargs keys:", list(kwargs.keys()), file=sys.stderr)
        if "proxies" in kwargs:
            print("[sitecustomize][FATAL] OpenAI() received proxies= (unsupported).", file=sys.stderr)
            print("[sitecustomize] kwargs:", kwargs, file=sys.stderr)
            traceback.print_stack(limit=50, file=sys.stderr)
            raise TypeError("Remove proxies=. If you need a proxy, pass an httpx.Client via http_client=.")
        return _RealOpenAI(*args, **kwargs)

    _openai_module.OpenAI = _OpenAI_wrapper
    print("[sitecustomize] Guard installed: OpenAI() wrapper active", file=sys.stderr)

