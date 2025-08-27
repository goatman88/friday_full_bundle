# integrations/calendar_helper.py
from __future__ import annotations

from typing import List
from datetime import datetime, timedelta, timezone

from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials


def _make_creds(session_token: dict | None) -> Credentials | None:
    """
    Build google.oauth2.credentials.Credentials from the session dict we saved after OAuth.
    Returns None if we don't have a token yet (not logged in).
    """
    if not session_token:
        return None
    try:
        return Credentials(
            token=session_token.get("token"),
            refresh_token=session_token.get("refresh_token"),
            token_uri=session_token.get("token_uri"),
            client_id=session_token.get("client_id"),
            client_secret=session_token.get("client_secret"),
            scopes=session_token.get("scopes") or [],
        )
    except Exception:
        return None


def _fmt_time(iso_or_date: str) -> str:
    """
    Accepts either a dateTime (ISO) or all-day date.
    Returns a short, human-friendly time string.
    """
    try:
        if "T" in iso_or_date:
            # dateTime like 2025-08-20T13:00:00-04:00
            dt = datetime.fromisoformat(iso_or_date.replace("Z", "+00:00"))
            return dt.strftime("%H%M")
        else:
            # all-day date like 2025-08-20
            return "all-day"
    except Exception:
        return "time?"


def get_today_events(session_token: dict | None, max_results: int = 10) -> List[str]:
    """
    Returns a list of "HHMM – Title" (or "all-day – Title") for today's primary calendar.
    Empty list if not logged in or anything fails.
    """
    creds = _make_creds(session_token)
    if not creds:
        return []

    try:
        service = build("calendar", "v3", credentials=creds, cache_discovery=False)

        # Today (UTC window) — simple and robust
        now_utc = datetime.now(timezone.utc)
        start = now_utc.replace(hour=0, minute=0, second=0, microsecond=0)
        end = start + timedelta(days=1)

        events_result = service.events().list(
            calendarId="primary",
            timeMin=start.isoformat(),
            timeMax=end.isoformat(),
            singleEvents=True,
            orderBy="startTime",
            maxResults=max_results,
        ).execute()

        items = events_result.get("items", [])
        out: List[str] = []
        for e in items:
            start_any = e.get("start", {})
            start_str = start_any.get("dateTime") or start_any.get("date") or ""
            title = e.get("summary", "(no title)")
            out.append(f"{_fmt_time(start_str)} – {title}")
        return out
    except Exception:
        return []

