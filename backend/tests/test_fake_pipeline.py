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

    # fixtures/segments.json in 10–15 s paragraphs (PLAN 15.4.10)
    first = "大家好，今天我们聊一聊钱在经济里是怎么流动的。对吧，一个国家挣到的钱大致分成三个口袋，家庭、企业和政府。"
    subtitle_json = client.get(f"/api/items/{item_id}/subtitle", params={"format": "json"})
    assert subtitle_json.status_code == 200
    assert subtitle_json.json()[0]["text"] == first

    srt = client.get(f"/api/items/{item_id}/subtitle", params={"format": "srt"})
    assert srt.status_code == 200
    assert "00:00:00,000 --> 00:00:12,900" in srt.text

    txt = client.get(f"/api/items/{item_id}/subtitle", params={"format": "txt"})
    assert f"[00:00:00] {first}" in txt.text


def test_fake_item_appears_in_category_counts(client):
    item_id = client.post("/api/items", json={"url": BV_URL, "figures": False}).json()["id"]
    wait_for_status(client, item_id, "done")
    rows = client.get("/api/categories").json()
    assert sum(row["count"] for row in rows) == 1


def test_fake_mode_offers_a_model_list_for_the_settings_e2e(client):
    # E11 ⑤: 「获取模型列表」 is exercised against the fake backend itself, never a real relay.
    response = client.get("/fake-llm/v1/models")
    assert response.status_code == 200
    assert [row["id"] for row in response.json()["data"]] == ["fake-model-a", "fake-model-b"]


def test_the_fake_model_list_is_absent_in_real_mode(client_factory, tmp_path):
    real = client_factory(data_dir=tmp_path / "data", fake=False)
    real.headers["Authorization"] = "Bearer test-token"
    assert real.get("/fake-llm/v1/models").status_code == 404
