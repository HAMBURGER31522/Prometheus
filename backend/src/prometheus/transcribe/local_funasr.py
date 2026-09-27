"""FunASR ONNX worker helpers (PLAN 15.4.4, D-39).

Paraformer returns one timestamp per token (a Chinese character or an English
word); the punctuation model returns the same tokens as one string with marks
inserted. Walking that string puts each mark back on its token, and the marks
then cut the tokens into subtitle-sized sentences.
"""

_MARKS = frozenset("，。！？；：、,.!?;:…")
_SENTENCE_END = frozenset("。！？；….!?;")
_CLAUSE = frozenset("，、,")
MAX_CHARS = 30
MAX_SECONDS = 8.0


def attach_punctuation(tokens: list, punctuated: str) -> list:
    """The punctuation that follows each token in ``punctuated`` ("" when none)."""
    marks = [""] * len(tokens)
    text = punctuated.lower()
    position = 0
    for index, token in enumerate(tokens):
        while position < len(text) and text[position].isspace():
            position += 1
        token = token.lower()
        if text.startswith(token, position):
            position += len(token)
        else:
            # The punctuated text drifted: look a little further, else leave this token bare.
            found = text.find(token, position, position + len(token) + 4)
            if found < 0:
                continue
            position = found + len(token)
        end = position
        while end < len(text) and text[end] in _MARKS:
            end += 1
        marks[index] = punctuated[position:end]
        position = end
    return marks


def _cut(items: list, marks: frozenset) -> list:
    """Split after every item whose punctuation contains one of ``marks``."""
    groups, current = [], []
    for item in items:
        current.append(item)
        if any(char in marks for char in item[1]):
            groups.append(current)
            current = []
    if current:
        groups.append(current)
    return groups


def _is_word(token: str) -> bool:
    return token.isascii() and token[:1].isalnum()


def _join(items: list) -> str:
    text, previous_word = "", False
    for token, mark, _times in items:
        if text and previous_word and _is_word(token):
            text += " "
        text += token + mark
        previous_word = _is_word(token)
    return text


def _fit(times_ms: list, count: int) -> list:
    """Paraformer can drop the timestamp of a filler (啊, "O K"): spread what there is over the tokens."""
    if len(times_ms) == count or not times_ms:
        return times_ms if times_ms else [[0, 0]] * count
    return [times_ms[min(index * len(times_ms) // count, len(times_ms) - 1)] for index in range(count)]


def build_segments(tokens: list, times_ms: list, punctuated: str, *, offset_s: float) -> list:
    """Sentences at 。！？；, long ones (> 30 characters or > 8 s) cut again at ，、."""
    times_ms = _fit(times_ms, len(tokens))
    items = list(zip(tokens, attach_punctuation(tokens, punctuated), times_ms, strict=True))
    segments = []
    for sentence in _cut(items, _SENTENCE_END):
        characters = sum(len(token) for token, _mark, _times in sentence)
        seconds = (sentence[-1][2][1] - sentence[0][2][0]) / 1000
        parts = _cut(sentence, _CLAUSE) if characters > MAX_CHARS or seconds > MAX_SECONDS else [sentence]
        for part in parts:
            segments.append({
                "start": round(offset_s + part[0][2][0] / 1000, 3),
                "end": round(offset_s + part[-1][2][1] / 1000, 3),
                "text": _join(part),
            })
    return segments
