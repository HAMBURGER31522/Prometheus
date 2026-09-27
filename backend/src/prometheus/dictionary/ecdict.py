"""ECDICT (MIT, github.com/skywind3000/ECDICT) as a local component (PLAN 15.4.9).

The CSV (66 MB, about 23 MB gzip-compressed on the wire) is streamed once into SQLite,
keeping single words that have a Chinese translation. A lookup returns the word's phonetic
and translation; an inflected form (went) shows its lemma (go) through ECDICT's exchange
field, and a form the dictionary lacks falls back to plain suffix rules.
"""

import csv
import gzip
import io
import re
import sqlite3
import zlib
from contextlib import closing
from pathlib import Path

from prometheus import paths

SOURCE = "https://raw.githubusercontent.com/skywind3000/ECDICT/master/ecdict.csv"
DOWNLOAD_MB = 23
INFLECTIONS = {"p": "过去式", "d": "过去分词", "i": "现在分词", "3": "第三人称单数",
               "r": "比较级", "t": "最高级", "s": "复数"}
_WORD = re.compile(r"[A-Za-z][A-Za-z'-]*")  # phrases, affixes and symbols are left out
_SUFFIXES = (("ies", "y"), ("ied", "y"), ("ying", "ie"), ("ing", ""), ("ing", "e"), ("ed", ""), ("ed", "e"),
             ("es", ""), ("s", ""), ("er", ""), ("est", ""))
_BATCH = 5000


class NotInstalled(Exception):
    pass


class DictionaryInstallError(Exception):
    pass


def db_path(data_dir) -> Path:
    return paths.models_dir(data_dir) / "ecdict" / "ecdict.db"


def installed(data_dir) -> bool:
    return db_path(data_dir).is_file()


def parse_exchange(text: str) -> dict:
    """"p:went/d:gone/0:go/1:p" -> {"p": "went", "d": "gone", "0": "go", "1": "p"}."""
    pairs = (part.split(":", 1) for part in (text or "").split("/") if ":" in part)
    return {kind: value for kind, value in pairs}


def _open(source: str, *, proxy: str = ""):
    """(binary stream, total bytes or None, gzip-encoded?) for a URL or a local file."""
    if not source.startswith(("http://", "https://")):
        path = Path(source)
        return path.open("rb"), path.stat().st_size, path.suffix == ".gz"
    import urllib.request

    handlers = [urllib.request.ProxyHandler({"http": proxy, "https": proxy})] if proxy.strip() else []
    request = urllib.request.Request(source, headers={"Accept-Encoding": "gzip", "User-Agent": "Prometheus"})
    response = urllib.request.build_opener(*handlers).open(request, timeout=60)
    total = int(response.headers.get("Content-Length") or 0) or None
    return response, total, response.headers.get("Content-Encoding") == "gzip"


class _Counting(io.RawIOBase):
    """Reports how many bytes of the download have been read."""

    def __init__(self, raw, report):
        self.raw, self.report, self.done = raw, report, 0

    def readable(self) -> bool:
        return True

    def readinto(self, buffer) -> int:
        count = self.raw.readinto(buffer)
        self.done += count or 0
        self.report(self.done)
        return count


def _build(rows, target: Path) -> int:
    header = next(rows)
    column = {name: index for index, name in enumerate(header)}
    target.unlink(missing_ok=True)
    count = 0
    with closing(sqlite3.connect(target)) as db:
        db.execute("CREATE TABLE words (key TEXT PRIMARY KEY, word TEXT, phonetic TEXT, translation TEXT, "
                   "exchange TEXT) WITHOUT ROWID")
        # The lowercase entry wins over a capitalised one (polish, not Polish).
        upsert = ("INSERT INTO words VALUES (?, ?, ?, ?, ?) ON CONFLICT(key) DO UPDATE SET word = excluded.word, "
                  "phonetic = excluded.phonetic, translation = excluded.translation, exchange = excluded.exchange "
                  "WHERE excluded.word = excluded.key")
        batch = []
        for row in rows:
            if len(row) < len(header):  # a ragged line: skip it rather than lose the dictionary
                continue
            word, translation = row[column["word"]].strip(), row[column["translation"]].strip()
            if not translation or not _WORD.fullmatch(word):
                continue
            batch.append((word.lower(), word, row[column["phonetic"]], translation, row[column["exchange"]]))
            if len(batch) >= _BATCH:
                db.executemany(upsert, batch)
                count += len(batch)
                batch = []
        db.executemany(upsert, batch)
        count += len(batch)
        db.commit()
    return count


def install(data_dir, *, source: str = SOURCE, proxy: str = "", open_source=None, progress=None) -> None:
    """Download and build to ecdict.db.part, then rename: a cut download never looks complete.
    `progress(done_bytes, total_bytes_or_None)` follows the download."""
    target = db_path(data_dir)
    target.parent.mkdir(parents=True, exist_ok=True)
    partial = target.with_name(target.name + ".part")
    try:
        stream, total, gzipped = (open_source or _open)(source, proxy=proxy)
        with stream:
            counted = io.BufferedReader(_Counting(stream, lambda done: progress and progress(done, total)))
            binary = gzip.GzipFile(fileobj=counted) if gzipped else counted
            count = _build(csv.reader(io.TextIOWrapper(binary, encoding="utf-8", newline="")), partial)
    except (OSError, EOFError, zlib.error, csv.Error, UnicodeDecodeError, sqlite3.Error, StopIteration) as exc:
        partial.unlink(missing_ok=True)
        raise DictionaryInstallError(f"离线词典下载失败：{exc}") from exc
    if count == 0:
        partial.unlink(missing_ok=True)
        raise DictionaryInstallError("离线词典下载失败：内容是空的")
    partial.replace(target)


def _candidates(word: str):
    for suffix, replacement in _SUFFIXES:
        if word.endswith(suffix) and len(word) - len(suffix) >= 2:
            stem = word[: -len(suffix)] + replacement
            yield stem
            if not replacement and len(stem) >= 3 and stem[-1] == stem[-2]:
                yield stem[:-1]  # stopped -> stop


def lookup(data_dir, word: str):
    """{"query", "headword", "phonetic", "translation": [lines], "inflection"} or None."""
    path = db_path(data_dir)
    if not path.is_file():
        raise NotInstalled
    query = word.strip()
    key = query.lower()
    with closing(sqlite3.connect(f"{path.as_uri()}?mode=ro", uri=True)) as db:
        def get(candidate):
            return db.execute("SELECT word, phonetic, translation, exchange FROM words WHERE key = ?",
                              (candidate,)).fetchone()

        row, inflection = get(key), None
        if row is not None:
            exchange = parse_exchange(row[3])
            lemma = exchange.get("0", "").lower()
            base = get(lemma) if lemma and lemma != key else None
            if base is not None:
                row = base
                inflection = "、".join(INFLECTIONS[kind] for kind in exchange.get("1", "") if kind in INFLECTIONS) or None
        else:
            row = next((found for candidate in _candidates(key) if (found := get(candidate))), None)
    if row is None:
        return None
    return {
        "query": query,
        "headword": row[0],
        "phonetic": row[1] or "",
        "translation": [line.strip() for line in row[2].replace("\\n", "\n").splitlines() if line.strip()],
        "inflection": inflection,
    }
