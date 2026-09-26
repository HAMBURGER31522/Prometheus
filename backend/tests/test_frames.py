"""Scene-frame extraction and candidate filtering (PLAN 8.7, M5)."""

from prometheus.report.frames import filter_frames, parse_showinfo

SHOWINFO_SAMPLE = """[Parsed_showinfo_1 @ 0000025c1d3fbcc0] n:   0 pts:60616 pts_time:6.0616 pos:     1012 \
crop:0:0:1920:1072
[Parsed_showinfo_1 @ 0000025c1d3fbcc0] n:   1 pts:245246 pts_time:24.5246 pos:     2211
"""


def test_parse_showinfo_extracts_pts_times():
    assert parse_showinfo(SHOWINFO_SAMPLE) == [6.0616, 24.5246]


def test_filter_enforces_minimum_interval():
    frames = filter_frames([0.0, 10.0, 25.0, 50.0], duration_s=120.0)
    times = [f["t"] for f in frames]
    assert times == [0.0, 25.0, 50.0]


def test_filter_caps_per_hour_and_total():
    every_minute = [float(m * 60) for m in range(0, 4 * 60)]  # 4h of 1-min candidates
    frames = filter_frames(every_minute, duration_s=4 * 3600)
    assert len(frames) == 80  # 总上限
    first_hour = [f for f in frames if f["t"] < 3600]
    assert len(first_hour) == 20  # 每小时上限


def test_filter_fills_evenly_when_sparse():
    frames = filter_frames([100.0, 200.0], duration_s=3600.0)
    times = [f["t"] for f in frames]
    assert len(times) == 5
    assert times[:2] == [100.0, 200.0]
    # 5 分钟一帧的均匀补帧
    assert 300.0 in times


def test_filter_naming_and_labels():
    frames = filter_frames([0.0, 25.0, 3661.0], duration_s=3700.0)
    by_file = {f["file"]: f for f in frames}
    assert "f_000000.jpg" in by_file
    assert "f_000025.jpg" in by_file
    assert "f_003661.jpg" in by_file
    assert by_file["f_000025.jpg"]["label"] == "00:25"
    assert by_file["f_003661.jpg"]["label"] == "01:01:01"
    assert all(isinstance(f["t"], float) for f in frames)
