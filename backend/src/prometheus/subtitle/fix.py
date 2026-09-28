"""Subtitle correction after the report (PLAN 15.4.6, D-37).

VRA's agent already fixes misheard names while it writes the report, but leaves
the transcript alone. This stage hands the report back to the model as a
glossary and asks it to fix the subtitles' homophones and add punctuation.
Every segment's change is capped, so a model that starts paraphrasing cannot
rewrite the subtitles; the ASR original stays in segments.raw.json. A transcript in
another language also gets a Chinese line per segment in the same call (PLAN 15.4.9).
"""

import json
import math
import shutil
import unicodedata
from concurrent.futures import ThreadPoolExecutor

from prometheus import paths
from prometheus.library import items as items_store

MAX_REFERENCE = 12000
# 「每次最多 120 段（约 2500 字）」: a 10–15 s paragraph (PLAN 15.4.10) holds 50–150 characters.
BATCH, BATCH_CHARS = 120, 2500
TRANSLATE_BATCH, TRANSLATE_BATCH_CHARS = 60, 1250  # the reply carries the text and its translation (15.4.9)
CHINESE = frozenset({"zh", "yue"})
WORKERS = 3
SEGMENTS_MARK = "字幕分段（JSON）：\n"


def _letters(text: str) -> list:
    return [char for char in text.lower() if unicodedata.category(char)[0] in "LN"]


def _distance(a: list, b: list) -> int:
    previous = list(range(len(b) + 1))
    for i, left in enumerate(a, 1):
        current = [i]
        for j, right in enumerate(b, 1):
            current.append(min(previous[j] + 1, current[j - 1] + 1, previous[j - 1] + (left != right)))
        previous = current
    return previous[-1]


def accept(original: str, corrected: str) -> bool:
    """Punctuation is free; the words may change by max(2, 30% of their length) edits."""
    if original.strip() and not corrected.strip():
        return False
    before, after = _letters(original), _letters(corrected)
    return _distance(before, after) <= max(2, math.ceil(len(before) * 0.3))


def accept_translation(original: str, zh: str) -> bool:
    """Chinese, not the original again, and not swollen with the neighbours' content."""
    if not isinstance(zh, str) or not zh.strip() or zh.strip() == original.strip():
        return False
    if not any("一" <= char <= "鿿" for char in zh):
        return False
    return len(_letters(zh)) <= len(_letters(original)) + 10


def parse_reply(text: str):
    """The first JSON object in the reply (models add prose and code fences), else None."""
    decoder = json.JSONDecoder()
    text = text or ""
    start = text.find("{")
    while start != -1:
        try:
            value, _ = decoder.raw_decode(text, start)
        except ValueError:
            start = text.find("{", start + 1)
            continue
        if isinstance(value, dict):
            return value
        start = text.find("{", start + 1)
    return None


def build_prompt(batch: dict, reference: str, *, human: bool, translate: bool = False) -> str:
    if human:
        rules = ["这是视频作者上传的人工字幕，文字已经正确：只补标点，不要改动任何字词。"]
    else:
        rules = [
            "这是语音识别的结果，可能有同音字、近音词、专有名词写错。请结合上下文和下面的参考材料改正这些错字，并补全标点。",
            "只改识别错误：不增删内容，不改说法，不润色，语气词和口语保留原样。",
            "参考材料是根据同一段视频写成的报告，其中的人名、术语、作品名可信；字幕不必和报告措辞一致。",
        ]
    if translate:
        rules.append("再给每段写中文翻译：忠实、通顺，只译这一段；人名、术语参照参考材料里的译法。")
        output = '输出与输入段号相同的 JSON 对象 {"段号": {"text": "改好的原文", "zh": "中文翻译"}}，每一段都要有。'
    else:
        output = '输出与输入段号相同的 JSON 对象 {"段号": "改好的文本"}，每一段都要有。'
    lines = [
        "下面是一段视频的字幕，按段号给出。",
        *rules,
        "不合并或拆分分段，不改动段号。",
        output + "只输出 JSON，不要任何说明。",
    ]
    if reference:
        lines += ["", "参考材料（报告）：", reference[:MAX_REFERENCE]]
    if translate:  # the format line above sits before a long report: say it again next to the segments
        lines += ["", '再说一遍输出格式：{"段号": {"text": "改好的原文", "zh": "中文翻译"}}，每一段都要有中文翻译。']
    return "\n".join(lines) + "\n\n" + SEGMENTS_MARK + json.dumps(batch, ensure_ascii=False)


def _batches(segments: list, size: int, chars: int) -> list:
    """Consecutive ranges of at most `size` segments and about `chars` characters."""
    batches, start, total = [], 0, 0
    for index, segment in enumerate(segments):
        if index > start and (index - start >= size or total + len(segment["text"]) > chars):
            batches.append(range(start, index))
            start, total = index, 0
        total += len(segment["text"])
    if start < len(segments):
        batches.append(range(start, len(segments)))
    return batches


