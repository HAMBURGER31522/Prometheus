"""Fake pipeline (PROMETHEUS_FAKE=1) completes all stages within 3 seconds (PLAN 12/M2)."""

import time

from conftest import BV_URL, wait_for_status


def test_fake_pipeline_completes_all_stages_quickly(client, tmp_path):
    item_id = client.post("/api/items", json={"url": BV_URL, "figures": False}).json()["id"]
    # The 3s budget (PLAN 12/M2) covers the pipeline itself: from the moment the
    # queue picks the item up to completion, excluding app startup on slow CIs.
    deadline = time.time() + 15
    while time.time() < deadline:
        if client.get(f"/api/items/{item_id}").json().get("status") == "running":
            break
        time.sleep(0.02)
    started = time.time()
    row = wait_for_status(client, item_id, "done", timeout=3.0)
    elapsed = time.time() - started
    assert elapsed < 3.0
    assert row["stage"] in ("classify", None) or row["stage"] is None
    assert row["mindmap_status"] == "ok"
    assert row["report_title"]
    assert row["category_id"] is not None

    from prometheus import paths

    data_dir = tmp_path / "data"
    assert row.get("library_path"), "library_path not recorded"
    folder = data_dir / row["library_path"]
    for name in paths.LIBRARY_FILES.values():
        assert (folder / name).is_file(), name
    assert paths.segments_file(data_dir, item_id).is_file()


def test_content_endpoints_serve_fake_artifacts(client):
    item_id = client.post("/api/items", json={"url": BV_URL, "figures": False}).json()["id"]
    wait_for_status(client, item_id, "done")
    report = client.get(f"/api/items/{item_id}/report")
    assert report.status_code == 200
    assert report.headers["content-type"].startswith("text/html")
    assert "<html" in report.text

    mindmap = client.get(f"/api/items/{item_id}/mindmap")
    assert mindmap.status_code == 200
    assert mindmap.headers["content-type"].startswith("text/markdown")
    assert mindmap.text.startswith("# ")

    subtitle_json = client.get(f"/api/items/{item_id}/subtitle", params={"format": "json"})
    assert subtitle_json.status_code == 200
    assert subtitle_json.json()[0]["text"] == "第一句"

    srt = client.get(f"/api/items/{item_id}/subtitle", params={"format": "srt"})
    assert srt.status_code == 200
    assert "00:00:00,000 --> 00:00:01,500" in srt.text

    txt = client.get(f"/api/items/{item_id}/subtitle", params={"format": "txt"})
    assert "[00:00:00] 第一句" in txt.text


def test_fake_item_appears_in_category_counts(client):
    item_id = client.post("/api/items", json={"url": BV_URL, "figures": False}).json()["id"]
    wait_for_status(client, item_id, "done")
    rows = client.get("/api/categories").json()
    assert sum(row["count"] for row in rows) == 1
