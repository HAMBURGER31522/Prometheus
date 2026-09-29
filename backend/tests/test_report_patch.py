"""Patching a finished 完整 report by the newer rules (PLAN 15.4.11a-5): the published 精读 is split
back into its chapters and each is checked and patched with the kept ledger — no new key points, no
new plan, no chapter written again — then an editor's-viewpoint pass, verified links, and the
chapters go back into the page."""

import base64
import json
import re

from prometheus.report import full, patch
from test_report_full import Model, make_units

JPEG = base64.b64encode(b"\xff\xd8\xff\xe0fake-jpeg").decode("ascii")
BOX = ('<aside class="viewpoint"><p class="viewpoint-label">编者观点（非视频内容）</p><ul>'
       '<li>编者的判断。<span class="confidence">置信度：中</span>依据：'
       '<a href="https://en.wikipedia.org/wiki/Coffee_roasting">Coffee roasting (Wikipedia)</a></li></ul></aside>')


def paragraph(number: int) -> str:
    return (f'<p data-points="K{number:03d}">咖啡豆的烘焙和萃取之{number - 1}：这一点讲清楚了是什么、为什么、怎么用，'
            "并举了例子说明。</p>")


def published(skip=("K003",)) -> str:
    first = "".join(paragraph(n) for n in range(1, 13) if f"K{n:03d}" not in skip)
    second = "".join(paragraph(n) for n in range(13, 25))
    return (
        '<!doctype html><html><head><title>手冲咖啡</title><style>.paper{}</style></head><body><main class="paper">'
        '<header class="intro"><h1>手冲咖啡</h1><p class="lead">烘焙与萃取。</p></header>'
        '<nav class="report-nav"><a href="#s1">烘焙</a><a href="#s2">萃取</a></nav>\n'
        '<section id="s1"><h2><span class="num">1</span><span class="section-title">烘焙</span>'
        f'<span class="section-time">00:00–06:00</span></h2>{first}</section>\n'
        '<section id="s2"><h2><span class="num">2</span><span class="section-title">萃取</span>'
        f'<span class="section-time">06:00–12:00</span></h2>{second}'
        f'<figure class="report-figure"><img src="data:image/jpeg;base64,{JPEG}" alt="图"><figcaption>图注</figcaption></figure>'
        "</section>\n</main></body></html>"
    )


class PatchPi:
    """Edits the chapter file in place: fills the points a targeted run names, adds a viewpoint box."""

    def __init__(self):
        self.calls = []

    def __call__(self, workspace, prompt, expect):
        assert (workspace / "SKILL.md").is_file()
        self.calls.append((expect, prompt))
        path = workspace / expect
        draft = path.read_text(encoding="utf-8")
        if "只补" in prompt:
            for point_id in re.findall(r"^- (K\d{3})：", prompt, flags=re.MULTILINE):
                draft = draft.replace("</section>", paragraph(int(point_id[1:])) + "</section>")
        elif "编者观点" in prompt:
            draft = draft.replace("</section>", BOX + "</section>")
        path.write_bytes(draft.encode("utf-8"))
        return path


def open_page(url):
    return "Coffee roasting - Wikipedia"


def test_the_published_report_splits_into_its_chapters_with_titles_and_times():
    chapters = patch.split_report(published())
    assert [(c["number"], c["title"], c["ranges"]) for c in chapters] == [
        (1, "烘焙", [["00:00", "06:00"]]), (2, "萃取", [["06:00", "12:00"]])]
    assert chapters[0]["fragment"].startswith('<section id="s1">') and chapters[1]["fragment"].endswith("</section>")


def test_embedded_pictures_go_back_to_files_so_prompts_stay_small(tmp_path):
    html, count = patch.extract_images(published(), tmp_path / "frames")
    assert count == 1 and "base64" not in html and 'src="frames/embedded-01.jpg"' in html
    assert (tmp_path / "frames" / "embedded-01.jpg").read_bytes() == b"\xff\xd8\xff\xe0fake-jpeg"


def test_a_finished_report_is_patched_by_the_new_rules_without_new_key_points_or_plan(tmp_path):
    units, model = make_units(), Model()
    ledger = full.run_keypoints(tmp_path, units, model)
    asked = len(model.prompts)
    pi = PatchPi()
    coverage = patch.patch_report(tmp_path, published(), ledger, units, pi, skipped=set(), verify_links=open_page,
                                  progress=lambda *args: None, workers=1)
    assert len(model.prompts) == asked  # the ledger is the kept one
    first = [prompt for name, prompt in pi.calls if name == "ch-01.html"]
    second = [prompt for name, prompt in pi.calls if name == "ch-02.html"]
    assert len(first) == 2 and "只补" in first[0] and "第2句原话" in first[0] and "编者观点" in first[1]
    assert len(second) == 1 and "编者观点" in second[0]
    assert all("=== 附件：SKILL.md" not in prompt for _, prompt in pi.calls)
    page = (tmp_path / "report.html").read_text(encoding="utf-8")
    assert 'data-points="K003"' in page and page.count('class="viewpoint"') == 2
    assert 'src="frames/embedded-01.jpg"' in page and "<h1>手冲咖啡</h1>" in page
    assert coverage["written"] == 24 and coverage["uncovered"] == []
    assert coverage["viewpoints"] == {"points": 2, "links": 2, "kept": 2, "dropped": 0, "unsourced": 0}
    assert json.loads((tmp_path / "coverage.json").read_text(encoding="utf-8"))["written"] == 24


def test_the_patched_report_goes_through_finalize_with_its_pictures_back_inline(tmp_path):
    from prometheus.report.finalize import finalize_report

    units = make_units()
    ledger = full.run_keypoints(tmp_path, units, Model())
    patch.patch_report(tmp_path, published(), ledger, units, PatchPi(), skipped=set(), verify_links=open_page,
                       progress=lambda *args: None, workers=1)
    final = tmp_path / "out" / "精读.html"
    finalize_report(tmp_path / "report.html", final, tmp_path)
    html = final.read_text(encoding="utf-8")
    assert "frames/embedded" not in html and f"data:image/jpeg;base64,{JPEG}" in html


def test_a_report_without_point_marks_is_refused(tmp_path):
    import pytest

    units = make_units()
    ledger = full.run_keypoints(tmp_path, units, Model())
    plain = re.sub(r' data-points="[^"]*"', "", published())
    with pytest.raises(ValueError, match="data-points"):
        patch.patch_report(tmp_path, plain, ledger, units, PatchPi(), skipped=set(), verify_links=None,
                           progress=lambda *args: None, workers=1)
