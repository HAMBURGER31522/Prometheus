"""SQLite schema, migrations and item/category persistence (PLAN 7.1)."""

import sqlite3

import pytest
from prometheus.library import categories as categories_store
from prometheus.library import db
from prometheus.library import items as items_store


@pytest.fixture
def data_dir(tmp_path):
    from prometheus import paths

    data_dir = tmp_path / "data"
    paths.init_data_dir(data_dir)
    db.init_db(data_dir)
    return data_dir


def test_schema_version_is_1(data_dir):
    conn = db.connect(data_dir)
    assert db.get_schema_version(conn) == 1


def test_items_table_columns(data_dir):
    conn = db.connect(data_dir)
    columns = {row[1] for row in conn.execute("PRAGMA table_info(items)")}
    expected = {
        "id", "platform", "video_id", "source_url", "source_title", "uploader",
        "duration_s", "report_title", "category_id", "figures", "status", "stage",
        "mindmap_status", "error_code", "error_message", "created_at", "started_at",
        "finished_at",
    }
    assert expected <= columns


def test_unique_platform_video_id(data_dir):
    items_store.create_item(data_dir, platform="bilibili", video_id="BV1xJYT6EEYc",
                            source_url="https://www.bilibili.com/video/BV1xJYT6EEYc/")
    with pytest.raises(sqlite3.IntegrityError):
        items_store.create_item(data_dir, platform="bilibili", video_id="BV1xJYT6EEYc",
                                source_url="https://www.bilibili.com/video/BV1xJYT6EEYc/")


def test_status_check_constraint(data_dir):
    with pytest.raises(sqlite3.IntegrityError):
        items_store.create_item(data_dir, platform="bilibili", video_id="BV1xJYT6EEYc",
                                source_url="u", status="bogus")


def test_category_count_only_counts_done(data_dir):
    category_id = categories_store.create_category(data_dir, "教学")
    done_item = items_store.create_item(data_dir, platform="bilibili", video_id="BV1aaaaaaaac",
                                        source_url="u1")
    queued_item = items_store.create_item(data_dir, platform="bilibili", video_id="BV1aaaaaaaad",
                                          source_url="u2")
    items_store.update_item(data_dir, done_item, category_id=category_id, status="done")
    items_store.update_item(data_dir, queued_item, category_id=category_id, status="queued")
    rows = {row["name"]: row["count"] for row in categories_store.list_categories(data_dir)}
    assert rows["教学"] == 1


def test_mark_running_as_interrupted(data_dir):
    items_store.create_item(data_dir, platform="bilibili", video_id="BV1aaaaaaaaae",
                            source_url="u", status="running")
    items_store.create_item(data_dir, platform="bilibili", video_id="BV1aaaaaaaafa",
                            source_url="u", status="queued")
    db.mark_running_as_interrupted(data_dir)
    conn = db.connect(data_dir)
    states = dict(conn.execute("SELECT video_id, status FROM items"))
    assert states["BV1aaaaaaaaae"] == "interrupted"
    assert states["BV1aaaaaaaafa"] == "queued"
