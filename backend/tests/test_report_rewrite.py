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
