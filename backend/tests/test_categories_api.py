"""Category rename, merge, delete and counting (PLAN 8.2)."""

from conftest import BV_URL
from prometheus.library import categories as categories_store


def make_category(client, name):
    return categories_store.create_category(client.app.state.data_dir, name)


def test_list_categories(client):
    make_category(client, "科技")
    rows = client.get("/api/categories").json()
    assert rows == [{"id": rows[0]["id"], "name": "科技", "count": 0}]


def test_rename_category(client):
    category_id = make_category(client, "科技")
    response = client.patch(f"/api/categories/{category_id}", json={"name": "科学"})
    assert response.status_code == 200
    assert client.get("/api/categories").json()[0]["name"] == "科学"


def test_rename_to_duplicate_gets_409(client):
    make_category(client, "科技")
    other = make_category(client, "生活")
    response = client.patch(f"/api/categories/{other}", json={"name": "科技"})
    assert response.status_code == 409


def test_delete_empty_category(client):
    category_id = make_category(client, "空分类")
    assert client.delete(f"/api/categories/{category_id}").status_code == 204
    assert client.get("/api/categories").json() == []


def test_delete_nonempty_category_gets_409(client):
    category_id = make_category(client, "非空")
    client.post("/api/items", json={"url": BV_URL, "figures": False})
    from prometheus.library import items as items_store

    items = items_store.list_items(client.app.state.data_dir)
    items_store.update_item(client.app.state.data_dir, items[0]["id"],
                            category_id=category_id, status="done")
    response = client.delete(f"/api/categories/{category_id}")
    assert response.status_code == 409


def test_merge_moves_items_and_deletes_source(client):
    source = make_category(client, "来源")
    target = make_category(client, "目标")
    client.post("/api/items", json={"url": BV_URL, "figures": False})
    from prometheus.library import items as items_store

    items = items_store.list_items(client.app.state.data_dir)
    items_store.update_item(client.app.state.data_dir, items[0]["id"],
                            category_id=source, status="done")
    response = client.post(f"/api/categories/{source}/merge", json={"into_id": target})
    assert response.status_code == 200
    assert client.get(f"/api/items/{items[0]['id']}").json()["category_id"] == target
    assert client.get("/api/categories").json()[0]["name"] == "目标"
