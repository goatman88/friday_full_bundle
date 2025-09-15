# backend/db.py
from __future__ import annotations
import os
from contextlib import contextmanager

DATABASE_URL = os.environ.get("DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL is not set")

_use_pool = True
try:
    from psycopg_pool import ConnectionPool   # installed via psycopg-pool
except Exception:
    _use_pool = False

import psycopg

if _use_pool:
    pool = ConnectionPool(
        conninfo=DATABASE_URL,
        min_size=1,
        max_size=10,
        kwargs={"options": "-c statement_timeout=15000"},
    )

    @contextmanager
    def get_conn():
        with pool.connection() as conn:
            yield conn
else:
    # Fallback: open/close per request. Fine for small traffic.
    @contextmanager
    def get_conn():
        with psycopg.connect(DATABASE_URL, options="-c statement_timeout=15000") as conn:
            yield conn

def fetchone(sql: str, params=None):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params or ())
            return cur.fetchone()

def fetchall(sql: str, params=None):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params or ())
            return cur.fetchall()

def execute(sql: str, params=None, many: bool=False):
    with get_conn() as conn:
        with conn.cursor() as cur:
            if many:
                cur.executemany(sql, params or [])
            else:
                cur.execute(sql, params or ())
        conn.commit()

