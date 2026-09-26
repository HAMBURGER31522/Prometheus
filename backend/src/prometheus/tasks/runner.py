"""Stage definitions and the sequential runner (PLAN 8.3)."""

import json
import time
from datetime import UTC, datetime

from prometheus import paths
from prometheus.library import items as items_store

STAGES = [
    "resolve", "download", "transcribe", "transcript", "frames",
    "report", "finalize", "mindmap", "classify",
]


class TaskCancelled(Exception):
    pass


def not_implemented(ctx):
    raise NotImplementedError("real stages land in M3-M6; use PROMETHEUS_FAKE=1 for E2E")


REAL_IMPLS = {stage: not_implemented for stage in STAGES}


class StageContext:
    def __init__(self, data_dir, item_id):
        self.data_dir = data_dir
        self.item_id = item_id
        self.cancel_requested = False


class _Trace:
    """Append one JSON line per stage event to work/run.trace.jsonl (PLAN 8.3)."""

    def __init__(self, ctx):
        self.path = paths.work_dir(ctx.data_dir, ctx.item_id) / "run.trace.jsonl"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.run = datetime.now(UTC).isoformat()

    def write(self, stage: str, event: str, **fields) -> None:
        line = {"run": self.run, "stage": stage, "event": event,
                "at": datetime.now(UTC).isoformat(), **fields}
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(line, ensure_ascii=False) + "\n")


def run_item(ctx, impls) -> None:
    """Run every stage in order; raise TaskCancelled when cancellation is set."""
    trace = _Trace(ctx)
    for stage in STAGES:
        if ctx.cancel_requested:
            raise TaskCancelled()
        items_store.update_item(ctx.data_dir, ctx.item_id, stage=stage)
        impl = impls.get(stage)
        trace.write(stage, "start")
        started = time.monotonic()
        try:
            if impl is not None:
                impl(ctx)
        except BaseException as exc:
            event = "cancelled" if ctx.cancel_requested else "error"
            trace.write(stage, event, elapsed_s=round(time.monotonic() - started, 3),
                        error=f"{type(exc).__name__}: {exc}"[:500])
            raise
        trace.write(stage, "end", elapsed_s=round(time.monotonic() - started, 3))
        if ctx.cancel_requested:
            raise TaskCancelled()
