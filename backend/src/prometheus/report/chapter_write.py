"""One chapter's writing run (PLAN 15.4.11 step 4; after LongWriter: one bounded piece per call).

Every chapter is written by its own Pi run. The writer gets the rules in full (SKILL.md, the mode
file, the template, depth.md), attached to the prompt so the run does not spend turns reading them:
the relay has no prompt cache and every turn resends the whole context (D-44). It also gets the
whole plan, so it knows where it stands, and its own points and transcript, nothing of the other
chapters' sources. Long documents come first and the task last.
"""

from prometheus.report.chapter_checks import feedback_prompt
from prometheus.report.plan import chapter_ranges


def _clock(seconds: float, hours: bool) -> str:
    seconds = int(seconds)
    if hours:
        return f"{seconds // 3600:02d}:{seconds % 3600 // 60:02d}:{seconds % 60:02d}"
    return f"{seconds // 60:02d}:{seconds % 60:02d}"


def _unit_line(unit: dict) -> str:
    seconds = int(unit["start_ms"] // 1000)
    clock = f"{seconds // 3600:02d}:{seconds % 3600 // 60:02d}:{seconds % 60:02d}"
    return f"[{unit['unit_id']} {clock}] {unit.get('canonical_text', '')}"


def chapter_units(chapter: dict, owned: list, points: dict, units: list) -> list:
    """The units inside the chapter's time ranges, plus those of points moved into it, in order."""
    spans = [(start * 1000, end * 1000) for start, end in chapter_ranges(chapter) or []]
    index = {unit["unit_id"]: position for position, unit in enumerate(units)}
    picked = {position for position, unit in enumerate(units)
              if any(unit["start_ms"] < end and unit["end_ms"] > start for start, end in spans)}
    for point_id in owned:
        first, last = (index.get(unit_id) for unit_id in points[point_id]["units"])
        if first is not None and last is not None:
            picked.update(range(first, last + 1))
    return [units[position] for position in sorted(picked)]


def _time_label(chapter: dict, hours: bool) -> str:
    return "；".join(f"{_clock(start, hours)}–{_clock(end, hours)}" for start, end in chapter_ranges(chapter) or [])


def chapter_prompt(plan: dict, number: int, owned: list, points: dict, units: list, *,
                   figures: bool, attached: str, frame_notes=None) -> str:
    chapters = plan["chapters"]
    chapter = chapters[number - 1]
    last_end = max([end for c in chapters for _start, end in chapter_ranges(c) or []]
                   + [units[-1]["end_ms"] / 1000 if units else 0])
    hours = last_end >= 3600
    time_label = _time_label(chapter, hours)
    filename = f"ch-{number:02d}.html"
    order = {c["id"]: position for position, c in enumerate(chapters)}
    glossary = [g for g in plan.get("glossary") or [] if isinstance(g, dict) and g.get("chapter") in order]
    first_here = [g["term"] for g in glossary if order[g["chapter"]] == number - 1]
    before = [g["term"] for g in glossary if order[g["chapter"]] < number - 1]
    outline = "\n".join(
        f"{position}. {c['title']}（{_time_label(c, hours)}）" + ("　← 本章" if position == number else "")
        for position, c in enumerate(chapters, 1))
    listed = "\n".join(
        f"- {point_id}（{points[point_id]['type']}，{_clock(points[point_id]['start_ms'] / 1000, hours)}）"
        f"{points[point_id]['text']}　原话：「{points[point_id]['anchor']}」" for point_id in owned)
    transcript = "\n".join(_unit_line(unit) for unit in chapter_units(chapter, owned, points, units))
    # No count limit (user 2026-09-28: more pictures); the candidate pool itself is at most 20 per hour.
    figure_rule = ("6. 开了配图：frames/ 里是本章时间范围内的候选帧（清单 frames/frames.json），"
                   "按 figures.md 的写法使用，但不受它第 3 条的张数限制。画面里有正文写不出来的信息就配上，宁多勿少："
                   "幻灯片、图表、板书和公式、代码、软件界面、实物演示、地图。不配：口播人像、转场、片头片尾、广告；"
                   "同一个画面只配一次。图注写画面里的关键信息，和正文互补，不重复正文。\n" if figures else "")
    offered = [frame for frame in frame_notes or [] if frame.get("useful")]
    if figures and offered:
        figure_rule += (
            "   本章的候选帧已经有人看过，画面内容如下（文件在 frames/ 里，要核对细节时再打开）：\n"
            + "".join(f"   - {frame['file']}（{frame['label']}，{frame['kind']}）{frame['what']}\n" for frame in offered)
            + "   每一张都在讲到它的段落后面配上；确实不用的（和已用的图是同一个画面，或者正文已经完整写出了它的信息），"
            "在片段里写一行 <!-- 不用 文件名：理由 -->，例如 <!-- 不用 f_000332.jpg：与上一张是同一页幻灯片 -->。\n"
        )
    return (
        f"{attached}\n\n"
        f"## 本章转写（每行开头是单元编号和时间）\n{transcript}\n\n"
        "## 任务\n"
        "本任务按 video-report skill（SKILL.md、modes/standard.md、assets/report-template.html）和 depth.md "
        "写一份完整精读里的**一章**。这几个文件的全文已附在本消息开头，不用再读取。"
        "其余各章由别的写作者分头写，程序会按规划把各章依次拼进模板，并生成题头、导语和目录，所以你只写这一章。\n\n"
        f"全篇规划：《{plan.get('title', '')}》，Profile：{plan.get('profile', '')}\n"
        f"导语：{plan.get('lead', '')}\n{outline}\n\n"
        f"本章是第 {number}/{len(chapters)} 章「{chapter['title']}」：\n"
        f"- 时间：{time_label}\n"
        "- 读者：聪明但零基础的成年人。每个要点按 depth.md 的四步写（是什么 → 类比 → 展开 → 所以呢），"
        "讲到读者能自己复述为止；术语、人名、缩写第一次出现就在那句话里解释\n"
        f"- 本章首次解释的术语：{'、'.join(first_here) or '无'}\n"
        f"- 前面章节已经解释过的术语（再用到时一句话带过）：{'、'.join(before) or '无'}\n\n"
        f"本章要点（每一条都要写到、讲清楚，按 depth.md 的讲解清单展开）：\n{listed or '（无）'}\n\n"
        "写法：\n"
        f"1. 写入 {filename}：只有一个 <section> 片段，不写 <html>、<head>、<body>、题头和目录。章节标题照模板："
        f'<h2><span class="num">{number}</span><span class="section-title">{chapter["title"]}</span>'
        f'<span class="section-time">{time_label}</span></h2>。\n'
        '2. 讲到某条要点的段落、列表项、表格行、卡片或图注，加 data-points="K003 K004" 标出讲了哪几条；'
        "本章的每条要点都至少标一次，标的地方要真的讲了它。\n"
        "3. 核心判断照 SKILL.md 用 data-source-units 绑定上面转写里的单元编号。\n"
        "4. 组件、图示、SVG 和表格照 SKILL.md 与 modes/standard.md 使用，样式只用模板里已有的类；"
        "确需新样式时，在片段开头放一个 <style>，只写本章用到的类。\n"
        '5. 补充说明照 depth.md 写在 <aside class="supplement"> 里；有争议的地方可以按 depth.md 写编者观点'
        '（<aside class="viewpoint">，标置信度和依据链接），编者的推测不写成讲者的话。'
        "原文列举的每一项、每一层原因、提到的具体名称都要写出来。\n"
        + figure_rule
    )


def revision_prompt(base: str, problems: list, filename: str, draft: str = "") -> str:
    """A fresh run fixing the draft in `filename`: the chapter's task again, the draft, then the list."""
    return base + "\n## 修改上一稿\n" + feedback_prompt(problems, filename, draft)


def targeted_prompt(depth: str, draft: str, failing: list, filename: str) -> str:
    """One small run for the points still failing after two rounds (PLAN 15.4.11a-3): the rules of
    depth.md, the draft and each point's own source; the draft is edited in place, not rewritten."""
    listed = "\n".join(f"- {item['id']}：{item['text']}\n  问题：{item['problem']}\n  原文：{item['source']}"
                        for item in failing)
    return (
        f"{depth}\n\n## 这一章现在的稿子（{filename}）\n{draft}\n\n"
        "## 只补这几条要点\n"
        f"下面这几条要点检查了两轮仍然没写到、没写清或漏了其中几项。对照它们的原文，用 edit 在 {filename} 里"
        "只改讲到它们的段落（或在合适的位置补一段），每条都用 data-points 标出；其余内容保持不变。\n"
        f"{listed}\n"
    )


def viewpoint_prompt(depth: str, draft: str, filename: str) -> str:
    """The editor's-viewpoint pass over a finished chapter (PLAN 15.4.11a-4/5)."""
    return (
        f"{depth}\n\n## 这一章现在的稿子（{filename}）\n{draft}\n\n"
        "## 加编者观点\n"
        "按上面「编者观点（非视频内容）」一节，在本章视频的说法有争议、值得商榷，或者你有自己判断的地方，"
        "加编者观点框（分点写，每点标置信度和依据链接）；正文里把编者的推测写成讲者意图或说法的句子，"
        f"改成编者口吻或挪进编者观点框。用 edit 在 {filename} 上改，其余内容保持不变；"
        "本章没有值得写的地方就不加。\n"
    )
