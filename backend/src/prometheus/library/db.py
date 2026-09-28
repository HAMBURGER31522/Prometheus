"""SQLite connection and schema management (PLAN 7.1, 15.4.1)."""

import sqlite3

from prometheus import paths

SCHEMA_VERSION = 5


SCHEMA_V1 = """
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


# Columns added after version 1, applied in place by init_db.
_ADDED_COLUMNS = (
    # Version 2: where the item lives in the readable library, plus AI metadata.
    ("library_path", "TEXT"),        # "<分类>/<日期 标题>", relative to the data dir
    ("tags", "TEXT"),                # JSON list of strings
    ("description", "TEXT"),         # one-sentence summary
    # Version 3 (PLAN 15.4.4): which engine produced the transcript, and why if it changed.
    ("transcript_source", "TEXT"),   # asr.json engine: bcut | funasr-onnx | faster-whisper | youtube-subtitles
    ("notice", "TEXT"),              # e.g. 「必剪不可用，已改用本地转写」
    # Version 4 (PLAN 15.4.6): subtitle correction ok | failed (NULL until it ran).
    ("subtitle_status", "TEXT"),
    # Version 5 (PLAN 15.4.11): where a long stage is, e.g. 「写作（第 3/10 章）」; cleared with each stage.
    ("stage_detail", "TEXT"),
)


def connect(data_dir) -> sqlite3.Connection:
    conn = sqlite3.connect(paths.db_path(data_dir), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(data_dir) -> None:
    conn = connect(data_dir)
    try:
        conn.executescript(SCHEMA_V1)
        existing = {row[1] for row in conn.execute("PRAGMA table_info(items)")}
        for name, kind in _ADDED_COLUMNS:
            if name not in existing:
                conn.execute(f"ALTER TABLE items ADD COLUMN {name} {kind}")
        if conn.execute("SELECT COUNT(*) FROM schema_version").fetchone()[0]:
            conn.execute("UPDATE schema_version SET version = ?", (SCHEMA_VERSION,))
        else:
            conn.execute("INSERT INTO schema_version (version) VALUES (?)", (SCHEMA_VERSION,))
        conn.commit()
    finally:
        conn.close()


def get_schema_version(conn) -> int:
    return conn.execute("SELECT version FROM schema_version LIMIT 1").fetchone()[0]


def mark_running_as_interrupted(data_dir) -> None:
    conn = connect(data_dir)
    try:
        conn.execute("UPDATE items SET status = 'interrupted' WHERE status = 'running'")
        # A mind map rerun clears mindmap_status; quitting mid-run leaves it pending.
        conn.execute(
            "UPDATE items SET mindmap_status = 'failed' WHERE status = 'done' AND mindmap_status IS NULL",
        )
        conn.commit()
    finally:
        conn.close()
