"""Item persistence (PLAN 7.1)."""

import sqlite3
from datetime import UTC, datetime

from prometheus import paths
from prometheus.library.db import connect

_ITEM_FIELDS = {
    "platform", "video_id", "source_url", "source_title", "uploader", "duration_s",
    "report_title", "category_id", "figures", "status", "stage", "mindmap_status",
    "error_code", "error_message", "started_at", "finished_at",
}


def _now() -> str:
    return datetime.now(UTC).isoformat()


def create_item(data_dir, *, platform, video_id, source_url, figures=0, status="queued"):
    item_id = paths.new_item_id()
    for subdirectory in ("report", "mindmap", "subtitle", "work"):
        (paths.item_dir(data_dir, item_id) / subdirectory).mkdir(parents=True, exist_ok=True)
    conn = connect(data_dir)
    try:
        conn.execute(
            "INSERT INTO items (id, platform, video_id, source_url, figures, status,"
            " created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (item_id, platform, video_id, source_url, int(figures), status, _now()),
        )
        conn.commit()
    finally:
        conn.close()
    return item_id


def get_item(data_dir, item_id):
    conn = connect(data_dir)
    try:
        row = conn.execute("SELECT * FROM items WHERE id = ?", (item_id,)).fetchone()
    finally:
        conn.close()
    return dict(row) if row else None


def find_by_video(data_dir, platform, video_id):
    conn = connect(data_dir)
    try:
        row = conn.execute(
            "SELECT * FROM items WHERE platform = ? AND video_id = ?",
            (platform, video_id),
        ).fetchone()
    finally:
        conn.close()
    return dict(row) if row else None


def list_items(data_dir, status=None, category_id=None):
    query = "SELECT * FROM items"
    conditions, parameters = [], []
    if status is not None:
        conditions.append("status = ?")
        parameters.append(status)
    if category_id is not None:
        conditions.append("category_id = ?")
        parameters.append(category_id)
    if conditions:
        query += " WHERE " + " AND ".join(conditions)
    query += " ORDER BY created_at, id"
    conn = connect(data_dir)
    try:
        return [dict(row) for row in conn.execute(query, parameters)]
    finally:
        conn.close()


def update_item(data_dir, item_id, **fields):
    assignments, parameters = [], []
    for name, value in fields.items():
        if name not in _ITEM_FIELDS:
            raise ValueError(f"unknown item field: {name}")
        assignments.append(f"{name} = ?")
        parameters.append(value)
    if not assignments:
        return
    parameters.append(item_id)
    conn = connect(data_dir)
    try:
        conn.execute(f"UPDATE items SET {', '.join(assignments)} WHERE id = ?", parameters)
        conn.commit()
    except sqlite3.IntegrityError:
        conn.rollback()
        raise
    finally:
        conn.close()


def delete_item(data_dir, item_id):
    row = get_item(data_dir, item_id)
    if row is None:
        return None
    conn = connect(data_dir)
    try:
        conn.execute("DELETE FROM items WHERE id = ?", (item_id,))
        conn.commit()
    finally:
        conn.close()
    import shutil

    shutil.rmtree(paths.item_dir(data_dir, item_id), ignore_errors=True)
    return row
