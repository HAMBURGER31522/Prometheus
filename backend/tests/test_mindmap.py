"""BiliSum-style knowledge-tree mind maps (PLAN 15.4.2, D-30)."""

import json
from pathlib import Path

from prometheus.mindmap.markdown import moment_link, tree_to_markdown
from prometheus.mindmap.prompt import build_prompt
from prometheus.mindmap.tree import parse_tree, validate_tree
from prometheus.report.outline import extract_outline

EXAMPLE = Path("vendor/video-report-agent/docs/examples/report.html")


def load_example():
    return extract_outline(EXAMPLE.read_text(encoding="utf-8"))


def _node(label, kind, summary="要点", time=None, children=None):
    return {"label": label, "type": kind, "summary": summary, "time": time, "children": children or []}


def good_tree(outline):
    """Three themes whose leaves sit at every section's start time."""
    sections = [s for s in outline["sections"] if s["start_s"] is not None]
    assert len(sections) >= 3, "the outline must carry section times"
    groups = [sections[0::3], sections[1::3], sections[2::3]]
    themes = [
        _node(f"主题{i + 1}", "theme", children=[
            _node(f"要点{j + 1}", "leaf", time=section["start_s"] + 1) for j, section in enumerate(group)
        ])
        for i, group in enumerate(groups)
    ]
    return {"title": outline["title"], "root": _node("削藩与分配", "root", "中国财政再平衡", children=themes)}


def test_outline_carries_section_ranges_and_text():
    outline = load_example()
    assert outline["title"] == "削藩与分配：中国财政再平衡的逻辑与路径"
    first = outline["sections"][0]
    assert "思想实验" in first["title"]
    assert (first["start_s"], first["end_s"]) == (0, 147)          # 00:00–02:27
    assert "水獭国" in first["text"]
    assert first["h3"]
    assert outline["intro"]


def test_moment_links_both_platforms():
    assert moment_link("bilibili", "BV1xJYT6EEYc?p=3", 125.7) == \
        "https://www.bilibili.com/video/BV1xJYT6EEYc/?p=3&t=125"
    assert moment_link("youtube", "jNQXAC9IVRw", 9) == "https://www.youtube.com/watch?v=jNQXAC9IVRw&t=9s"


def test_parse_takes_the_first_json_object_despite_noise():
    tree = {"title": "T", "root": _node("R", "root")}
    text = "好的，下面是导图：\n```json\n" + json.dumps(tree, ensure_ascii=False) + "\n```\n说明：共 3 个主题。"
    assert parse_tree(text) == tree
    assert parse_tree("没有 JSON") is None


def test_a_good_tree_passes():
    outline = load_example()
    assert validate_tree(good_tree(outline), outline) == []


def test_theme_count_must_be_three_to_six():
    outline = load_example()
    tree = good_tree(outline)
    tree["root"]["children"] = tree["root"]["children"][:2]
    assert any("主题" in error for error in validate_tree(tree, outline))


def test_labels_and_summaries_have_length_limits():
    outline = load_example()
    tree = good_tree(outline)
    tree["root"]["children"][0]["label"] = "长" * 21
    tree["root"]["children"][1]["children"][0]["summary"] = "长" * 61  # leaves: 60; themes: 40 (PLAN 15.4.9)
    errors = validate_tree(tree, outline)
    assert any("20" in error for error in errors) and any("60" in error for error in errors)


def test_leaves_need_a_time_inside_some_section():
    outline = load_example()
    tree = good_tree(outline)
    leaves = tree["root"]["children"][0]["children"]
    leaves[0]["time"] = None
    leaves[1]["time"] = 999999
    errors = validate_tree(tree, outline)
    assert any("没有时间" in error for error in errors)
    assert any("不在任何章节" in error for error in errors)


def test_depth_is_at_most_four_levels():
    outline = load_example()
    tree = good_tree(outline)
    leaf = tree["root"]["children"][0]["children"][0]
    leaf["type"] = "topic"
    leaf["children"] = [_node("叶", "leaf", time=leaf["time"], children=[_node("太深", "leaf", time=leaf["time"])])]
    assert any("层" in error for error in validate_tree(tree, outline))


