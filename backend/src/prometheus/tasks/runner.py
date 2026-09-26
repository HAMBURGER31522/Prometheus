"""Stage definitions and the sequential runner (PLAN 8.3)."""

STAGES = []


class TaskCancelled(Exception):
    pass


class StageContext:
    def __init__(self, data_dir, item_id):
        self.data_dir = data_dir
        self.item_id = item_id
        self.cancel_requested = False


def run_item(ctx, impls):
    raise NotImplementedError
