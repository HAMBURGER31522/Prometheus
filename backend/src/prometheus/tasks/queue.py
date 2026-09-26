"""Serial task queue (PLAN 8.3)."""


class TaskQueue:
    def __init__(self, data_dir, impls):
        self.data_dir = data_dir
        self.impls = impls

    def start(self) -> None:
        raise NotImplementedError

    def stop(self) -> None:
        raise NotImplementedError

    def enqueue(self, item_id) -> None:
        raise NotImplementedError

    def cancel(self, item_id) -> bool:
        raise NotImplementedError
