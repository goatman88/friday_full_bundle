# integrations/calendar_helper.py

from __future__ import annotations
from datetime import datetime, timedelta

# Return a small list of demo events for "today".
# Later we can swap this to real Google Calendar calls.
def get_today_events() -> list[dict]:
    now = datetime.now()
    today = now.date()

    def at(hh_mm: str) -> datetime:
        h, m = map(int, hh_mm.split(":"))
        return datetime(today.year, today.month, today.day, h, m)

    return [
        {"start": at("09:00"), "end": at("10:00"), "title": "Work block"},
        {"start": at("12:00"), "end": at("13:00"), "title": "Training + Run"},
        {"start": at("17:00"), "end": at("18:00"), "title": "Family time"},
    ]
