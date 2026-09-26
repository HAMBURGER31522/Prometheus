"""Data directory layout (PLAN 15.4.1): readable library + hidden .prometheus."""

import sys

from prometheus import paths


def _is_hidden(path) -> bool:
    import ctypes

    attributes = ctypes.windll.kernel32.GetFileAttributesW(str(path))
    return attributes != -1 and bool(attributes & 0x2)  # FILE_ATTRIBUTE_HIDDEN


def test_init_creates_the_hidden_internal_folder(tmp_path):
    library = tmp_path / "知识库"
    paths.init_data_dir(library)
    internal = library / ".prometheus"
    for relative in ("config/pi", "runtime/cuda", "models", "logs", "cache"):
        assert (internal / relative).is_dir(), relative
    assert paths.db_path(library) == internal / "prometheus.db"
    assert paths.settings_file(library) == internal / "config" / "settings.json"
    assert paths.pi_config_dir(library) == internal / "config" / "pi"
    assert paths.logs_dir(library) == internal / "logs"
    assert not (library / "items").exists()
    if sys.platform == "win32":
        assert _is_hidden(internal)


def test_item_cache_layout(tmp_path):
    library = tmp_path / "知识库"
    item_id = "a" * 32
    cache = library / ".prometheus" / "cache" / item_id
    assert paths.cache_dir(library, item_id) == cache
    assert paths.work_dir(library, item_id) == cache
    assert paths.segments_file(library, item_id) == cache / "segments.json"
    assert paths.report_file(library, item_id) == cache / "out" / "report.html"
    assert paths.mindmap_file(library, item_id) == cache / "out" / "mindmap.md"
    assert paths.srt_file(library, item_id) == cache / "out" / "subtitle.srt"


def test_library_file_names():
    assert paths.LIBRARY_FILES == {
        "html": "精读.html", "md": "精读.md", "mindmap": "思维导图.md",
        "srt": "字幕.srt", "txt": "字幕.txt", "url": "来源.url",
    }


def test_item_id_is_32_hex():
    assert len(paths.new_item_id()) == 32
    int(paths.new_item_id(), 16)
