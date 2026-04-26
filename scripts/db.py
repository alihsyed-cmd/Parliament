"""
Database connection helper for the Parliament backend.

Provides a single shared psycopg2 connection used by all adapters and the
Flask API. Connection is lazily created on first use and reused across
queries to avoid the overhead of repeatedly establishing a new connection.

Future iterations may swap this for a connection pool (psycopg2.pool) when
deployment concurrency demands it.
"""

import os
from typing import Any, Optional

import psycopg2
from psycopg2.extensions import connection as PgConnection


_connection: Optional[PgConnection] = None


def get_connection() -> PgConnection:
    """Return the shared connection, creating it on first call."""
    global _connection

    if _connection is None or _connection.closed:
        db_url = os.getenv("SUPABASE_DB_URL")
        if not db_url:
            raise RuntimeError(
                "SUPABASE_DB_URL is not set. Cannot connect to database."
            )
        _connection = psycopg2.connect(
            db_url,
            keepalives=1,
            keepalives_idle=30,
            keepalives_interval=10,
            keepalives_count=5,
        )
        _connection.autocommit = True

    return _connection


def query(sql: str, params: tuple = ()) -> list[tuple[Any, ...]]:
    """Run a SELECT query and return all rows."""
    conn = get_connection()
    with conn.cursor() as cur:
        cur.execute(sql, params)
        return cur.fetchall()


def query_one(sql: str, params: tuple = ()) -> Optional[tuple[Any, ...]]:
    """Run a SELECT query and return the first row (or None)."""
    conn = get_connection()
    with conn.cursor() as cur:
        cur.execute(sql, params)
        return cur.fetchone()


def close_connection() -> None:
    """Close the shared connection. Useful for tests or shutdown."""
    global _connection
    if _connection is not None and not _connection.closed:
        _connection.close()
    _connection = None
