"""Serial queue: ordering, cancellation, startup interruption (PLAN 8.3)."""

import threading
import time

from conftest import BV_URL, wait_for_status
from prometheus.tasks import runner


def block_on_event(ctx):
    while not ctx.cancel_requested:
        time.sleep(0.02)
    raise runner.TaskCancelled()


def test_second_item_stays_queued_until_first_finishes(client, monkeypatch):
    release = threading.Event()
    started = threading.Event()

    def slow_transcribe(ctx):
        started.set()
        release.wait(timeout=15)

    monkeypatch.setitem(client.app.state.queue.impls, "transcribe", slow_transcribe)
    first = client.post("/api/items", json={"url": BV_URL, "figures": False}).json()["id"]
    assert started.wait(timeout=15)
    second = client.post("/api/items", json={
        "url": "https://www.bilibili.com/video/BV1bTtb6uE7d/", "figures": False,
    }).json()["id"]
    assert client.get(f"/api/items/{second}").json()["status"] == "queued"
    assert client.get(f"/api/items/{first}").json()["status"] == "running"
    release.set()
    wait_for_status(client, first, "done")
    wait_for_status(client, second, "done")


def test_cancel_running_item(client, monkeypatch):
    monkeypatch.setitem(client.app.state.queue.impls, "download", block_on_event)
    item_id = client.post("/api/items", json={"url": BV_URL, "figures": False}).json()["id"]
    deadline = time.time() + 15
    while time.time() < deadline:
        if client.get(f"/api/items/{item_id}").json()["stage"] == "download":
            break
        time.sleep(0.02)
    assert client.post(f"/api/items/{item_id}/cancel").status_code == 200
    row = wait_for_status(client, item_id, "cancelled")
    assert row["status"] == "cancelled"


def test_queue_lists_active_and_recent_done(client):
    item_id = client.post("/api/items", json={"url": BV_URL, "figures": False}).json()["id"]
    wait_for_status(client, item_id, "done")
    rows = client.get("/api/queue").json()
    assert [row["id"] for row in rows] == [item_id]
    assert rows[0]["status"] == "done"


def test_startup_marks_running_as_interrupted(client_factory, tmp_path):
    from prometheus import paths
    from prometheus.library import db
    from prometheus.library import items as items_store

    data_dir = tmp_path / "data"
    paths.init_data_dir(data_dir)
    db.init_db(data_dir)
    items_store.create_item(data_dir, platform="bilibili", video_id="BV1aaaaaaaaag",
                            source_url=BV_URL, status="running")
    client = client_factory(data_dir=data_dir, fake=True)
    assert client.get("/api/items", headers={
        "Authorization": "Bearer test-token",
    }).json()[0]["status"] == "interrupted"
