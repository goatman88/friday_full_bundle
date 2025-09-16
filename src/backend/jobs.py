# src/backend/jobs.py
from __future__ import annotations
import threading
import time
from typing import Dict, Optional, Any

_LOCK = threading.Lock()
_JOBS: Dict[str, Dict[str, Any]] = {}

def create(job_id: str, title: str = "") -> None:
    with _LOCK:
        _JOBS[job_id] = {
            "status": "queued",   # queued | processing | done | error
            "progress": 0,        # 0..100
            "message": "Queued",
            "title": title,
            "updated_at": time.time(),
        }

def set_status(job_id: str, status: str, message: str = "", progress: Optional[int] = None) -> None:
    with _LOCK:
        job = _JOBS.get(job_id)
        if not job:
            job = {}
            _JOBS[job_id] = job
        job["status"] = status
        if message:
            job["message"] = message
        if progress is not None:
            job["progress"] = max(0, min(100, int(progress)))
        job["updated_at"] = time.time()

def get(job_id: str) -> Optional[Dict[str, Any]]:
    with _LOCK:
        job = _JOBS.get(job_id)
        return dict(job) if job else None

def bump(job_id: str, delta: int, message: Optional[str] = None) -> None:
    with _LOCK:
        job = _JOBS.get(job_id)
        if not job:
            return
        job["progress"] = max(0, min(100, int(job.get("progress", 0) + delta)))
        if message is not None:
            job["message"] = message
        job["updated_at"] = time.time()
