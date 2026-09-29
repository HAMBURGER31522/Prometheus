"""Write only the 精读 of finished items again (PLAN 15.4.11 experiments).

    python scripts/report-eval/rewrite.py <data dir> <item id> [<item id> ...] [--frames]

Runs 提取要点 → 规划 → report → finalize → publish with the data dir's settings (精读详细程度
included) and the item's kept transcript; subtitles and the mind map stay as they are, so only the
report calls the user's model. Save the old 精读.html first if you want to compare
(report-eval/run.py --report ID=PATH).

--frames: the finished item's video and frames were cleaned away; turn 配图 on for it, download the
video again and extract frames first, and clean the scratch up again after a successful run.
"""

import argparse
import sys
import time
from pathlib import Path

from prometheus import paths
from prometheus import runtime as runtime_mod
from prometheus.library import db
from prometheus.library import items as items_store
from prometheus.llm import one_shot
from prometheus.report import evaluation
from prometheus.tasks import cleanup, runner
from prometheus.tasks.stages import build_real_impls

STAGES = ("keypoints", "plan", "report", "finalize", "publish")
WITH_FRAMES = ("download", "frames", *STAGES)
one_shot_call = one_shot.run_one_shot  # the real call; tests put a fake here


def main(argv=None, impls=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("data_dir", type=Path)
    parser.add_argument("items", nargs="+")
    parser.add_argument("--frames", action="store_true")
    parser.add_argument("--patch", action="store_true")
    args = parser.parse_args(argv)
    data_dir = args.data_dir.resolve()  # Pi runs elsewhere: relative paths would point astray
    db.init_db(data_dir)  # an older data dir gets the new columns, as the app does at startup

    rows = [items_store.get_item(data_dir, item_id) for item_id in args.items]
    refused = [item_id for item_id, row in zip(args.items, rows, strict=True) if not row or row["status"] != "done"]
    if refused:
        print(f"只能重写已完成的条目：{', '.join(refused)}", file=sys.stderr)
        return 2
    impls = impls if impls is not None else build_real_impls(data_dir, runtime=runtime_mod.resolve(None))
    calls: list = []

    def tallied(work_dir, **kwargs):
        reply = one_shot_call(work_dir, **kwargs)
        calls.append({"in": kwargs.get("prompt") or "", "out": reply or "", "images": len(kwargs.get("files") or ())})
        return reply

    original, one_shot.run_one_shot = one_shot.run_one_shot, tallied
    try:
        for row in rows:
            _rewrite(data_dir, row, impls, calls, frames=args.frames)
    finally:
        one_shot.run_one_shot = original
    return 0


def _rewrite(data_dir, row: dict, impls: dict, calls: list, *, frames: bool) -> None:
    started, work = time.monotonic(), paths.work_dir(data_dir, row["id"])
    since, calls[:] = evaluation.pi_events_offsets(work), []
    stages = WITH_FRAMES if frames else STAGES
    if not row.get("tags"):  # items from before tags (15.4.10) get them on the way; the category stays
        stages = (*stages[:-1], "classify", stages[-1])
    ctx = runner.StageContext(data_dir, row["id"])
    if frames:
        items_store.update_item(data_dir, row["id"], figures=1)
    try:
        runner.run_item(ctx, impls, stages=stages)
    finally:
        items_store.update_item(data_dir, row["id"], stage=None, stage_detail=None)
        _spend(work, since, calls)
    if frames:
        cleanup.clean_work_dir(work)
    print(f"{row.get('report_title') or row['id']}：重写完成，用时 {time.monotonic() - started:.0f} 秒", file=sys.stderr)


def _spend(work, since: dict, calls: list) -> None:
    """What this run cost: Pi's own records for the agent runs, characters for the one-shot calls."""
    pi = evaluation.pi_usage(work, since)
    shot = evaluation.estimate_cost(calls)
    images = sum(call["images"] for call in calls)
    image_usd = images * evaluation.IMAGE_TOKENS * evaluation.PRICE_IN / 1_000_000
    print(f"  Pi 运行：输入 {pi['input']}、输出 {pi['output']}、缓存命中 {pi['cacheRead']} token"
          f"（{pi['replies']} 次回复），约 {pi['usd']:.2f} 美元", file=sys.stderr)
    print(f"  一次性调用 {len(calls)} 次：输入约 {shot['tokens_in']}、输出约 {shot['tokens_out']} token，附图 {images} 张，"
          f"约 {shot['usd'] + image_usd:.2f} 美元（按字数估算）", file=sys.stderr)
    print(f"  合计约 {pi['usd'] + shot['usd'] + image_usd:.2f} 美元（按 claude-opus-4-8 官方价）", file=sys.stderr)


if __name__ == "__main__":
    sys.exit(main())
