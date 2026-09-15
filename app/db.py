"""Tiny DB layer: SQLite locally, Postgres (Neon) when DATABASE_URL is set.

Queries are written in SQLite style (`?` placeholders) and translated for Postgres.
"""
import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path

DATABASE_URL = os.environ.get("DATABASE_URL")
SQLITE_PATH = os.environ.get(
    "KARAOKE_DB", str(Path(__file__).resolve().parent.parent / "data" / "karaoke.db")
)
IS_PG = bool(DATABASE_URL)

SCHEMA = [
    """CREATE TABLE IF NOT EXISTS rooms (
        code TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        created_at DOUBLE PRECISION NOT NULL
    )""",
    """CREATE TABLE IF NOT EXISTS songs (
        id {pk},
        room TEXT NOT NULL,
        deezer_id BIGINT,
        title TEXT NOT NULL,
        artist TEXT NOT NULL,
        cover TEXT,
        preview TEXT,
        genre TEXT,
        added_by TEXT,
        added_by_name TEXT,
        created_at DOUBLE PRECISION NOT NULL,
        UNIQUE(room, deezer_id)
    )""",
    """CREATE TABLE IF NOT EXISTS votes (
        song_id INTEGER NOT NULL REFERENCES songs(id) ON DELETE CASCADE,
        user_id TEXT NOT NULL,
        created_at DOUBLE PRECISION NOT NULL,
        PRIMARY KEY (song_id, user_id)
    )""",
]


class Conn:
    """Uniform wrapper: execute(sql, params) -> cursor-like with fetchone/fetchall/lastrowid."""

    def __init__(self, raw):
        self.raw = raw

    def execute(self, sql: str, params: tuple = ()):
        if IS_PG:
            sql = sql.replace("?", "%s")
        cur = self.raw.execute(sql, params)
        return Cursor(cur)

    def insert_ignore(self, sql: str, params: tuple = ()):
        """INSERT that silently skips duplicates. `sql` is a plain INSERT statement."""
        if IS_PG:
            sql = sql.replace("?", "%s") + " ON CONFLICT DO NOTHING"
        else:
            sql = sql.replace("INSERT", "INSERT OR IGNORE", 1)
        self.raw.execute(sql, params)

    def insert_returning_id(self, sql: str, params: tuple = ()) -> int:
        if IS_PG:
            cur = self.raw.execute(sql.replace("?", "%s") + " RETURNING id", params)
            return cur.fetchone()["id"]
        return self.raw.execute(sql, params).lastrowid


class Cursor:
    def __init__(self, cur):
        self.cur = cur

    def fetchone(self):
        row = self.cur.fetchone()
        return dict(row) if row is not None else None

    def fetchall(self):
        return [dict(r) for r in self.cur.fetchall()]


@contextmanager
def db():
    if IS_PG:
        import psycopg
        from psycopg.rows import dict_row

        raw = psycopg.connect(DATABASE_URL, row_factory=dict_row)
    else:
        Path(SQLITE_PATH).parent.mkdir(parents=True, exist_ok=True)
        raw = sqlite3.connect(SQLITE_PATH)
        raw.row_factory = sqlite3.Row
    try:
        yield Conn(raw)
        raw.commit()
    except Exception:
        raw.rollback()
        raise
    finally:
        raw.close()


def init_db() -> None:
    pk = "BIGSERIAL PRIMARY KEY" if IS_PG else "INTEGER PRIMARY KEY AUTOINCREMENT"
    with db() as conn:
        for stmt in SCHEMA:
            conn.execute(stmt.format(pk=pk))
