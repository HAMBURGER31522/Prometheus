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
from prometheus.library import items as items_store
from prometheus.llm import one_shot
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
    args = parser.parse_args(argv)
    data_dir = args.data_dir.resolve()  # Pi runs elsewhere: relative paths would point astray

    rows = [items_store.get_item(data_dir, item_id) for item_id in args.items]
    refused = [item_id for item_id, row in zip(args.items, rows, strict=True) if not row or row["status"] != "done"]
    if refused:
        print(f"只能重写已完成的条目：{', '.join(refused)}", file=sys.stderr)
        return 2
    one_shot.run_one_shot = lambda work_dir, **kwargs: one_shot_call(work_dir, **kwargs)
    impls = impls if impls is not None else build_real_impls(data_dir, runtime=runtime_mod.resolve(None))
    for row in rows:
        started = time.monotonic()
        ctx = runner.StageContext(data_dir, row["id"])
        if args.frames:
            items_store.update_item(data_dir, row["id"], figures=1)
        try:
            runner.run_item(ctx, impls, stages=WITH_FRAMES if args.frames else STAGES)
        finally:
            items_store.update_item(data_dir, row["id"], stage=None, stage_detail=None)
        if args.frames:
            cleanup.clean_work_dir(paths.work_dir(data_dir, row["id"]))
        print(f"{row.get('report_title') or row['id']}：重写完成，用时 {time.monotonic() - started:.0f} 秒",
              file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