def test_most_sections_must_be_covered():
    outline = load_example()
    tree = good_tree(outline)
    first = outline["sections"][0]["start_s"] + 1
    for theme in tree["root"]["children"]:
        for leaf in theme["children"]:
            leaf["time"] = first
    assert any("覆盖" in error for error in validate_tree(tree, outline))


def test_markdown_export_has_headings_summaries_and_moment_links():
    outline = load_example()
    md = tree_to_markdown(good_tree(outline), "bilibili", "BV1xJYT6EEYc")
    assert md.startswith("# 削藩与分配\n")
    assert "## 主题1" in md
    assert "**要点1**" in md
    assert "https://www.bilibili.com/video/BV1xJYT6EEYc/?p=1&t=1" in md


def test_prompt_carries_bilisum_rules_and_section_ranges():
    prompt = build_prompt(load_example())
    assert "语义归纳" in prompt
    assert "theme" in prompt and "leaf" in prompt
    assert "00:00–02:27" in prompt
    assert "只输出 JSON" in prompt


def test_generate_retries_once_then_saves_json_and_markdown(tmp_path, monkeypatch):
    from prometheus import paths
    from prometheus.library import db
    from prometheus.library import items as items_store
    from prometheus.llm import one_shot
    from prometheus.mindmap import generate

    data_dir = tmp_path / "data"
    paths.init_data_dir(data_dir)
    db.init_db(data_dir)
    item_id = items_store.create_item(data_dir, platform="bilibili", video_id="BV1xJYT6EEYc",
                                      source_url="https://www.bilibili.com/video/BV1xJYT6EEYc/",
                                      status="running")
    report = paths.report_file(data_dir, item_id)
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(EXAMPLE.read_text(encoding="utf-8"), encoding="utf-8")
    answers = ["不是 JSON", json.dumps(good_tree(load_example()), ensure_ascii=False)]
    prompts = []

    def fake_one_shot(work_dir, *, prompt, **kwargs):
        prompts.append(prompt)
        return answers[len(prompts) - 1]

    monkeypatch.setattr(one_shot, "run_one_shot", fake_one_shot)
    row = items_store.get_item(data_dir, item_id)
    saved = generate.generate_for_item(data_dir, item_id, row, {"provider": "deepseek", "model": "m"},
                                       node_exe="node.exe", pi_cli="cli.js")
    assert saved is True
    skeleton = [p for p in prompts if "末端要点" not in p]  # filling calls come after (PLAN 15.4.9)
    assert len(skeleton) == 2 and "上次输出的问题" in skeleton[1]
    assert paths.mindmap_json(data_dir, item_id).is_file()
    tree = json.loads(paths.mindmap_json(data_dir, item_id).read_text(encoding="utf-8"))
    assert len(tree["root"]["children"]) == 3
    assert paths.mindmap_file(data_dir, item_id).read_text(encoding="utf-8").startswith("# ")
    assert items_store.get_item(data_dir, item_id)["mindmap_status"] == "ok"


def test_mindmap_endpoint_serves_the_tree_as_json(client):
    from conftest import BV_URL, wait_for_status

    item_id = client.post("/api/items", json={"url": BV_URL, "figures": False}).json()["id"]
    wait_for_status(client, item_id, "done")
    response = client.get(f"/api/items/{item_id}/mindmap", params={"format": "json"})
    assert response.status_code == 200
    assert response.json()["root"]["type"] == "root"
    markdown = client.get(f"/api/items/{item_id}/mindmap")
    assert markdown.status_code == 200 and markdown.text.startswith("# ")


def _item(tmp_path, status="running"):
    from prometheus import paths
    from prometheus.library import db
    from prometheus.library import items as items_store

    data_dir = tmp_path / "data"
    paths.init_data_dir(data_dir)
    db.init_db(data_dir)
    item_id = items_store.create_item(data_dir, platform="bilibili", video_id="BV1xJYT6EEYc",
                                      source_url="https://www.bilibili.com/video/BV1xJYT6EEYc/",
                                      status=status)
    return data_dir, item_id


