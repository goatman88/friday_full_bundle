# Friday API (Render)

## Deploy (Render)
1. Create a **Web Service** from this repo.
2. Environment:
   - Runtime: Python 3.11+
   - Build Command: `pip install -r requirements.txt`
   - Start Command: *(leave blank to use Procfile)* or set  
     `uvicorn src.app:app --host 0.0.0.0 --port $PORT`
3. Deploy. When live, verify in browser:
   - `https://<your-app>.onrender.com/api/health` → JSON `{"status":"ok",...}`
   - `https://<your-app>.onrender.com/docs`

## PowerShell client
See `friday-client.ps1` in this folder. Example:
```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\friday-client.ps1 -Base "https://<your-app>.onrender.com" -DoQuery:$true





