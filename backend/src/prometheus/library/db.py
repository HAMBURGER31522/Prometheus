"""SQLite connection and schema management (PLAN 7.1)."""

SCHEMA_VERSION = 0


def connect(data_dir):
    raise NotImplementedError


def init_db(data_dir) -> None:
    raise NotImplementedError


def get_schema_version(conn):
    raise NotImplementedError


def mark_running_as_interrupted(data_dir) -> None:
    raise NotImplementedError
