"""ECDICT (MIT, github.com/skywind3000/ECDICT) as a local component (PLAN 15.4.9)."""

from pathlib import Path

from prometheus import paths

SOURCE = "https://raw.githubusercontent.com/skywind3000/ECDICT/master/ecdict.csv"


class NotInstalled(Exception):
    pass


class DictionaryInstallError(Exception):
    pass


def db_path(data_dir) -> Path:
    return paths.models_dir(data_dir) / "ecdict" / "ecdict.db"


def installed(data_dir) -> bool:
    return False


def parse_exchange(text: str) -> dict:
    return {}


def install(data_dir, *, source: str = SOURCE, proxy: str = "", open_source=None, progress=None) -> None:
    return None


def lookup(data_dir, word: str):
    return None
