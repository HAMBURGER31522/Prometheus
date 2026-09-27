"""Custom cloud ASR (PLAN 15.4.9): an OpenAI-compatible /audio/transcriptions endpoint, big
files cut at silences, and every failure falling back to local transcription. The HTTP
endpoint and ffmpeg are faked."""

from pathlib import Path

import pytest
from prometheus.transcribe import bcut, openai_compat

CONFIG = {"base_url": "https://asr.example/v1/", "api_key": "sk-test", "model": "whisper-1"}
MB = 1024 * 1024


def _mp3(tmp_path, size):
    path = tmp_path / "audio.mp3"
    path.write_bytes(b"\0" * size)
    return path


def _reply(*segments, language="english"):
    return {"language": language, "text": " ".join(s[2] for s in segments),
            "segments": [{"id": i, "start": s[0], "end": s[1], "text": s[2]} for i, s in enumerate(segments)]}


def test_a_small_file_is_one_verbose_json_request(tmp_path):
    calls = []

    def post(url, *, api_key, fields, file_path, timeout):
        calls.append((url, api_key, fields, Path(file_path).name))
        return _reply((0.0, 2.5, " Hello there."), (2.5, 4.0, "Bye."))

    segments, language = openai_compat.transcribe(_mp3(tmp_path, 1000), CONFIG, post=post)
    assert calls == [("https://asr.example/v1/audio/transcriptions", "sk-test",
                      {"model": "whisper-1", "response_format": "verbose_json",
                       "timestamp_granularities[]": "segment"}, "audio.mp3")]
    assert segments == [{"start": 0.0, "end": 2.5, "text": "Hello there."}, {"start": 2.5, "end": 4.0, "text": "Bye."}]
    assert language == "en"


def test_the_language_falls_back_to_the_text_when_the_reply_has_none(tmp_path):
    reply = _reply((0.0, 2.0, "你好，世界"), language="")
    _segments, language = openai_compat.transcribe(_mp3(tmp_path, 10), CONFIG, post=lambda url, **kw: reply)
    assert language == "zh"


@pytest.mark.parametrize("failure", [
    {"text": "Hello there."},           # no timestamps
    OSError("timed out"),               # network error / timeout
    ValueError("not JSON"),             # a reply that is not JSON
])
def test_every_failure_is_unavailable(tmp_path, failure):
    def post(url, **kw):
        if isinstance(failure, Exception):
            raise failure
        return failure

    with pytest.raises(openai_compat.CustomAsrUnavailable):
        openai_compat.transcribe(_mp3(tmp_path, 10), CONFIG, post=post)


def test_an_unconfigured_endpoint_is_unavailable(tmp_path):
    def post(url, **kw):
        raise AssertionError("no request without an address, key and model")

    with pytest.raises(openai_compat.CustomAsrUnavailable):
        openai_compat.transcribe(_mp3(tmp_path, 10), {"base_url": "", "api_key": "", "model": ""}, post=post)


def test_duration_and_silences_are_read_from_ffmpeg():
    stderr = (
        "Input #0, mp3, from 'audio.mp3':\n  Duration: 01:10:00.50, start: 0.025057, bitrate: 48 kb/s\n"
        "[silencedetect @ 000001] silence_start: 100.5\n"
        "[silencedetect @ 000001] silence_end: 101.75 | silence_duration: 1.25\n"
        "[silencedetect @ 000001] silence_start: 2000\n"
        "[silencedetect @ 000001] silence_end: 2001.5 | silence_duration: 1.5\n"
    )
    assert openai_compat.parse_probe(stderr) == (4200.5, [(100.5, 101.75), (2000.0, 2001.5)])


def _check_plan(chunks, duration, size, limit):
    rate = size / duration
    assert chunks[0][0] == 0 and chunks[-1][1] == duration
    assert all(a[1] == b[0] for a, b in zip(chunks, chunks[1:], strict=False)), "chunks must be contiguous"
    assert all((end - start) * rate <= limit for start, end in chunks)


def test_a_big_file_is_cut_inside_silences_below_the_limit():
    silences = [(float(t), t + 1.0) for t in range(100, 3000, 250)]
    chunks = openai_compat.plan_chunks(3000.0, 60 * MB, silences, max_bytes=20 * MB)
    assert len(chunks) >= 3
    _check_plan(chunks, 3000.0, 60 * MB, 20 * MB)
    assert all(any(s <= start <= e for s, e in silences) for start, _end in chunks[1:])


def test_without_silences_the_cut_falls_at_the_limit():
    chunks = openai_compat.plan_chunks(3000.0, 60 * MB, [], max_bytes=20 * MB)
    assert len(chunks) >= 3
    _check_plan(chunks, 3000.0, 60 * MB, 20 * MB)


def test_chunk_times_go_back_on_the_original_timeline(tmp_path):
    mp3 = _mp3(tmp_path, 3000)
    cuts = []

    def probe(path):
        return 300.0, [(95.0, 96.0), (195.0, 196.0)]

    def cut(path, start, end, target):
        cuts.append((start, end))
        target.write_bytes(b"\0" * 10)
        return target

    def post(url, **kw):
        return _reply((1.0, 2.0, "part"))

    segments, _language = openai_compat.transcribe(mp3, CONFIG, post=post, probe=probe, cut=cut, max_bytes=1000)
    assert len(cuts) >= 3
    assert [s["start"] for s in segments] == [start + 1.0 for start, _end in cuts]
    assert [s["end"] for s in segments] == [start + 2.0 for start, _end in cuts]


def test_the_run_says_custom_cloud():
    run = openai_compat.asr_run([{"start": 0.0, "end": 1.5, "text": "Hello."}], language="en",
                                model="whisper-1", elapsed_ms=900)
    assert (run.engine, run.backend, run.language) == ("openai-compatible", "cloud", "en")


def test_bcut_tells_english_from_chinese_by_the_text():
    # 必剪 reports no language; an English video must still get its Chinese lines (15.4.9).
    english = bcut.asr_run([{"start": 0.0, "end": 2.0, "text": "Imagine the money a country earns"}], elapsed_ms=1)
    chinese = bcut.asr_run([{"start": 0.0, "end": 2.0, "text": "想象一个国家挣到的钱"}], elapsed_ms=1)
    assert (english.language, chinese.language) == ("en", "zh")
