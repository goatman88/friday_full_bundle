# backend/db.py
from __future__ import annotations
import os
from contextlib import contextmanager
from psycopg_pool import ConnectionPool

DATABASE_URL = os.environ.get("DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL is not set")

# Reasonable defaults for Render/Herokuish envs
pool = ConnectionPool(
    conninfo=DATABASE_URL,
    min_size=1,
    max_size=10,
    kwargs={
        "options": "-c statement_timeout=15000",  # 15s
    },
)

@contextmanager
def get_conn():
    with pool.connection() as conn:
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
