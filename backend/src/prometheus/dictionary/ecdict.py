"""ECDICT (MIT, github.com/skywind3000/ECDICT) as a local component (PLAN 15.4.9).

The CSV (66 MB, about 23 MB gzip-compressed on the wire) is streamed once into SQLite,
keeping single words that have a Chinese translation. A lookup returns the word's phonetic
and translation; an inflected form (went) shows its lemma (go) through ECDICT's exchange
field, and a form the dictionary lacks falls back to plain suffix rules.

Up to three English definitions (ECDICT's definition field, mostly WordNet) come with it
(PLAN 15.4.10). A dictionary built before that has no such column: its lookups still work
and say `needs_update`, and installing again rebuilds it.
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
DEFINITIONS = 3
# Parts of speech as the Chinese meanings (vt.) and the WordNet definitions (v., s. for adjectives) write them.
_POS = {"n": "n", "v": "v", "vt": "v", "vi": "v", "a": "a", "adj": "a", "s": "a", "ad": "r", "adv": "r", "r": "r"}
_POS_MARK = re.compile(r"([a-z]+)\.?\s")


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
                   "exchange TEXT, definition TEXT) WITHOUT ROWID")
        # The lowercase entry wins over a capitalised one (polish, not Polish).
        upsert = ("INSERT INTO words VALUES (?, ?, ?, ?, ?, ?) ON CONFLICT(key) DO UPDATE SET word = excluded.word, "
                  "phonetic = excluded.phonetic, translation = excluded.translation, exchange = excluded.exchange, "
                  "definition = excluded.definition WHERE excluded.word = excluded.key")
        batch = []
        for row in rows:
            if len(row) < len(header):  # a ragged line: skip it rather than lose the dictionary
                continue
            word, translation = row[column["word"]].strip(), row[column["translation"]].strip()
            if not translation or not _WORD.fullmatch(word):
                continue
            batch.append((word.lower(), word, row[column["phonetic"]], translation, row[column["exchange"]],
                          row[column["definition"]] if "definition" in column else ""))
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


def _lines(text: str) -> list:
    """ECDICT keeps its line breaks as a literal \\n (a few rows \\r\\n)."""
    return (text or "").replace("\\r", "").replace("\\n", "\n").splitlines()


def _part_of_speech(line: str) -> str:
    match = _POS_MARK.match(line)
    return _POS.get(match.group(1), "") if match else ""


def _definitions(text: str, translation: list) -> list:
    """Up to three English definitions, those with the part of speech of the first Chinese meaning
    first (went → go: the verb senses before "a board game"). An indented line continues the one
    before it (the older, Webster-style entries wrap their lines)."""
    lines = []
    for line in _lines(text):
        if line.strip() and line[0].isspace() and lines:
            lines[-1] += " " + line.strip()
        elif line.strip():
            lines.append(line.strip())
    first = _part_of_speech(translation[0]) if translation else ""
    if first:
        lines.sort(key=lambda line: _part_of_speech(line) != first)
    return lines[:DEFINITIONS]


def lookup(data_dir, word: str):
    """{"query", "headword", "phonetic", "translation": [lines], "inflection", "definition": [up to 3],
    "needs_update"} or None."""
    path = db_path(data_dir)
    if not path.is_file():
        raise NotInstalled
    query = word.strip()
    key = query.lower()
    with closing(sqlite3.connect(f"{path.resolve().as_uri()}?mode=ro", uri=True)) as db:
        # Dictionaries installed before English definitions lack the column (R7c).
        outdated = "definition" not in {column[1] for column in db.execute("PRAGMA table_info(words)")}
        select = ("SELECT word, phonetic, translation, exchange, '' FROM words WHERE key = ?" if outdated
                  else "SELECT word, phonetic, translation, exchange, definition FROM words WHERE key = ?")

        def get(candidate):
            return db.execute(select, (candidate,)).fetchone()

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
    translation = [line.strip() for line in _lines(row[2]) if line.strip()]
    return {
        "query": query,
        "headword": row[0],
        "phonetic": row[1] or "",
        "translation": translation,
        "inflection": inflection,
        "definition": _definitions(row[4], translation),
        "needs_update": outdated,
    }
