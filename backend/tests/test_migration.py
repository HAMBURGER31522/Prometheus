"""Legacy data dirs (items/<id>/...) migrate to the readable library (PLAN 15.4.1)."""

import sqlite3

from prometheus import paths
from prometheus.library import db
from prometheus.library.migrate import migrate_legacy_layout

DONE_ID = "d" * 32
FAILED_ID = "f" * 32


def _legacy_data_dir(root):
    """What M0–M8 wrote: db and config at the root, one folder per item id."""
    root.mkdir(parents=True)
    for relative in ("config/pi", "logs", "models", "runtime/cuda"):
        (root / relative).mkdir(parents=True)
    (root / "config" / "settings.json").write_text("{}", encoding="utf-8")
    conn = sqlite3.connect(root / "prometheus.db")
    conn.executescript(db.SCHEMA_V1)
    conn.execute("INSERT INTO schema_version (version) VALUES (1)")
    conn.execute("INSERT INTO categories (id, name, created_at) VALUES (1, '神秘学', 'now')")
    rows = [
        (DONE_ID, "BV1yPb46xExH", "done", "魔法卡巴拉导论：生命树", 1, "2026-09-26T19:47:43+00:00"),
        (FAILED_ID, "BV1xJYT6EEYc", "failed", None, None, None),
    ]
    for item_id, video, status, title, category, finished in rows:
        conn.execute(
            "INSERT INTO items (id, platform, video_id, source_url, source_title, report_title,"
            " category_id, figures, status, created_at, finished_at)"
            " VALUES (?, 'bilibili', ?, ?, ?, ?, ?, 0, ?, 'now', ?)",
            (item_id, video, f"https://www.bilibili.com/video/{video}/", title, title, category,
             status, finished),
        )
        item = root / "items" / item_id
        for sub in ("report", "mindmap", "subtitle", "work"):
            (item / sub).mkdir(parents=True)
        (item / "work" / "transcript.md").write_text("t", encoding="utf-8")
        (item / "subtitle" / "segments.json").write_text(
            '[{"start": 0.0, "end": 1.5, "text": "开场"}]', encoding="utf-8")
        if status == "done":
            (item / "report" / "report.html").write_text(
                "<html><body><h1>魔法卡巴拉导论：生命树</h1><p>正文</p></body></html>",
                encoding="utf-8")
            (item / "mindmap" / "mindmap.md").write_text("# 导图\n", encoding="utf-8")
            (item / "subtitle" / "subtitle.srt").write_text("1\n00:00:00,000 --> 00:00:01,500\n开场\n",
                                                             encoding="utf-8")
    conn.commit()
    conn.close()
    return root


def test_legacy_layout_moves_into_the_library(tmp_path):
    root = _legacy_data_dir(tmp_path / "data")
    assert migrate_legacy_layout(root) is True
    internal = root / ".prometheus"
    assert (internal / "prometheus.db").is_file() and not (root / "prometheus.db").exists()
    assert (internal / "config" / "settings.json").is_file()
    assert not (root / "items").exists()

    conn = db.connect(root)
    done = dict(conn.execute("SELECT * FROM items WHERE id = ?", (DONE_ID,)).fetchone())
    failed = dict(conn.execute("SELECT * FROM items WHERE id = ?", (FAILED_ID,)).fetchone())
    assert db.get_schema_version(conn) == 2
    assert done["library_path"] == "神秘学/2026-09-26 魔法卡巴拉导论：生命树"
    folder = root / done["library_path"]
    assert "正文" in (folder / "精读.html").read_text(encoding="utf-8")
    assert (folder / "思维导图.md").is_file() and (folder / "字幕.srt").is_file()
    assert failed["library_path"] is None
    for item_id in (DONE_ID, FAILED_ID):
        assert (paths.cache_dir(root, item_id) / "transcript.md").is_file()
        assert paths.segments_file(root, item_id).is_file()


def test_migration_is_idempotent(tmp_path):
    root = _legacy_data_dir(tmp_path / "data")
    assert migrate_legacy_layout(root) is True
    assert migrate_legacy_layout(root) is False
    assert (root / "神秘学").is_dir()


def test_a_fresh_library_is_left_alone(tmp_path):
    root = tmp_path / "data"
    paths.init_data_dir(root)
    assert migrate_legacy_layout(root) is False
