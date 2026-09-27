"""Fill mind map leaves with grounded detail: simple at the root, rich at the leaves
(PLAN 15.4.9, D-40).

One call per theme writes every leaf's `detail` from evidence retrieved for that leaf
(retrieve.py). Each detail is checked deterministically; failing leaves are sent back once
with their problems, and a leaf that still fails keeps no detail rather than a vague one.
"""

import re
import unicodedata
from concurrent.futures import ThreadPoolExecutor

from prometheus.llm.replies import first_json_object
from prometheus.mindmap import retrieve

MIN_CHARS, MAX_CHARS = 80, 220
MAX_ECHO = 0.6        # trigram overlap with the summary: above this it only restates it
MIN_GROUNDING = 0.35  # share of the detail's trigrams found in its evidence
SPAN = 6              # a run of this many characters copied from the evidence counts as concrete
WORKERS = 3

GOOD_EXAMPLE = (
    "要点「分税制改革」：1994 年分税制把增值税的 75% 划归中央、25% 留给地方，中央财政收入占比从 22% 升到 55% 左右；"
    "地方事权没有相应减少而财力收缩，于是转向土地出让金补缺口。"
)
BAD_EXAMPLE = "要点「分税制改革」：这一部分介绍了分税制改革的背景和影响，说明了它在财政体系中的重要作用。（泛泛而谈，没有具体信息）"


def _norm(text: str) -> str:
    return "".join(c.lower() for c in text if unicodedata.category(c)[0] in "LN")


def _trigrams(text: str) -> set:
    chars = _norm(text)
    return {chars[i:i + 3] for i in range(len(chars) - 2)}


def grounding(detail: str, evidence: str) -> float:
    grams = _trigrams(detail)
    return len(grams & _trigrams(evidence)) / len(grams) if grams else 0.0


def is_concrete(detail: str, evidence: str) -> bool:
    if re.search(r"\d|「[^」]+」|《[^》]+》|“[^”]+”|[A-Za-z]{2,}", detail):
        return True
    chars, source = _norm(detail), _norm(evidence)
    return any(chars[i:i + SPAN] in source for i in range(len(chars) - SPAN + 1))


def check_detail(detail: str, summary: str, evidence: str) -> list:
    """What is wrong with a leaf's detail, in words the model can act on ([] = fine)."""
    problems = []
    length = len(re.sub(r"\s", "", detail))
    if length < MIN_CHARS:
        problems.append(f"只有 {length} 字，要写 {MIN_CHARS}–{MAX_CHARS} 字（2–4 句）")
    elif length > MAX_CHARS:
        problems.append(f"有 {length} 字，超过 {MAX_CHARS} 字")
    detail_grams, summary_grams = _trigrams(detail), _trigrams(summary)
    union = detail_grams | summary_grams
    if union and len(detail_grams & summary_grams) / len(union) >= MAX_ECHO:
        problems.append("几乎在复述摘要：要在摘要的基础上展开具体内容")
    score = grounding(detail, evidence)
    if score < MIN_GROUNDING:
        problems.append(f"依据率 {score:.2f}，低于 {MIN_GROUNDING}：写了资料里没有的内容，只能依据资料")
    if not is_concrete(detail, evidence):
        problems.append("没有具体信息：要写进资料里的数字、名称、定义、例子或条件")
    return problems


def _leaves(node: dict, node_id: str):
    if node["type"] == "leaf":
        yield node_id, node
    for index, child in enumerate(node["children"]):
        yield from _leaves(child, f"{node_id}.{index}")


def build_prompt(theme: dict, leaves: list, evidence: dict, previous: dict | None = None) -> str:
    lines = [
        "你在给一张知识树思维导图的末端要点写「详解」。导图越往外越具体：根和主题只点题，",
        "末端要点要让读者不看报告也能拿到具体的知识。",
        "",
        f"所属主题：{theme['label']}（{theme.get('summary', '')}）",
        "",
        "写作规范：",
        f"1. 每个要点写 2–4 句，{MIN_CHARS}–{MAX_CHARS} 字；",
        "2. 只依据该要点下面给出的资料，资料里没有的不写，不引申、不评价；",
        "3. 至少写进资料里的一项具体信息：数字、名称、定义、例子或条件；",
        "4. 不要重复要点的标题和摘要，要在它们的基础上展开。",
        "",
        f"好的示例：{GOOD_EXAMPLE}",
        f"差的示例：{BAD_EXAMPLE}",
        "",
        '只输出 JSON：{"要点编号": "详解", ...}，每个要点都要有。',
        "",
    ]
    for leaf_id, leaf in leaves:
        lines += [f'要点（编号 "{leaf_id}"）', f"标题：{leaf['label']}", f"摘要：{leaf.get('summary', '')}"]
        if previous and leaf_id in previous:
            detail, problems = previous[leaf_id]
            lines += [f"上次写的：{detail}", f"问题：{'；'.join(problems)}。请按资料重写。"]
        lines += ["资料：", evidence[leaf_id], ""]
    return "\n".join(lines)


