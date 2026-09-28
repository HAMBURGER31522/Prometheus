"""Subtitle paragraphs of 10–15 seconds (PLAN 15.4.10).

Whisper and 必剪 cut speech into fragments (the 104-minute sample: median 1.3 s, 「对吧，」 alone
on a line), which are tiring to read one by one. They are joined in order into paragraphs:

- once a paragraph is 10 s long it ends at the first sentence end (。！？!?.…);
- when the next fragment would take it past 15 s it ends at the last comma-like mark (，,、；;：:,
  or a sentence end that came before 10 s), else after the last fragment that fits, so it can be
  shorter than 10 s; the end of the transcript stays together when it fits;
- a single fragment longer than 15 s is first split at its punctuation, with the time shared out
  by character count; a piece still longer than 15 s is split evenly by characters.

Words are joined with a space unless either side is Chinese or Japanese; no character is lost or
changed. The corrected and the raw transcript are grouped on the same boundaries, so switching
to 「原始识别」 shows the same paragraphs.
"""

import math
import unicodedata
from itertools import pairwise
from typing import NamedTuple

MIN_SECONDS = 10.0
MAX_SECONDS = 15.0
SENTENCE_END = frozenset("。！？!?.…")
PAUSE = frozenset("，,、；;：:")
BREAKS = SENTENCE_END | PAUSE
_CLOSERS = frozenset("\"'”’）)」』】]》")


class _Piece(NamedTuple):
    index: int  # the segment it comes from
    begin: int  # its characters in that segment's text
    stop: int
    start: float
    end: float
    lead: bool  # the first piece of its segment carries the segment's translation


def _letter(char: str) -> bool:
    return unicodedata.category(char)[0] in "LN"


def _mark(text: str) -> str:
    """The last character that is not a space or a closing quote or bracket."""
    for char in reversed(text):
        if not char.isspace() and char not in _CLOSERS:
            return char
    return ""


def _tight(char: str) -> bool:
    """Chinese and Japanese are written without spaces between words (Korean keeps them)."""
    return unicodedata.east_asian_width(char) in ("W", "F") and not "가" <= char <= "힣"


def _join(parts) -> str:
    text = ""
    for part in parts:
        part = part.strip()
        if part:
            text += ("" if not text or _tight(text[-1]) or _tight(part[0]) else " ") + part
    return text


def _wordish(char: str) -> bool:
    return (char.isascii() and (char.isalnum() or char in "'-.,")) or char == "’"


def _clause_ends(text: str) -> list:
    """Where the text can be cut after its marks; a mark followed by a Latin letter or a digit
    (3.5, 1,000) is part of a word."""
    cuts, position = [], 0
    while position < len(text):
        if text[position] not in BREAKS:
            position += 1
            continue
        after = position + 1
        while after < len(text) and (text[after] in BREAKS or text[after] in _CLOSERS):
            after += 1
        if after < len(text) and not (text[after].isascii() and text[after].isalnum()):
            cuts.append(after)
        position = after
    return cuts


def _safe_cut(text: str, target: int) -> int:
    """The place nearest to `target` that is not inside a Latin word or a number."""
    for distance in range(len(text)):
        for position in (target - distance, target + distance):
            if 0 < position < len(text) and not (_wordish(text[position - 1]) and _wordish(text[position])):
                return position
    return target


def _share(texts: list, start: float, end: float) -> list:
    """(start, end) of each text, the time shared out by character count."""
    weights = [sum(map(_letter, text)) for text in texts]
    if not sum(weights):
        weights = [len(text.strip()) for text in texts]
    if not sum(weights):
        weights = [1] * len(texts)
    total, done, bounds = sum(weights), 0, [start]
    for weight in weights:
        done += weight
        bounds.append(start + (end - start) * done / total)
    bounds[-1] = end
    return list(pairwise(bounds))


