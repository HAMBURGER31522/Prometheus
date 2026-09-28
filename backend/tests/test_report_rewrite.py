"""scripts/report-eval/rewrite.py (PLAN 15.4.11 experiments): only the 精读 of a finished item is
written again (report → finalize → publish); subtitles and the mind map stay as they are."""

import importlib.util
from pathlib import Path

from prometheus import paths
from prometheus.library import db
from prometheus.library import items as items_store

SCRIPT = Path(__file__).parents[2] / "scripts" / "report-eval" / "rewrite.py"


def load_script():
    spec = importlib.util.spec_from_file_location("report_rewrite", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def finished_item(tmp_path):
    data_dir = tmp_path / "data"
    paths.init_data_dir(data_dir)
    db.init_db(data_dir)
    item_id = items_store.create_item(data_dir, platform="bilibili", video_id="BV1xJYT6EEYc",
                                      source_url="https://www.bilibili.com/video/BV1xJYT6EEYc/")
    items_store.update_item(data_dir, item_id, status="done", mindmap_status="ok")
    return data_dir, item_id


def test_only_the_report_stages_run_and_the_item_stays_done(tmp_path):
    data_dir, item_id = finished_item(tmp_path)
    ran = []
    impls = {stage: (lambda ctx, stage=stage: ran.append((stage, ctx.item_id)))
             for stage in ("resolve", "transcribe", "keypoints", "plan", "report", "finalize", "subtitle_fix",
                           "mindmap", "publish")}
    assert load_script().main([str(data_dir), item_id], impls=impls) == 0
    assert ran == [("keypoints", item_id), ("plan", item_id), ("report", item_id), ("finalize", item_id),
                   ("publish", item_id)]
    row = items_store.get_item(data_dir, item_id)
    assert (row["status"], row["stage"], row["mindmap_status"]) == ("done", None, "ok")


def test_an_unknown_or_unfinished_item_is_refused(tmp_path):
    data_dir, item_id = finished_item(tmp_path)
    ran = []
    impls = {"report": lambda ctx: ran.append(ctx.item_id)}
    assert load_script().main([str(data_dir), "f" * 32], impls=impls) == 2
    items_store.update_item(data_dir, item_id, status="failed")
    assert load_script().main([str(data_dir), item_id], impls=impls) == 2
    assert ran == []


def test_frames_turns_figures_on_downloads_again_extracts_and_cleans_up_after(tmp_path):
    """A finished item's video and frames were cleaned away: --frames brings them back for the run."""
    from prometheus import paths

    data_dir, item_id = finished_item(tmp_path)
    work = paths.work_dir(data_dir, item_id)
    ran = []

    def download(ctx):
        ran.append("download")
        (work / "video.mp4").write_bytes(b"video")

    impls = {stage: (lambda ctx, stage=stage: ran.append(stage))
             for stage in ("resolve", "transcribe", "frames", "keypoints", "plan", "report", "finalize", "publish")}
    impls["download"] = download
    assert load_script().main([str(data_dir), item_id, "--frames"], impls=impls) == 0
    assert ran == ["download", "frames", "keypoints", "plan", "report", "finalize", "publish"]
    assert items_store.get_item(data_dir, item_id)["figures"] == 1
    assert not (work / "video.mp4").exists()


def test_an_item_without_tags_gets_them_on_the_way(tmp_path):
    """罗素 and 卡巴拉 came before tags (15.4.10): the rewrite also runs 分类 for them (category kept)."""
    data_dir, item_id = finished_item(tmp_path)
    ran = []
    impls = {stage: (lambda ctx, stage=stage: ran.append(stage))
             for stage in ("keypoints", "plan", "report", "finalize", "classify", "publish")}
    assert load_script().main([str(data_dir), item_id], impls=impls) == 0
    assert ran == ["keypoints", "plan", "report", "finalize", "classify", "publish"]
    items_store.update_item(data_dir, item_id, tags='["示例"]')
    ran.clear()
    assert load_script().main([str(data_dir), item_id], impls=impls) == 0
    assert "classify" not in ran


def test_the_spend_is_tallied_before_the_cleanup(tmp_path, capsys):
    """The relay has no prompt cache (D-44): every run says what it cost — Pi's own usage records for
    the agent runs, characters for the one-shot calls (an estimate)."""
    import json as json_mod

    from prometheus import paths
    from prometheus.llm import one_shot

    data_dir, item_id = finished_item(tmp_path)
    work = paths.work_dir(data_dir, item_id)

    def report(ctx):
        events = work / "chapters" / "ch-01" / "pi.events.jsonl"
        events.parent.mkdir(parents=True)
        usage = {"input": 40_000, "output": 2_000, "cacheRead": 0, "cacheWrite": 0}
        lines = [{"type": "message_end", "message": {"role": "assistant", "usage": usage}},
                 {"type": "message_end", "message": {"role": "user"}},
                 {"type": "message_update", "usage": usage}]
        events.write_text("\n".join(json_mod.dumps(line) for line in lines), encoding="utf-8")
        one_shot.run_one_shot(work, prompt="要点" * 500, provider="p", model="m", api_key="", thinking="medium",
                              node_exe="", pi_cli="", agent_dir=work)

    impls = {"report": report}
    script = load_script()
    script.one_shot_call = lambda work_dir, **kwargs: "回答" * 100  # the real call is replaced for the test
    assert script.main([str(data_dir), item_id, "--frames"], impls=impls) == 0
    err = capsys.readouterr().err
    assert "Pi 运行：输入 40000、输出 2000" in err
    assert "一次性调用 1 次" in err and "美元" in err


def test_a_data_dir_from_before_the_latest_schema_is_brought_up_to_date_first(tmp_path):
    """Like the app at startup: the preview data dir was still at schema 4 (no stage_detail)."""
    import sqlite3

    from prometheus import paths

    data_dir = tmp_path / "data"
    paths.init_data_dir(data_dir)
    conn = sqlite3.connect(paths.db_path(data_dir))
    conn.executescript(db.SCHEMA_V1)
    conn.execute("INSERT INTO schema_version (version) VALUES (4)")
    conn.execute("INSERT INTO items (id, platform, video_id, source_url, figures, status, created_at)"
                 " VALUES ('a', 'bilibili', 'BV1', 'u', 0, 'done', 'now')")
    conn.commit()
    conn.close()
    ran = []
    impls = {"report": lambda ctx: ran.append(ctx.item_id)}
    assert load_script().main([str(data_dir), "a"], impls=impls) == 0
    assert ran == ["a"]
