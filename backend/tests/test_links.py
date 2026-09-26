"""Full link table (PLAN 8.4) and the no-duration-limit rule."""

import pytest
from prometheus.ingest.links import LinkUnsupported, parse_url


@pytest.mark.parametrize(("text", "platform", "video_id", "page"), [
    ("https://www.bilibili.com/video/BV1xJYT6EEYc/", "bilibili", "BV1xJYT6EEYc", 1),
    ("https://www.bilibili.com/video/BV1xJYT6EEYc/?p=3&spm_id_from=333",
     "bilibili", "BV1xJYT6EEYc?p=3", 3),
    ("BV1xJYT6EEYc", "bilibili", "BV1xJYT6EEYc", 1),
    ("【干货】推荐这个 https://www.bilibili.com/video/BV1xJYT6EEYc/ 转需",
     "bilibili", "BV1xJYT6EEYc", 1),
    ("https://www.youtube.com/watch?v=jNQXAC9IVRw&t=10s", "youtube", "jNQXAC9IVRw", 1),
    ("https://youtu.be/jNQXAC9IVRw", "youtube", "jNQXAC9IVRw", 1),
    ("https://www.youtube.com/shorts/jNQXAC9IVRw", "youtube", "jNQXAC9IVRw", 1),
])
def test_parse_table(text, platform, video_id, page):
    source = parse_url(text)
    assert source.platform == platform
    assert source.video_id == video_id
    assert source.page == page


def test_b23_short_link_follows_redirect(monkeypatch):
    from prometheus.ingest import links

    monkeypatch.setattr(
        links, "resolve_redirect",
        lambda url: "https://www.bilibili.com/video/BV1xJYT6EEYc/?p=2",
    )
    source = parse_url("https://b23.tv/abc123")
    assert source.platform == "bilibili"
    assert source.video_id == "BV1xJYT6EEYc?p=2"
    assert source.page == 2


def test_regular_links_never_touch_the_network(monkeypatch):
    from prometheus.ingest import links

    monkeypatch.setattr(
        links, "resolve_redirect",
        lambda url: (_ for _ in ()).throw(AssertionError("network touched")),
    )
    assert parse_url("https://www.bilibili.com/video/BV1xJYT6EEYc/").page == 1


@pytest.mark.parametrize("text", [
    "https://www.youtube.com/playlist?list=PL1234567890abcdef",
    "https://space.bilibili.com/123456",
    "https://v.qq.com/x/cover/abc123.html",
    "随便一段文字，没有链接",
])
def test_rejects_unsupported(text):
    with pytest.raises(LinkUnsupported):
        parse_url(text)


def test_five_hour_video_can_be_queued(client):
    from prometheus.library import items as items_store

    item_id = client.post("/api/items", json={
        "url": "https://www.bilibili.com/video/BV1xJYT6EEYc/", "figures": False,
    }).json()["id"]
    items_store.update_item(client.app.state.data_dir, item_id, duration_s=5 * 3600)
    row = items_store.get_item(client.app.state.data_dir, item_id)
    assert row["duration_s"] == 5 * 3600