def test_model_errors_only_mark_the_mindmap_failed(tmp_path, monkeypatch):
    # PLAN 8.3: a mind map failure never fails the item.
    from prometheus import paths
    from prometheus.library import items as items_store
    from prometheus.llm import one_shot
    from prometheus.mindmap import generate

    data_dir, item_id = _item(tmp_path)
    report = paths.report_file(data_dir, item_id)
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(EXAMPLE.read_text(encoding="utf-8"), encoding="utf-8")

    def model_down(work_dir, *, prompt, **kwargs):
        raise RuntimeError("502 Bad Gateway")

    monkeypatch.setattr(one_shot, "run_one_shot", model_down)
    try:
        saved = generate.generate_for_item(data_dir, item_id, items_store.get_item(data_dir, item_id),
                                           {"provider": "deepseek", "model": "m"},
                                           node_exe="node.exe", pi_cli="cli.js")
    except RuntimeError as exc:
        raise AssertionError(f"a model error escaped the mind map stage: {exc}") from exc
    assert saved is False
    assert items_store.get_item(data_dir, item_id)["mindmap_status"] == "failed"


def test_regenerating_a_finished_item_reads_the_library_report(tmp_path, monkeypatch):
    # After success the cache keeps no report copy; the library folder has it.
    from prometheus import paths
    from prometheus.library import items as items_store
    from prometheus.llm import one_shot
    from prometheus.mindmap import generate

    data_dir, item_id = _item(tmp_path, status="done")
    folder = data_dir / "未分类" / "2026-09-26 削藩与分配"
    folder.mkdir(parents=True)
    (folder / paths.LIBRARY_FILES["html"]).write_text(EXAMPLE.read_text(encoding="utf-8"), encoding="utf-8")
    items_store.update_item(data_dir, item_id, library_path="未分类/2026-09-26 削藩与分配")
    assert not paths.report_file(data_dir, item_id).exists()
    answer = json.dumps(good_tree(load_example()), ensure_ascii=False)
    monkeypatch.setattr(one_shot, "run_one_shot", lambda work_dir, *, prompt, **kwargs: answer)
    saved = generate.generate_for_item(data_dir, item_id, items_store.get_item(data_dir, item_id),
                                       {"provider": "deepseek", "model": "m"},
                                       node_exe="node.exe", pi_cli="cli.js")
    assert saved is True
    assert paths.mindmap_json(data_dir, item_id).is_file()


def test_startup_turns_a_stranded_mindmap_job_into_failed(tmp_path):
    from prometheus.library import db
    from prometheus.library import items as items_store

    # A rerun clears mindmap_status (NULL = pending); quitting mid-run strands it.
    data_dir, item_id = _item(tmp_path, status="done")
    items_store.update_item(data_dir, item_id, mindmap_status=None)
    db.mark_running_as_interrupted(data_dir)
    row = items_store.get_item(data_dir, item_id)
    assert row["mindmap_status"] == "failed"
    assert row["status"] == "done"


def _wait_for_mindmap(client, item_id, status, timeout=15.0):
    import time

    deadline = time.time() + timeout
    last = None
    while time.time() < deadline:
        last = client.get(f"/api/items/{item_id}").json()
        # generate sets the status before publish copies the file: wait for the rerun to end.
        if last.get("mindmap_status") == status and not client.app.state.queue.is_running(item_id):
            return last
        time.sleep(0.05)
    raise AssertionError(f"mindmap_status never reached {status!r}, last={last!r}")


def _finished_item_without_mindmap(client):
    from conftest import BV_URL, wait_for_status
    from prometheus import paths
    from prometheus.library import items as items_store

    data_dir = client.app.state.data_dir
    item_id = client.post("/api/items", json={"url": BV_URL, "figures": False}).json()["id"]
    row = wait_for_status(client, item_id, "done")
    exported = paths.library_folder(data_dir, row["library_path"]) / paths.LIBRARY_FILES["mindmap"]
    exported.unlink()
    items_store.update_item(data_dir, item_id, mindmap_status="failed")
    return item_id, exported


