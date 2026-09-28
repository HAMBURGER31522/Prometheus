"""Serial task queue (PLAN 8.3): one running item at a time."""

import threading
from datetime import UTC, datetime

from prometheus import paths
from prometheus.library import items as items_store
from prometheus.tasks import cleanup, errors, processes, runner

# 「重新生成导图」(PLAN 8.8): a finished item reruns only these and stays done.
MINDMAP_STAGES = ("mindmap", "publish")
# 「补全标签和摘要」(PLAN 15.4.10): classify keeps the category, so only tags and description change.
TAG_STAGES = ("classify", "publish")


def _now() -> str:
    return datetime.now(UTC).isoformat()


class TaskQueue:
    def __init__(self, data_dir, impls):
        self.data_dir = data_dir
        self.impls = impls
        self._lock = threading.Lock()
        self._wake = threading.Event()
        self._current = None
        self._mindmap_reruns = []  # item ids, oldest first
        self._tag_reruns = []  # item ids, oldest first
        self._stop_requested = False
        self._thread = None

    def start(self) -> None:
        if self._thread is None:
            self._thread = threading.Thread(target=self._loop, daemon=True)
            self._thread.start()

    def stop(self) -> None:
        self._stop_requested = True
        self._wake.set()

    def enqueue(self, item_id) -> None:
        with self._lock:
            current = self._current
        if current is not None and current.item_id == item_id:
            return
        self._wake.set()

    def enqueue_mindmap(self, item_id) -> None:
        """Rerun only the mind map of a finished item; mindmap_status stays NULL until it ends."""
        items_store.update_item(self.data_dir, item_id, mindmap_status=None)
        with self._lock:
            if item_id not in self._mindmap_reruns:
                self._mindmap_reruns.append(item_id)
        self._wake.set()

    def enqueue_tags(self, item_id) -> None:
        """Rerun classify + publish on a finished item that has no tags yet; it stays done."""
        with self._lock:
            if item_id not in self._tag_reruns:
                self._tag_reruns.append(item_id)
        self._wake.set()

    def cancel(self, item_id) -> bool:
        with self._lock:
            current = self._current
            waiting = item_id in self._mindmap_reruns
            if waiting:
                self._mindmap_reruns.remove(item_id)
            if item_id in self._tag_reruns:
                self._tag_reruns.remove(item_id)
        if current is not None and current.item_id == item_id:
            current.cancel_requested = True
            # The running stage is blocked on Pi / whisper / ffmpeg: end them now.
            processes.kill_children()
            self._wake.set()
            return True
        if waiting:
            items_store.update_item(self.data_dir, item_id, mindmap_status="failed")
            return True
        row = items_store.get_item(self.data_dir, item_id)
        if row is not None and row["status"] == "queued":
            items_store.update_item(
                self.data_dir, item_id, status="cancelled", stage=None, finished_at=_now(),
            )
            return True
        return False

    def is_running(self, item_id) -> bool:
        with self._lock:
            current = self._current
        return current is not None and current.item_id == item_id

    def _loop(self) -> None:
        while not self._stop_requested:
            self._wake.wait(timeout=0.2)
            self._wake.clear()
            while not self._stop_requested and self._drain_one():
                pass

    def _drain_one(self) -> bool:
        queued = items_store.list_items(self.data_dir, status="queued")
        with self._lock:
            if self._current is not None:
                return False
            # Mind map reruns are short and the user is waiting on them: they go first.
            if self._mindmap_reruns:
                item_id, rerun = self._mindmap_reruns.pop(0), True
            elif self._tag_reruns:
                item_id, rerun = self._tag_reruns.pop(0), "tags"
            elif queued:
                item_id, rerun = queued[0]["id"], False
            else:
                return False
            ctx = runner.StageContext(self.data_dir, item_id)
            self._current = ctx
        try:
            if rerun == "tags":
                self._rerun_tags(ctx)
            elif rerun:
                self._rerun_mindmap(ctx)
            else:
                self._run(ctx)
        finally:
            with self._lock:
                self._current = None
            self._wake.set()
        return True

    def _run(self, ctx) -> None:
        item_id = ctx.item_id
        items_store.update_item(
            self.data_dir, item_id, status="running", stage=runner.STAGES[0], started_at=_now(),
        )
        try:
            runner.run_item(ctx, self.impls)
        except runner.TaskCancelled:
            items_store.update_item(
                self.data_dir, item_id, status="cancelled", stage=None, finished_at=_now(),
            )
        except Exception as exc:  # noqa: BLE001 - any stage failure fails the task
            if ctx.cancel_requested:  # killed children surface as ordinary errors
                items_store.update_item(
                    self.data_dir, item_id, status="cancelled", stage=None, finished_at=_now(),
                )
            else:
                # The stage stays (PLAN 15.4.10): the console says in which step it failed.
                stage = (items_store.get_item(self.data_dir, item_id) or {}).get("stage")
                code, message = errors.describe(stage, exc)
                items_store.update_item(
                    self.data_dir, item_id, status="failed",
                    error_code=code, error_message=message, finished_at=_now(),
                )
        else:
            cleanup.clean_work_dir(paths.work_dir(self.data_dir, item_id))
            items_store.update_item(
                self.data_dir, item_id, status="done", stage=None, finished_at=_now(),
            )

    def _rerun_tags(self, ctx) -> None:
        """The item stays done; a failure just leaves it without tags (the button stays)."""
        try:
            runner.run_item(ctx, self.impls, stages=TAG_STAGES)
            cleanup.clean_work_dir(paths.work_dir(self.data_dir, ctx.item_id))
        except Exception:  # noqa: BLE001 - cancelled or broken: the item keeps no tags, the button stays
            items_store.update_item(self.data_dir, ctx.item_id, stage=None)
            return
        items_store.update_item(self.data_dir, ctx.item_id, stage=None)

    def _rerun_mindmap(self, ctx) -> None:
        """The item stays done whatever happens; only its mind map can fail."""
        try:
            runner.run_item(ctx, self.impls, stages=MINDMAP_STAGES)
        except Exception:  # noqa: BLE001 - cancelled (TaskCancelled) or broken
            items_store.update_item(self.data_dir, ctx.item_id, stage=None, mindmap_status="failed")
        else:
            cleanup.clean_work_dir(paths.work_dir(self.data_dir, ctx.item_id))
            items_store.update_item(self.data_dir, ctx.item_id, stage=None)
