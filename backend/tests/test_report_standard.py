"""「标准」精读 (PLAN 15.4.15-10): VRA's own 精读 in one go, then an editor's-viewpoint pass per chapter with
confidence and checked links, and a jump TOC. Shaped like VRA's real output (BV1EJ4m1t7Zs, 2026-09-30):
chapter sections carry aria-labelledby, not an id, and a short video got no TOC."""

from pathlib import Path

from prometheus.report import standard, workspace

LINK = "https://en.wikipedia.org/wiki/Large_language_model"
BOX = ('<aside class="viewpoint"><p class="viewpoint-label">编者观点（非视频内容）</p><ul>'
       '<li>参数多不等于能力强。<span class="confidence">置信度：中</span>'
       f'依据：<a href="{LINK}">Large language model</a></li></ul></aside>')


def _chapter(number: int, title: str, body: str, time: str = "02:15–05:54") -> str:
    return (f'<section aria-labelledby="s{number}-title"><h2 id="s{number}-title"><span class="section-title">{title}'
            f'</span><span class="section-time">{time}</span></h2>{body}</section>')


def _report(*sections: str) -> str:
    return ('<!doctype html><html><head><title>t</title></head><body><main class="paper"><header><h1>大模型</h1>'
            '</header>' + "".join(sections) + "<details><summary>来源与处理说明</summary></details></main></body></html>")


REPORT = _report(_chapter(1, "训练", "<p>训练把文本之间的关系写进参数文件。</p>"),
                 _chapter(2, "推理与续写", "<p>推理时按上下文一个词一个词往下续写。</p>", "08:38–10:49"))


def _adding(box: str):
    """run_pi that adds `box` before the chapter's end; the prompts and files it was given."""
    seen = []

    def run_pi(space, prompt, expect):
        target = Path(space) / expect
        seen.append({"space": Path(space), "prompt": prompt, "expect": expect, "draft": target.read_text(encoding="utf-8")})
        text = target.read_text(encoding="utf-8")
        target.write_text(text[: text.rindex("</section>")] + box + "</section>", encoding="utf-8")
        return target

    return run_pi, seen


def _wikipedia(opened):
    def fetch(url):
        opened.append(url)
        return "Large language model - Wikipedia\nA large language model is a language model trained on a lot of text."
    return fetch


def test_the_vra_request_asks_for_its_own_jingdu_in_chapters_with_their_times():
    row = {"duration_s": 797.0}
    settings = {"llm": {"provider": "deepseek", "model": "m", "api_key": "", "thinking": "medium"}}
    prompt = workspace.build_runner_kwargs(row, settings, "node", "cli", figures=False,
                                           model_supports_images=False)["extra_prompt"]
    assert "精读表达" in prompt and "section-time" in prompt
    assert "不因为视频短" in prompt  # VRA would otherwise write a 13-minute video as a short report
    assert "depth.md" not in prompt


def test_the_chapters_are_vras_titled_sections():
    found = standard.chapters(REPORT)
    assert [chapter["title"] for chapter in found] == ["训练", "推理与续写"]
    assert all(chapter["fragment"].startswith("<section") and chapter["fragment"].endswith("</section>")
               for chapter in found)
    untitled = _report("<section><p>没有章节标题的一段</p></section>", _chapter(1, "训练", "<p>x</p>"))
    assert [chapter["title"] for chapter in standard.chapters(untitled)] == ["训练"]


def test_two_chapters_or_more_get_a_jump_toc_that_reaches_them():
    page = standard.add_nav(REPORT)
    assert page.count('class="report-nav"') == 1
    assert '<span class="report-nav-title">目录</span><a href="#s1">训练</a><a href="#s2">推理与续写</a>' in page
    assert '<section id="s1" aria-labelledby="s1-title">' in page and '<section id="s2" ' in page
    assert page.index('class="report-nav"') < page.index('<section id="s1"')
    assert standard.add_nav(page) == page  # already has one
    one = _report(_chapter(1, "训练", "<p>x</p>"))
    assert standard.add_nav(one) == one
    named = _report('<section id="intro"><h2><span class="section-title">开场</span></h2></section>',
                    _chapter(2, "训练", "<p>x</p>"))
    assert '<a href="#intro">开场</a><a href="#s2">训练</a>' in standard.add_nav(named)


def test_every_chapter_gets_its_own_editor_pass_with_confidence_and_checked_links(tmp_path):
    (tmp_path / "report.html").write_text(REPORT, encoding="utf-8")
    run_pi, seen = _adding(BOX)
    opened = []
    stats = standard.add_viewpoints(tmp_path, run_pi, verify_links=_wikipedia(opened), progress=lambda *a: None)
    page = (tmp_path / "report.html").read_text(encoding="utf-8")
    assert page.count('class="viewpoint"') == 2
    assert sorted(call["expect"] for call in seen) == ["ch-01.html", "ch-02.html"]
    assert "训练把文本之间的关系写进参数文件。" in next(c["draft"] for c in seen if c["expect"] == "ch-01.html")
    prompt = seen[0]["prompt"]
    assert "置信度" in prompt and "依据" in prompt and "编者观点（非视频内容）" in prompt
    assert "图文结合照旧" not in prompt  # the viewpoint rules only, not all of 完整's writing rules
    assert opened == [LINK, LINK] and f'href="{LINK}"' in page
    assert stats["kept"] == 2
    assert 'class="report-nav"' in page


def test_a_link_that_does_not_open_goes_and_the_confidence_drops(tmp_path):
    (tmp_path / "report.html").write_text(_report(_chapter(1, "训练", "<p>训练把文本之间的关系写进参数文件。</p>")),
                                          encoding="utf-8")
    run_pi, _seen = _adding(BOX)

    def closed(url):
        raise OSError("404")

    standard.add_viewpoints(tmp_path, run_pi, verify_links=closed, progress=lambda *a: None)
    page = (tmp_path / "report.html").read_text(encoding="utf-8")
    assert "参数多不等于能力强。" in page and LINK not in page and "置信度：低" in page


def test_a_pass_that_loses_the_chapters_text_leaves_the_chapter_as_it_was(tmp_path):
    (tmp_path / "report.html").write_text(REPORT, encoding="utf-8")

    def run_pi(space, prompt, expect):
        target = Path(space) / expect
        text = target.read_text(encoding="utf-8")
        if expect == "ch-01.html":  # rewrote the chapter down to its box
            text = text[: text.index("</h2>") + 5] + BOX + "</section>"
        else:
            text = text[: text.rindex("</section>")] + BOX + "</section>"
        target.write_text(text, encoding="utf-8")
        return target

    standard.add_viewpoints(tmp_path, run_pi, verify_links=None, progress=lambda *a: None)
    page = (tmp_path / "report.html").read_text(encoding="utf-8")
    assert "训练把文本之间的关系写进参数文件。" in page
    assert page.count('class="viewpoint"') == 1  # chapter 2's pass stays
