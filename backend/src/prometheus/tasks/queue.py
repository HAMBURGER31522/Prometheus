"""Serial task queue (PLAN 8.3): one running item at a time."""

import threading
from datetime import UTC, datetime

from prometheus import paths
from prometheus.library import items as items_store
from prometheus.tasks import cleanup, errors, processes, runner


def _now() -> str:
    return datetime.now(UTC).isoformat()


class TaskQueue:
    def __init__(self, data_dir, impls):
        self.data_dir = data_dir
        self.impls = impls
        self._lock = threading.Lock()
        self._wake = threading.Event()
        self._current = None
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

    def cancel(self, item_id) -> bool:
        with self._lock:
            current = self._current
        if current is not None and current.item_id == item_id:
            current.cancel_requested = True
            # The running stage is blocked on Pi / whisper / ffmpeg: end them now.
            processes.kill_children()
            self._wake.set()
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
        if not queued:
            return False
        item = queued[0]
        ctx = runner.StageContext(self.data_dir, item["id"])
        with self._lock:
            if self._current is not None:
                return False
            self._current = ctx
        try:
            items_store.update_item(
                self.data_dir, item["id"], status="running", stage=runner.STAGES[0],
                started_at=_now(),
            )
            try:
                runner.run_item(ctx, self.impls)
            except runner.TaskCancelled:
                items_store.update_item(
                    self.data_dir, item["id"], status="cancelled", stage=None,
                    finished_at=_now(),
                )
            except Exception as exc:  # noqa: BLE001 - any stage failure fails the task
                if ctx.cancel_requested:  # killed children surface as ordinary errors
                    items_store.update_item(
                        self.data_dir, item["id"], status="cancelled", stage=None,
                        finished_at=_now(),
                    )
                else:
                    code, message = errors.describe(exc)
                    items_store.update_item(
                        self.data_dir, item["id"], status="failed", stage=None,
                        error_code=code, error_message=message, finished_at=_now(),
                    )
            else:
                cleanup.clean_work_dir(paths.work_dir(self.data_dir, item["id"]))
                items_store.update_item(
                    self.data_dir, item["id"], status="done", stage=None,
                    finished_at=_now(),
                )
        finally:
            with self._lock:
                self._current = None
            self._wake.set()
        return True