def _split(index: int, segment: dict) -> list:
    """A segment as pieces of at most 15 s."""
    start, end, text = segment["start"], segment["end"], segment["text"]
    if end - start <= MAX_SECONDS:
        return [_Piece(index, 0, len(text), start, end, True)]
    bounds = [0, *_clause_ends(text), len(text)]
    clauses = list(pairwise(bounds))
    pieces = []
    for (begin, stop), (clause_start, clause_end) in zip(
            clauses, _share([text[a:b] for a, b in clauses], start, end)):
        length = clause_end - clause_start
        count = math.floor(length / MAX_SECONDS) + 1 if length > MAX_SECONDS else 1
        cuts = [begin]
        for k in range(1, count):  # evenly by characters, each piece the same time
            cuts.append(max(cuts[-1], begin + _safe_cut(text[begin:stop], round((stop - begin) * k / count))))
        cuts.append(stop)
        for k, (a, b) in enumerate(pairwise(cuts)):
            piece_end = clause_end if k == count - 1 else clause_start + length * (k + 1) / count
            pieces.append(_Piece(index, a, b, clause_start + length * k / count, piece_end, not pieces))
    return pieces


def _pieces(segments: list) -> list:
    return [piece for index, segment in enumerate(segments) for piece in _split(index, segment)]


def _text(segments: list, piece: _Piece) -> str:
    return segments[piece.index]["text"][piece.begin:piece.stop]


def _ranges(segments: list, pieces: list) -> list:
    """(first, last) piece of each paragraph."""
    ranges, first = [], 0
    while first < len(pieces):
        start, end, last, chosen = pieces[first].start, pieces[first].end, first, None
        for position in range(first, len(pieces)):
            end = max(end, pieces[position].end)
            if position > first and end - start > MAX_SECONDS:
                break
            last = position
            if end - start >= MIN_SECONDS and _mark(_text(segments, pieces[position])) in SENTENCE_END:
                chosen = position
                break
        if chosen is None:
            breaks = [p for p in range(first, last + 1) if _mark(_text(segments, pieces[p])) in BREAKS]
            chosen = last if last == len(pieces) - 1 or not breaks else breaks[-1]
        ranges.append((first, chosen))
        first = chosen + 1
    return ranges


def _paragraph(segments: list, pieces: list) -> dict:
    paragraph = {"start": pieces[0].start, "end": max(piece.end for piece in pieces),
                 "text": _join(_text(segments, piece) for piece in pieces)}
    zh = _join(segments[piece.index]["zh"] for piece in pieces if piece.lead and segments[piece.index].get("zh"))
    if zh:
        paragraph["zh"] = zh
    return paragraph


def group_segments(segments: list) -> list:
    """Paragraphs [{"start", "end", "text"(, "zh")}] of ordered segments."""
    pieces = _pieces(segments)
    return [_paragraph(segments, pieces[first:last + 1]) for first, last in _ranges(segments, pieces)]


def _follow(source: str, target: str, offset: int) -> int:
    """Where a cut in `source` falls in `target`: after as many letters, and the marks after them."""
    if offset <= 0:
        return 0
    if offset >= len(source):
        return len(target)
    wanted, seen, position = sum(map(_letter, source[:offset])), 0, 0
    while position < len(target) and seen < wanted:
        seen += _letter(target[position])
        position += 1
    while position < len(target) and not _letter(target[position]) and not target[position].isspace():
        position += 1
    return position


def group_pair(shown: list, raw: list) -> tuple:
    """Paragraphs of the corrected subtitles, and of the raw ones cut at the same places (raw
    segments that do not line up with the corrected ones are grouped on their own)."""
    pieces = _pieces(shown)
    ranges = _ranges(shown, pieces)
    grouped = [_paragraph(shown, pieces[first:last + 1]) for first, last in ranges]
    if len(raw) != len(shown):
        return grouped, group_segments(raw)

    def follow(piece: _Piece) -> _Piece:
        source, target = shown[piece.index]["text"], raw[piece.index]["text"]
        return piece._replace(begin=_follow(source, target, piece.begin), stop=_follow(source, target, piece.stop))

    mapped = [follow(piece) for piece in pieces]
    return grouped, [_paragraph(raw, mapped[first:last + 1]) for first, last in ranges]


def convert_library(data_dir) -> int:
    return 0
