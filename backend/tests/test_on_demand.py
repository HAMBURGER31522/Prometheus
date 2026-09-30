"""按需生成 (PLAN 15.4.15): what a video gets — the report (with its mind map), the subtitles — and how
detailed its report is, for this video only."""

import pytest
from conftest import BV_URL
from prometheus.library import items as items_store

ALL = {"report": True, "subtitles": True, "mindmap": True}
SUBTITLES = {"report": False, "subtitles": True, "mindmap": False}


def _submit(client, **body):
    return client.post("/api/items", json={"url": BV_URL, "figures": False, **body})


def _row(client, item_id):
    return client.get(f"/api/items/{item_id}").json()


# ---------------- the submit (E17 ①: saved and checked) ----------------

def test_a_submit_keeps_what_the_video_gets_and_how_detailed(client):
    outputs = {"report": True, "subtitles": False, "mindmap": False}
    item_id = _submit(client, figures=True, outputs=outputs, depth="standard").json()["id"]
    row = _row(client, item_id)
    assert row.get("outputs") == outputs
    assert row.get("depth") == "standard"
    assert row["figures"] == 1


def test_without_a_report_there_are_no_figures_to_draw(client):
    item_id = _submit(client, figures=True, outputs=SUBTITLES, depth="full").json()["id"]
    row = _row(client, item_id)
    assert row.get("outputs") == SUBTITLES
    assert row["figures"] == 0


def test_old_items_and_old_clients_get_all_three_at_the_settings_depth(client):
    """PLAN 15.4.15-6: items from before R7h have all three and follow the settings' depth."""
    item_id = _submit(client).json()["id"]
    row = _row(client, item_id)
    assert row.get("outputs") == ALL
    assert "depth" in row and row["depth"] is None
    old = items_store.create_item(client.app.state.data_dir, platform="bilibili", video_id="BV1old00000",
                                  source_url="https://www.bilibili.com/video/BV1old00000/", status="done")
    assert _row(client, old).get("outputs") == ALL
    listed = {row["id"]: row for row in client.get("/api/items").json()}
    assert listed[old].get("outputs") == ALL
    queued = {row["id"]: row for row in client.get("/api/queue").json()}
    assert queued[old].get("outputs") == ALL


@pytest.mark.parametrize(("body", "code"), [
    ({"outputs": {"report": False, "subtitles": False, "mindmap": False}}, "OUTPUTS_INVALID"),
    ({"outputs": {"report": False, "subtitles": True, "mindmap": True}}, "OUTPUTS_INVALID"),
    ({"outputs": {"report": False, "subtitles": False, "mindmap": True}}, "OUTPUTS_INVALID"),
    ({"outputs": {"report": True}}, "OUTPUTS_INVALID"),
    ({"outputs": {"report": "yes", "subtitles": True, "mindmap": False}}, "OUTPUTS_INVALID"),
    ({"outputs": ["report", "subtitles"]}, "OUTPUTS_INVALID"),
    ({"depth": "deep"}, "DEPTH_INVALID"),
    ({"depth": None, "outputs": SUBTITLES}, "DEPTH_INVALID"),
])
def test_nothing_to_make_a_map_without_its_report_or_an_unknown_depth_is_refused(client, body, code):
    response = _submit(client, **body)
    assert response.status_code == 422
    assert response.json() == {"code": code}
    assert client.get("/api/items").json() == []
