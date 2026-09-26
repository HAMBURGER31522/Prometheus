"""Category and item operations keep the library folders in sync (PLAN 15.4.1)."""

import json
import shutil

from conftest import BV_URL, wait_for_status
from prometheus.library import categories as categories_store

OTHER_URL = "https://www.bilibili.com/video/BV1bTtb6uE7d/"


def _done(client, url=BV_URL):
    item_id = client.post("/api/items", json={"url": url, "figures": False}).json()["id"]
    row = wait_for_status(client, item_id, "done")
    assert row.get("library_path"), "library_path not recorded"
    return row


def _indexed_categories(client):
    index = json.loads((client.app.state.data_dir / "index.json").read_text(encoding="utf-8"))
    return {item["id"]: item["category"] for item in index["items"]}


def test_renaming_a_category_renames_its_folder(client):
    row = _done(client)
    data_dir = client.app.state.data_dir
    assert client.patch(f"/api/categories/{row['category_id']}", json={"name": "神秘学"}).status_code == 200
    moved = client.get(f"/api/items/{row['id']}").json()
    assert moved["library_path"].startswith("神秘学/")
    assert (data_dir / moved["library_path"] / "精读.html").is_file()
    assert not (data_dir / "未分类").exists()
    assert _indexed_categories(client)[row["id"]] == "神秘学"


def test_moving_an_item_moves_its_folder(client):
    row = _done(client)
    data_dir = client.app.state.data_dir
    target = categories_store.create_category(data_dir, "财政与经济")
    assert client.patch(f"/api/items/{row['id']}", json={"category_id": target}).status_code == 200
    moved = client.get(f"/api/items/{row['id']}").json()
    assert moved["library_path"].startswith("财政与经济/")
    assert (data_dir / moved["library_path"] / "精读.md").is_file()
    assert not (data_dir / row["library_path"]).exists()
    assert _indexed_categories(client)[row["id"]] == "财政与经济"


def test_merging_categories_moves_every_folder(client):
    first = _done(client)
    second = _done(client, OTHER_URL)
    data_dir = client.app.state.data_dir
    target = categories_store.create_category(data_dir, "历史")
    response = client.post(f"/api/categories/{first['category_id']}/merge", json={"into_id": target})
    assert response.status_code == 200
    for item_id in (first["id"], second["id"]):
        moved = client.get(f"/api/items/{item_id}").json()
        assert moved["library_path"].startswith("历史/")
        assert (data_dir / moved["library_path"]).is_dir()
    assert not (data_dir / "未分类").exists()


def test_a_folder_deleted_in_explorer_is_reported_missing(client):
    row = _done(client)
    shutil.rmtree(client.app.state.data_dir / row["library_path"])
    listed = next(item for item in client.get("/api/items").json() if item["id"] == row["id"])
    assert listed["files_missing"] is True
    report = client.get(f"/api/items/{row['id']}/report")
    assert report.status_code == 404
    assert report.json()["code"] == "FILES_MISSING"
