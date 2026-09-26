"""Stage definitions and the sequential runner (PLAN 8.3)."""

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


def run_item(ctx, impls) -> None:
    """Run every stage in order; raise TaskCancelled when cancellation is set."""
    for stage in STAGES:
        if ctx.cancel_requested:
            raise TaskCancelled()
        items_store.update_item(ctx.data_dir, ctx.item_id, stage=stage)
        impl = impls.get(stage)
        if impl is not None:
            impl(ctx)
        if ctx.cancel_requested:
            raise TaskCancelled()