def test_regenerate_only_the_mindmap_of_a_finished_item(client):
    from prometheus import paths

    item_id, exported = _finished_item_without_mindmap(client)
    response = client.post(f"/api/items/{item_id}/regenerate", json={"only": "mindmap"})
    assert response.status_code == 200
    assert response.json() == {"queued": True}
    row = _wait_for_mindmap(client, item_id, "ok")
    assert row["status"] == "done"
    assert exported.is_file()
    trace = paths.work_dir(client.app.state.data_dir, item_id) / "run.trace.jsonl"
    events = [json.loads(line) for line in trace.read_text(encoding="utf-8").splitlines()]
    last_run = [e["stage"] for e in events if e["run"] == events[-1]["run"] and e["event"] == "start"]
    assert last_run == ["mindmap", "publish"]


def test_regenerate_only_the_mindmap_needs_a_finished_item(client):
    from prometheus.library import items as items_store

    item_id, _ = _finished_item_without_mindmap(client)
    items_store.update_item(client.app.state.data_dir, item_id, status="failed")
    response = client.post(f"/api/items/{item_id}/regenerate", json={"only": "mindmap"})
    assert response.status_code == 409


def test_a_failed_mindmap_rerun_leaves_the_item_done(client, monkeypatch):
    item_id, _ = _finished_item_without_mindmap(client)

    def publish_breaks(ctx):
        raise OSError("disk full")

    monkeypatch.setitem(client.app.state.queue.impls, "publish", publish_breaks)
    assert client.post(f"/api/items/{item_id}/regenerate", json={"only": "mindmap"}).status_code == 200
    row = _wait_for_mindmap(client, item_id, "failed")
    assert row["status"] == "done"
    assert row["error_code"] is None


def test_cancelling_a_mindmap_rerun_leaves_the_item_done(client, monkeypatch):
    import threading
    import time

    item_id, _ = _finished_item_without_mindmap(client)
    started = threading.Event()

    def slow_mindmap(ctx):
        started.set()
        deadline = time.time() + 10
        while not ctx.cancel_requested and time.time() < deadline:
            time.sleep(0.02)
        raise RuntimeError("Pi was killed")

    monkeypatch.setitem(client.app.state.queue.impls, "mindmap", slow_mindmap)
    assert client.post(f"/api/items/{item_id}/regenerate", json={"only": "mindmap"}).status_code == 200
    assert started.wait(timeout=15)
    assert client.post(f"/api/items/{item_id}/cancel").status_code == 200
    row = _wait_for_mindmap(client, item_id, "failed")
    assert row["status"] == "done"


def test_deleting_during_a_mindmap_rerun_stops_it_first(client, monkeypatch):
    import threading
    import time

    from prometheus import paths

    item_id, _ = _finished_item_without_mindmap(client)
    started = threading.Event()

    def slow_mindmap(ctx):
        started.set()
        deadline = time.time() + 10
        while not ctx.cancel_requested and time.time() < deadline:
            time.sleep(0.02)
        raise RuntimeError("Pi was killed")

    monkeypatch.setitem(client.app.state.queue.impls, "mindmap", slow_mindmap)
    assert client.post(f"/api/items/{item_id}/regenerate", json={"only": "mindmap"}).status_code == 200
    assert started.wait(timeout=15)
    assert client.delete(f"/api/items/{item_id}").status_code == 204
    assert not client.app.state.queue.is_running(item_id)
    assert not paths.cache_dir(client.app.state.data_dir, item_id).exists()


def test_cancelling_a_waiting_mindmap_rerun_drops_it(tmp_path):
    from prometheus.library import items as items_store
    from prometheus.tasks import runner
    from prometheus.tasks.queue import TaskQueue

    data_dir, item_id = _item(tmp_path, status="done")
    items_store.update_item(data_dir, item_id, mindmap_status="ok")
    ran = []
    queue = TaskQueue(data_dir, {stage: (lambda ctx, s=stage: ran.append(s)) for stage in runner.STAGES})
    queue.enqueue_mindmap(item_id)  # the worker thread is not started: nothing runs yet
    assert queue.cancel(item_id) is True
    queue._drain_one()
    assert ran == []
    assert items_store.get_item(data_dir, item_id)["mindmap_status"] == "failed"


