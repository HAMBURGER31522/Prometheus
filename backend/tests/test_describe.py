"""「补全标签和摘要」for items finished before tags existed (PLAN 15.4.10)."""

import json
import time

from conftest import BV_URL, wait_for_status
from prometheus import paths
from prometheus.library import categories as categories_store
from prometheus.library import items as items_store


def _finished_without_tags(client):
    item_id = client.post("/api/items", json={"url": BV_URL, "figures": False}).json()["id"]
    wait_for_status(client, item_id, "done")
    data_dir = client.app.state.data_dir
    chosen = categories_store.create_category(data_dir, "人工分类")
    assert client.patch(f"/api/items/{item_id}", json={"category_id": chosen}).status_code == 200
    items_store.update_item(data_dir, item_id, tags=None, description=None)
    return item_id, chosen


def _wait_for_tags(client, item_id, timeout=10.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        row = client.get(f"/api/items/{item_id}").json()
        if row.get("tags"):
            return row
        time.sleep(0.1)
    raise AssertionError("tags never arrived")


def test_filling_tags_keeps_the_category_and_rewrites_the_library_files(client):
    item_id, chosen = _finished_without_tags(client)
    response = client.post(f"/api/items/{item_id}/regenerate", json={"only": "tags"})
    assert response.status_code == 200
    assert response.json() == {"queued": True}
    row = _wait_for_tags(client, item_id)
    assert json.loads(row["tags"]) and row["description"]
    assert row["status"] == "done"
    assert row["category_id"] == chosen
    data_dir = client.app.state.data_dir
    md = (paths.library_folder(data_dir, row["library_path"]) / paths.LIBRARY_FILES["md"]).read_text(encoding="utf-8")
    assert json.loads(row["tags"])[0] in md
    index = json.loads((data_dir / "index.json").read_text(encoding="utf-8"))
    assert [entry["tags"] for entry in index["items"] if entry["id"] == item_id] == [json.loads(row["tags"])]
    trace = paths.work_dir(data_dir, item_id) / "run.trace.jsonl"
    events = [json.loads(line) for line in trace.read_text(encoding="utf-8").splitlines()]
    last_run = [e["stage"] for e in events if e["run"] == events[-1]["run"] and e["event"] == "start"]
    assert last_run == ["classify", "publish"]


def test_filling_tags_needs_a_finished_item(client):
    item_id, _ = _finished_without_tags(client)
    items_store.update_item(client.app.state.data_dir, item_id, status="failed")
    assert client.post(f"/api/items/{item_id}/regenerate", json={"only": "tags"}).status_code == 409
