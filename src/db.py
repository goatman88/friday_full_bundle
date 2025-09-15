from __future__ import annotations
import psycopg
from psycopg.rows import dict_row
from contextlib import asynccontextmanager, contextmanager
from . import settings

def get_conn():
    if not settings.DATABASE_URL:
        raise RuntimeError("DATABASE_URL is not set")
    # psycopg 3 simple connection (sync)
    return psycopg.connect(settings.DATABASE_URL, autocommit=True)

@contextmanager
def db() -> psycopg.Connection:
    conn = get_conn()
    try:
        yield conn
    finally:
        conn.close()