def test_generate_fills_the_leaves_after_the_skeleton(tmp_path, monkeypatch):
    # PLAN 15.4.9: skeleton first, then one grounded filling call per theme.
    import re

    from prometheus import paths
    from prometheus.library import db
    from prometheus.library import items as items_store
    from prometheus.llm import one_shot
    from prometheus.mindmap import generate

    data_dir = tmp_path / "data"
    paths.init_data_dir(data_dir)
    db.init_db(data_dir)
    item_id = items_store.create_item(data_dir, platform="bilibili", video_id="BV1xJYT6EEYc",
                                      source_url="https://www.bilibili.com/video/BV1xJYT6EEYc/",
                                      status="running")
    report = paths.report_file(data_dir, item_id)
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(EXAMPLE.read_text(encoding="utf-8"), encoding="utf-8")
    skeleton = json.dumps(good_tree(load_example()), ensure_ascii=False)

    def fake_one_shot(work_dir, *, prompt, **kwargs):
        if "末端要点" not in prompt:
            return skeleton
        # A diligent model: every detail is taken from the evidence it was given.
        details = {}
        for chunk in prompt.split('要点（编号 "')[1:]:
            leaf_id = chunk.split('"', 1)[0]
            source = chunk.split("资料：\n", 1)[1]
            details[leaf_id] = re.sub(r"\s+", "", source)[:150]
        return json.dumps(details, ensure_ascii=False)

    monkeypatch.setattr(one_shot, "run_one_shot", fake_one_shot)
    assert generate.generate_for_item(data_dir, item_id, items_store.get_item(data_dir, item_id),
                                      {"provider": "deepseek", "model": "m"}, node_exe="node", pi_cli="cli")
    saved = json.loads(paths.mindmap_json(data_dir, item_id).read_text(encoding="utf-8"))
    leaves = [leaf for theme in saved["root"]["children"] for leaf in theme["children"]]
    assert leaves and all(leaf.get("detail") for leaf in leaves)
    assert saved["enrichment"]["coverage"] == 1.0
    assert leaves[0]["detail"] in paths.mindmap_file(data_dir, item_id).read_text(encoding="utf-8")
    assert "summary" not in saved["root"], "the root is the title only (PLAN 15.4.9: root ≤ 20 字)"


def test_the_retry_fixes_the_previous_tree_instead_of_starting_over(tmp_path, monkeypatch):
    # A 35-leaf tree regenerated from scratch trades one length slip for another; the one
    # retry therefore hands back the previous JSON with its problems (PLAN 8.3 / 15.4.2).
    from prometheus import paths
    from prometheus.library import db
    from prometheus.library import items as items_store
    from prometheus.llm import one_shot
    from prometheus.mindmap import generate

    data_dir = tmp_path / "data"
    paths.init_data_dir(data_dir)
    db.init_db(data_dir)
    item_id = items_store.create_item(data_dir, platform="bilibili", video_id="BV1xJYT6EEYc",
                                      source_url="https://www.bilibili.com/video/BV1xJYT6EEYc/",
                                      status="running")
    report = paths.report_file(data_dir, item_id)
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(EXAMPLE.read_text(encoding="utf-8"), encoding="utf-8")
    slipped = good_tree(load_example())
    slipped["root"]["children"][0]["label"] = "超" * 21
    answers = [json.dumps(slipped, ensure_ascii=False), json.dumps(good_tree(load_example()), ensure_ascii=False)]
    prompts = []

    def fake_one_shot(work_dir, *, prompt, **kwargs):
        if "末端要点" in prompt:
            return "{}"
        prompts.append(prompt)
        return answers[len(prompts) - 1]

    monkeypatch.setattr(one_shot, "run_one_shot", fake_one_shot)
    assert generate.generate_for_item(data_dir, item_id, items_store.get_item(data_dir, item_id),
                                      {"provider": "deepseek", "model": "m"}, node_exe="node", pi_cli="cli")
    assert len(prompts) == 2
    assert "超" * 21 in prompts[1] and "只修改这些问题" in prompts[1]


# ---------------- three tries, and why it failed (PLAN 15.4.15-9) ----------------

