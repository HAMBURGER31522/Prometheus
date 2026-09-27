"""Item creation, listing, category move, delete, cancel and retry (PLAN 8.2)."""

from conftest import BV_URL, wait_for_status


def test_create_item_returns_201_and_queues(client):
    response = client.post("/api/items", json={"url": BV_URL, "figures": False})
    assert response.status_code == 201
    item_id = response.json()["id"]
    assert len(item_id) == 32
    row = client.get(f"/api/items/{item_id}").json()
    assert row["platform"] == "bilibili"
    assert row["video_id"] == "BV1xJYT6EEYc"
    assert row["status"] == "queued"


def test_duplicate_item_gets_409(client):
    first = client.post("/api/items", json={"url": BV_URL, "figures": False})
    second = client.post("/api/items", json={"url": BV_URL, "figures": False})
    assert second.status_code == 409
    assert second.json() == {"id": first.json()["id"]}


def test_unsupported_link_gets_422(client):
    response = client.post("/api/items", json={
        "url": "https://www.youtube.com/playlist?list=PL1234567890", "figures": False,
    })
    assert response.status_code == 422
    assert response.json() == {"code": "URL_UNSUPPORTED"}


def test_items_list_filters_by_status(client):
    from conftest import wait_for_status

    item_id = client.post("/api/items", json={"url": BV_URL, "figures": False}).json()["id"]
    wait_for_status(client, item_id, "done")
    done = client.get("/api/items", params={"status": "done"}).json()
    assert [row["id"] for row in done] == [item_id]
    queued = client.get("/api/items", params={"status": "queued"}).json()
    assert queued == []


def test_delete_removes_row_library_folder_and_cache(client, tmp_path):
    from conftest import wait_for_status
    from prometheus import paths

    created = client.post("/api/items", json={"url": BV_URL, "figures": False})
    item_id = created.json()["id"]
    row = wait_for_status(client, item_id, "done")
    data_dir = tmp_path / "data"
    assert row.get("library_path"), "library_path not recorded"
    folder = data_dir / row["library_path"]
    cache = paths.cache_dir(data_dir, item_id)
    assert folder.is_dir() and cache.is_dir()
    assert client.delete(f"/api/items/{item_id}").status_code == 204
    assert client.get(f"/api/items/{item_id}").status_code == 404
    assert not folder.exists()
    assert not cache.exists()


def test_patch_category_id(client):
    from prometheus.library import categories as categories_store

    category_id = categories_store.create_category(client.app.state.data_dir, "科技")
    created = client.post("/api/items", json={"url": BV_URL, "figures": False})
    item_id = created.json()["id"]
    moved = client.patch(f"/api/items/{item_id}", json={"category_id": category_id})
    assert moved.status_code == 200
    assert client.get(f"/api/items/{item_id}").json()["category_id"] == category_id


def test_retry_failed_item(client):
    from prometheus.library import items as items_store

    created = client.post("/api/items", json={"url": BV_URL, "figures": False})
    item_id = created.json()["id"]
    wait_for_status(client, item_id, "done")
    items_store.update_item(client.app.state.data_dir, item_id, status="failed",
                            error_code="EXTERNAL_API_FAILURE")
    assert client.post(f"/api/items/{item_id}/retry").status_code == 200
    # The queue may pick the item up before we look, so assert the outcome:
    # the retried item runs again and finishes.
    assert client.get(f"/api/items/{item_id}").json()["status"] in ("queued", "running", "done")
    wait_for_status(client, item_id, "done")
