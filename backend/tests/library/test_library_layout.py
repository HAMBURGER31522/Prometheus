"""Readable folder names in the library (PLAN 15.4.1)."""

from prometheus.library import layout


def test_windows_reserved_characters_become_full_width():
    assert layout.safe_name('a<b>c:d"e/f\\g|h?i*j') == "a＜b＞c：d＂e／f＼g｜h？i＊j"


def test_edges_are_trimmed_and_trailing_dots_removed():
    assert layout.safe_name("  标题。.. ") == "标题。"


def test_long_names_are_cut_at_sixty_characters():
    name = layout.safe_name("长" * 80)
    assert len(name) == 61 and name.endswith("…")


def test_blank_category_falls_back_to_uncategorized():
    assert layout.category_folder_name("") == "未分类"
    assert layout.category_folder_name(None) == "未分类"


def test_item_folder_is_date_then_title():
    assert layout.item_folder_name("2026-09-26", "魔法卡巴拉导论：生命树") == "2026-09-26 魔法卡巴拉导论：生命树"


def test_clashing_names_get_a_number(tmp_path):
    first = layout.unique_child(tmp_path, "同名")
    first.mkdir()
    second = layout.unique_child(tmp_path, "同名")
    assert second != first, "a taken name must not be handed out again"
    second.mkdir()
    assert (first.name, second.name) == ("同名", "同名 (2)")
    assert layout.unique_child(tmp_path, "同名").name == "同名 (3)"


def test_the_data_dir_explains_itself(client):
    """PLAN 15.4.17: a user who opens the data folder can tell from 说明.txt where the reports, maps and
    subtitles are, what is for AI, what the app keeps, and how to back it up."""
    guide = client.app.state.data_dir / "说明.txt"
    assert guide.is_file()
    text = guide.read_text(encoding="utf-8")
    for words in ("精读.html", "思维导图.md", "字幕.srt", "llms.txt", "index.json", ".prometheus", "备份"):
        assert words in text


def test_the_guide_is_written_again_when_it_changed(client):
    from prometheus.library import guide

    target = client.app.state.data_dir / "说明.txt"
    target.write_text("旧的说明", encoding="utf-8")
    guide.write(client.app.state.data_dir)
    assert target.read_text(encoding="utf-8") == guide.TEXT