def _accept(value) -> bool:
    return isinstance(value, dict) and all(isinstance(v, str) for v in value.values())


def _fill_theme(theme: dict, leaves: list, evidence: dict, ask) -> tuple:
    """{leaf id: detail or None} for one theme, and how many leaves were rewritten."""
    reply = first_json_object(ask(build_prompt(theme, leaves, evidence)), _accept) or {}
    results, failing = {}, {}
    for leaf_id, leaf in leaves:
        detail = (reply.get(leaf_id) or "").strip()
        problems = check_detail(detail, leaf.get("summary", ""), evidence[leaf_id]) if detail else ["没有写"]
        if problems:
            failing[leaf_id] = (detail, problems)
        else:
            results[leaf_id] = detail
    if failing:
        retry = [(leaf_id, leaf) for leaf_id, leaf in leaves if leaf_id in failing]
        again = first_json_object(ask(build_prompt(theme, retry, evidence, previous=failing)), _accept) or {}
        for leaf_id, leaf in retry:
            detail = (again.get(leaf_id) or "").strip()
            ok = detail and not check_detail(detail, leaf.get("summary", ""), evidence[leaf_id])
            results[leaf_id] = detail if ok else None
    return results, len(failing)


def richness(tree: dict, evidence: dict) -> dict:
    """The numbers docs/mindmap-eval.md reports: text per level, coverage, grounding, concreteness."""
    root = tree["root"]
    size = lambda node: len(node["label"]) + len(node.get("summary") or "") + len(node.get("detail") or "")
    by_level: dict = {"root": [size(root)]}

    def walk(node):
        for child in node["children"]:
            by_level.setdefault(child["type"], []).append(size(child))
            walk(child)

    walk(root)
    leaves = list(_leaves(root, "0"))
    detailed = [(leaf_id, leaf) for leaf_id, leaf in leaves if leaf.get("detail")]
    return {
        "chars_by_level": {level: round(sum(values) / len(values), 1) for level, values in by_level.items()},
        "leaves": len(leaves),
        "coverage": round(len(detailed) / len(leaves), 3) if leaves else 0.0,
        "grounding": round(sum(grounding(leaf["detail"], evidence.get(i, "")) for i, leaf in detailed) / len(detailed), 3)
        if detailed else 0.0,
        "concrete": round(sum(is_concrete(leaf["detail"], evidence.get(i, "")) for i, leaf in detailed) / len(detailed), 3)
        if detailed else 0.0,
    }


def enrich_tree(tree: dict, html: str, *, ask) -> tuple:
    """The tree with `detail` on every leaf that passed, and the richness numbers."""
    index = retrieve.Index(html)
    batches = []
    for position, theme in enumerate(tree["root"]["children"]):
        leaves = list(_leaves(theme, f"0.{position}"))
        if leaves:
            batches.append((theme, leaves))
    evidence = {leaf_id: index.evidence(leaf) for _theme, leaves in batches for leaf_id, leaf in leaves}

    def run(batch):
        theme, leaves = batch
        try:
            return _fill_theme(theme, leaves, evidence, ask)
        except Exception:  # noqa: BLE001 - one theme's failure must not lose the others
            return {}, 0

    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        outcomes = list(pool.map(run, batches))
    rewrites = 0
    for (_theme, leaves), (results, rewritten) in zip(batches, outcomes, strict=True):
        rewrites += rewritten
        for leaf_id, leaf in leaves:
            if results.get(leaf_id):
                leaf["detail"] = results[leaf_id]
    stats = richness(tree, evidence)
    stats["rewrites"] = rewrites
    return tree, stats
