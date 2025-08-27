# quick check for your Google credentials.json
from pathlib import Path
import json

p = Path(__file__).resolve().parent / "credentials.json"
if not p.exists():
    print(f"ERROR: credentials.json not found at {p}")
    raise SystemExit(1)

print("credentials.json loaded successfully")
data = json.loads(p.read_text())
web = data.get("web", {})

print("\nClient ID :", web.get("client_id"))
print("Client Secret : ******")

print("\nRedirect URIs:")
for u in web.get("redirect_uris", []):
    print(" -", u)

print("\nJavascript Origins:")
for u in web.get("javascript_origins", []):
    print(" -", u)

print("\nSanity checks:")
print("- has expected redirect? ", any("oauth2callback" in u for u in web.get("redirect_uris", [])))
print("- has expected origin?   ", any("127.0.0.1:5000" in u or "localhost:5000" in u for u in web.get("javascript_origins", [])))