def fix_segments(segments: list, reference: str, *, human: bool, ask, translate: bool = False) -> tuple:
    """Corrected copies of the segments (times untouched) and what happened to them."""
    fixed = [dict(segment) for segment in segments]
    batches = _batches(segments, *((TRANSLATE_BATCH, TRANSLATE_BATCH_CHARS) if translate else (BATCH, BATCH_CHARS)))

    def run(indices):
        prompt = build_prompt({str(i): segments[i]["text"] for i in indices}, reference, human=human,
                              translate=translate)
        readable = None
        for _attempt in range(2):  # one retry when the reply has no JSON, or no translation at all
            reply = parse_reply(ask(prompt))
            translated = any(isinstance(value, dict) and value.get("zh") for value in (reply or {}).values())
            if reply is not None and (translated or not translate):
                return indices, reply
            readable = reply or readable
        return indices, readable  # an untranslated reply still carries the corrections

    stats = {"changed": 0, "rejected": 0, "failed_batches": 0, "translated": 0, "batches": len(batches)}
    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        results = list(pool.map(run, batches))
    for indices, reply in results:
        if reply is None:
            stats["failed_batches"] += 1
            continue
        for i in indices:
            corrected = reply.get(str(i))
            if isinstance(corrected, dict):  # {"text", "zh"} when translating
                zh = corrected.get("zh")
                if translate and accept_translation(segments[i]["text"], zh):
                    fixed[i]["zh"] = zh.strip()
                    stats["translated"] += 1
                corrected = corrected.get("text")
            if not isinstance(corrected, str) or not accept(segments[i]["text"], corrected):
                stats["rejected"] += 1
                continue
            corrected = corrected.strip()
            if corrected != segments[i]["text"]:
                fixed[i]["text"] = corrected
                stats["changed"] += 1
    return fixed, stats


def _reference(data_dir, item_id: str, row: dict) -> str:
    from prometheus.report.markdown_export import report_to_markdown

    report = paths.report_file(data_dir, item_id)
    if not report.is_file() and row.get("library_path"):
        report = paths.library_folder(data_dir, row["library_path"]) / paths.LIBRARY_FILES["html"]
    if not report.is_file():
        return ""
    return report_to_markdown(report.read_text(encoding="utf-8"))[:MAX_REFERENCE]


def _ask_model(data_dir, llm: dict, *, node_exe: str, pi_cli: str):
    from prometheus.llm import one_shot

    def ask(prompt: str) -> str:
        return one_shot.run_one_shot(
            paths.pi_config_dir(data_dir), prompt=prompt, provider=llm["provider"], model=llm["model"],
            api_key=llm.get("api_key") or "", thinking=llm.get("thinking") or "low",
            node_exe=node_exe, pi_cli=pi_cli, agent_dir=paths.pi_config_dir(data_dir),
        )
    return ask


def _language(data_dir, item_id: str) -> str:
    """The transcript's language as the ASR (or the subtitle track) reported it; "" if unknown."""
    try:
        asr = json.loads((paths.work_dir(data_dir, item_id) / "asr.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return ""
    return str(asr.get("language") or "").lower()


def fix_for_item(data_dir, item_id: str, row: dict, llm: dict, *, node_exe: str, pi_cli: str,
                 ask=None) -> bool:
    """Correct segments.json from segments.raw.json; any failure leaves the subtitles as they are.
    `ask` replaces the model (the fake pipeline)."""
    shown = paths.segments_file(data_dir, item_id)
    raw = paths.raw_segments_file(data_dir, item_id)
    try:
        if not raw.is_file():
            shutil.copy2(shown, raw)
        segments = json.loads(raw.read_text(encoding="utf-8"))
        fixed, stats = fix_segments(
            segments, _reference(data_dir, item_id, row),
            human=row.get("transcript_source") == "youtube-subtitles",
            ask=ask or _ask_model(data_dir, llm, node_exe=node_exe, pi_cli=pi_cli),
            translate=_language(data_dir, item_id) not in {"", *CHINESE},
        )
    except Exception:  # noqa: BLE001 - PLAN 15.4.6: a correction failure never fails the item
        items_store.update_item(data_dir, item_id, subtitle_status="failed")
        return False
    if segments and stats["failed_batches"] == stats["batches"]:
        items_store.update_item(data_dir, item_id, subtitle_status="failed")
        return False
    shown.write_text(json.dumps(fixed, ensure_ascii=False), encoding="utf-8")
    items_store.update_item(data_dir, item_id, subtitle_status="ok")
    return True
