"""Cutting a canonical transcript into ~5-minute blocks (PLAN 15.4.11: questions per block,
later the key-point ledger per block)."""

import json

from prometheus.report.chunks import chunk_units, load_units


def units(count, seconds_each=1.0, start=0.0):
    return [{"unit_id": f"unit-{i + 1:06d}", "start_ms": int((start + i * seconds_each) * 1000),
             "end_ms": int((start + (i + 1) * seconds_each) * 1000), "canonical_text": f"第{i + 1}句。"}
            for i in range(count)]


def test_blocks_are_about_five_minutes_on_unit_boundaries():
    blocks = chunk_units(units(1000), seconds=300)
    assert [len(block) for block in blocks] == [300, 300, 300, 100]
    assert blocks[1][0]["unit_id"] == "unit-000301"


def test_nothing_is_lost_or_reordered():
    rows = units(777, seconds_each=1.3)
    blocks = chunk_units(rows, seconds=300)
    assert [unit for block in blocks for unit in block] == rows
    assert len(blocks) > 1


def test_a_short_last_block_joins_the_one_before():
    blocks = chunk_units(units(610), seconds=300)
    assert [len(block) for block in blocks] == [300, 310]


def test_long_units_never_split_and_an_empty_transcript_has_no_blocks():
    blocks = chunk_units(units(10, seconds_each=100.0), seconds=300)
    assert [len(block) for block in blocks] == [3, 3, 3, 1]  # a 100 s tail is not "short" (< 1/3 block)
    assert chunk_units([], seconds=300) == []


def test_load_units_reads_the_jsonl_cache_file(tmp_path):
    path = tmp_path / "canonical-transcript.jsonl"
    rows = units(3)
    path.write_text("\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n", encoding="utf-8")
    assert load_units(path) == rows
