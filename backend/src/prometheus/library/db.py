"""SQLite connection and schema management (PLAN 7.1)."""

import sqlite3

from prometheus import paths

SCHEMA_VERSION = 1

_SCHEMA = """
CREATE TABLE IF NOT EXISTS schema_version (version INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS categories (
  id         INTEGER PRIMARY KEY,
  name       TEXT NOT NULL UNIQUE,
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS items (
  id              TEXT PRIMARY KEY,
  platform        TEXT NOT NULL CHECK (platform IN ('bilibili','youtube')),
  video_id        TEXT NOT NULL,
  source_url      TEXT NOT NULL,
  source_title    TEXT,
  uploader        TEXT,
  duration_s      REAL,
  report_title    TEXT,
  category_id     INTEGER REFERENCES categories(id),
  figures         INTEGER NOT NULL,
  status          TEXT NOT NULL CHECK (status IN
                    ('queued','running','done','failed','cancelled','interrupted')),
  stage           TEXT,
  mindmap_status  TEXT CHECK (mindmap_status IN ('ok','failed')),
  error_code      TEXT,
  error_message   TEXT,
  created_at      TEXT NOT NULL,
  started_at      TEXT,
  finished_at     TEXT,
  UNIQUE (platform, video_id)
);
"""


def connect(data_dir) -> sqlite3.Connection:
    conn = sqlite3.connect(paths.db_path(data_dir), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(data_dir) -> None:
    conn = connect(data_dir)
    try:
        conn.executescript(_SCHEMA)
        has_version = conn.execute("SELECT COUNT(*) FROM schema_version").fetchone()[0]
        if not has_version:
            conn.execute(
                "INSERT INTO schema_version (version) VALUES (?)", (SCHEMA_VERSION,),
            )
        conn.commit()
    finally:
        conn.close()


def get_schema_version(conn) -> int:
    return conn.execute("SELECT version FROM schema_version LIMIT 1").fetchone()[0]


def mark_running_as_interrupted(data_dir) -> None:
    conn = connect(data_dir)
    try:
        conn.execute("UPDATE items SET status = 'interrupted' WHERE status = 'running'")
        conn.commit()
    finally:
        conn.close()
