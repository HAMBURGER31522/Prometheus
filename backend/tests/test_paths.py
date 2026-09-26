"""Data directory layout (PLAN section 7)."""

from prometheus import paths


def test_init_creates_layout(tmp_path):
    data_dir = tmp_path / "data"
    paths.init_data_dir(data_dir)
    assert paths.db_path(data_dir).parent == data_dir
    assert (data_dir / "config" / "settings.json").parent.is_dir()
    assert (data_dir / "config" / "pi").is_dir()
    assert (data_dir / "runtime" / "cuda").is_dir()
    assert (data_dir / "models").is_dir()
    assert (data_dir / "logs").is_dir()
    assert (data_dir / "items").is_dir()


def test_item_dir_layout(tmp_path):
    data_dir = tmp_path / "data"
    item_id = "a" * 32
    item_dir = paths.item_dir(data_dir, item_id)
    assert item_dir == data_dir / "items" / item_id
    assert paths.report_file(data_dir, item_id) == item_dir / "report" / "report.html"
    assert paths.mindmap_file(data_dir, item_id) == item_dir / "mindmap" / "mindmap.md"
    assert paths.segments_file(data_dir, item_id) == item_dir / "subtitle" / "segments.json"
    assert paths.srt_file(data_dir, item_id) == item_dir / "subtitle" / "subtitle.srt"
    assert paths.work_dir(data_dir, item_id) == item_dir / "work"


def test_item_id_is_32_hex():
    assert len(paths.new_item_id()) == 32
    int(paths.new_item_id(), 16)
