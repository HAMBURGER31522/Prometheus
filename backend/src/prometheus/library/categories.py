"""Category persistence (PLAN 7.1)."""

import sqlite3
from datetime import UTC, datetime

from prometheus.library.db import connect


def _now() -> str:
    return datetime.now(UTC).isoformat()


def list_categories(data_dir):
    conn = connect(data_dir)
    try:
        rows = conn.execute(
            "SELECT c.id, c.name, COUNT(i.id) AS count FROM categories c"
            " LEFT JOIN items i ON i.category_id = c.id AND i.status = 'done'"
            " GROUP BY c.id ORDER BY c.created_at, c.id"
        ).fetchall()
    finally:
        conn.close()
    return [dict(row) for row in rows]


def create_category(data_dir, name):
    conn = connect(data_dir)
    try:
        cursor = conn.execute(
            "INSERT INTO categories (name, created_at) VALUES (?, ?)", (name, _now()),
        )
        conn.commit()
    finally:
        conn.close()
    return cursor.lastrowid


def rename_category(data_dir, category_id, name):
    conn = connect(data_dir)
    try:
        conn.execute("UPDATE categories SET name = ? WHERE id = ?", (name, category_id))
        conn.commit()
    except sqlite3.IntegrityError:
        conn.rollback()
        raise
    finally:
        conn.close()


def item_count(data_dir, category_id) -> int:
    conn = connect(data_dir)
    try:
        return conn.execute(
            "SELECT COUNT(*) FROM items WHERE category_id = ?", (category_id,)
        ).fetchone()[0]
    finally:
        conn.close()


def delete_category(data_dir, category_id) -> None:
    conn = connect(data_dir)
    try:
        conn.execute("DELETE FROM categories WHERE id = ?", (category_id,))
        conn.commit()
    finally:
        conn.close()


def merge_category(data_dir, category_id, into_id) -> None:
    conn = connect(data_dir)
    try:
        conn.execute(
            "UPDATE items SET category_id = ? WHERE category_id = ?", (into_id, category_id),
        )
        conn.execute("DELETE FROM categories WHERE id = ?", (category_id,))
        conn.commit()
    finally:
        conn.close()


def ensure_category(data_dir, name):
    conn = connect(data_dir)
    try:
        row = conn.execute("SELECT id FROM categories WHERE name = ?", (name,)).fetchone()
        if row:
            return row[0]
        cursor = conn.execute(
            "INSERT INTO categories (name, created_at) VALUES (?, ?)", (name, _now()),
        )
        conn.commit()
        return cursor.lastrowid
    finally:
        conn.close()