def _with_report(tmp_path):
    from prometheus import paths

    data_dir, item_id = _item(tmp_path)
    report = paths.report_file(data_dir, item_id)
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(EXAMPLE.read_text(encoding="utf-8"), encoding="utf-8")
    return data_dir, item_id


def _slipped():
    tree = good_tree(load_example())
    tree["root"]["children"][0]["label"] = "超" * 21
    return tree


def _skeleton_answers(monkeypatch, answers):
    """The skeleton calls get `answers` in turn (the last one repeats); filling calls get nothing to add."""
    from prometheus.llm import one_shot

    prompts = []

    def fake_one_shot(work_dir, *, prompt, **kwargs):
        if "末端要点" in prompt:
            return "{}"
        prompts.append(prompt)
        return json.dumps(answers[min(len(prompts), len(answers)) - 1], ensure_ascii=False)

    monkeypatch.setattr(one_shot, "run_one_shot", fake_one_shot)
    return prompts


def _generate(data_dir, item_id):
    from prometheus.library import items as items_store
    from prometheus.mindmap import generate

    return generate.generate_for_item(data_dir, item_id, items_store.get_item(data_dir, item_id),
                                      {"provider": "deepseek", "model": "m"}, node_exe="node", pi_cli="cli")


def test_a_tree_that_fails_twice_gets_a_third_try_on_the_last_one(tmp_path, monkeypatch):
    # BV1EJ4m1t7Zs (2026-09-30): two tries failed; the same report passed on the next run.
    from prometheus.library import items as items_store

    data_dir, item_id = _with_report(tmp_path)
    prompts = _skeleton_answers(monkeypatch, [_slipped(), _slipped(), good_tree(load_example())])
    assert _generate(data_dir, item_id) is True
    assert len(prompts) == 3 and "只修改这些问题" in prompts[2]
    row = items_store.get_item(data_dir, item_id)
    assert (row["mindmap_status"], row.get("mindmap_error")) == ("ok", None)


def test_three_failed_tries_keep_which_checks_failed(tmp_path, monkeypatch):
    from prometheus.library import items as items_store

    data_dir, item_id = _with_report(tmp_path)
    prompts = _skeleton_answers(monkeypatch, [_slipped()])
    assert _generate(data_dir, item_id) is False
    assert len(prompts) == 3
    row = items_store.get_item(data_dir, item_id)
    assert row["mindmap_status"] == "failed"
    reason = row.get("mindmap_error") or ""
    assert reason.startswith("没通过检查：")
    assert "；".join(validate_tree(_slipped(), load_example())) in reason


def test_a_model_error_keeps_what_it_said(tmp_path, monkeypatch):
    from prometheus.library import items as items_store
    from prometheus.llm import one_shot

    data_dir, item_id = _with_report(tmp_path)

    def model_down(work_dir, *, prompt, **kwargs):
        raise RuntimeError("502 Bad Gateway")

    monkeypatch.setattr(one_shot, "run_one_shot", model_down)
    assert _generate(data_dir, item_id) is False
    reason = items_store.get_item(data_dir, item_id).get("mindmap_error") or ""
    assert reason.startswith("调用出错：") and "502 Bad Gateway" in reason


def test_regenerating_the_map_clears_the_last_reason(client, monkeypatch):
    import threading

    from conftest import BV_URL, wait_for_status
    from prometheus.library import items as items_store

    item_id = client.post("/api/items", json={"url": BV_URL, "figures": False}).json()["id"]
    wait_for_status(client, item_id, "done")
    data_dir = client.app.state.data_dir
    items_store.update_item(data_dir, item_id, mindmap_status="failed", mindmap_error="没通过检查：主题太少")
    assert client.get(f"/api/items/{item_id}").json().get("mindmap_error") == "没通过检查：主题太少"
    release = threading.Event()
    monkeypatch.setitem(client.app.state.queue.impls, "mindmap", lambda ctx: release.wait(timeout=10))
    try:
        assert client.post(f"/api/items/{item_id}/regenerate", json={"only": "mindmap"}).status_code == 200
        assert client.get(f"/api/items/{item_id}").json().get("mindmap_error", "missing") is None
    finally:
        release.set()
