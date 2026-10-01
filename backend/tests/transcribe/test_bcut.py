"""必剪 cloud ASR client (PLAN 15.4.4, D-32). The HTTP session is faked; nothing leaves the machine."""

import json

import pytest
import requests
from prometheus.transcribe import bcut

UTTERANCES = [
    {"start_time": 0, "end_time": 1500, "transcript": "这是你打开B站"},
    {"start_time": 1500, "end_time": 3200, "transcript": "每天可以看到的推荐视频"},
]


class FakeResponse:
    def __init__(self, payload=None, status_code=200, headers=None):
        self.payload = payload if payload is not None else {"code": 0, "data": {}}
        self.status_code = status_code
        self.headers = headers or {}

    def json(self):
        return self.payload


class FakeSession:
    """Answers the five 必剪 calls from a script; records what was sent."""

    def __init__(self, states=(4,), create_status=200, fail=None, code=0):
        self.headers = {}
        self.calls = []
        self.states = list(states)
        self.create_status = create_status
        self.fail = fail
        self.code = code

    def post(self, url, json=None, timeout=None):
        self.calls.append(("POST", url, json))
        if self.fail:
            raise self.fail
        if url.endswith("/resource/create"):
            return FakeResponse({"code": self.code, "data": {
                "in_boss_key": "boss", "resource_id": "res", "upload_id": "up", "per_size": 10,
                "upload_urls": ["https://upload/1", "https://upload/2", "https://upload/3"],
            }}, status_code=self.create_status)
        if url.endswith("/resource/create/complete"):
            return FakeResponse({"code": 0, "data": {"download_url": "https://boss/audio.mp3"}})
        if url.endswith("/task"):
            return FakeResponse({"code": 0, "data": {"task_id": "t1"}})
        raise AssertionError(url)

    def put(self, url, data=None, timeout=None):
        self.calls.append(("PUT", url, data))
        return FakeResponse(headers={"Etag": "e" + url[-1]})

    def get(self, url, params=None, timeout=None):
        self.calls.append(("GET", url, params))
        state = self.states.pop(0) if len(self.states) > 1 else self.states[0]
        result = json.dumps({"utterances": UTTERANCES}, ensure_ascii=False) if state == 4 else ""
        return FakeResponse({"code": 0, "data": {"state": state, "result": result}})


def _mp3(tmp_path):
    path = tmp_path / "audio.mp3"
    path.write_bytes(bytes(range(25)))
    return path


def _run(tmp_path, session, **kwargs):
    return bcut.transcribe(_mp3(tmp_path), session=session, sleep=lambda s: None, **kwargs)


def test_upload_in_parts_commit_poll_and_return_segments(tmp_path):
    session = FakeSession(states=(1, 1, 4))
    segments = _run(tmp_path, session)
    assert segments == [
        {"start": 0.0, "end": 1.5, "text": "这是你打开B站"},
        {"start": 1.5, "end": 3.2, "text": "每天可以看到的推荐视频"},
    ]
    create = session.calls[0]
    assert create[1] == bcut.API + "/resource/create"
    assert create[2]["size"] == 25 and create[2]["ResourceFileType"] == "mp3"
    puts = [call[2] for call in session.calls if call[0] == "PUT"]
    assert puts == [bytes(range(10)), bytes(range(10, 20)), bytes(range(20, 25))]
    commit = next(call for call in session.calls if call[1].endswith("/resource/create/complete"))
    assert commit[2]["Etags"] == "e1,e2,e3"
    task = next(call for call in session.calls if call[1].endswith("/task"))
    assert task[2]["resource"] == "https://boss/audio.mp3"
    polls = [call for call in session.calls if call[0] == "GET"]
    assert len(polls) == 3 and polls[0][2]["task_id"] == "t1"
    assert session.headers["User-Agent"].startswith("Bilibili/1.0.0")


def test_http_412_means_unavailable(tmp_path):
    with pytest.raises(bcut.BcutUnavailable):
        _run(tmp_path, FakeSession(create_status=412))


def test_an_error_code_in_the_payload_means_unavailable(tmp_path):
    with pytest.raises(bcut.BcutUnavailable):
        _run(tmp_path, FakeSession(code=-400))


def test_a_failed_task_means_unavailable(tmp_path):
    with pytest.raises(bcut.BcutUnavailable):
        _run(tmp_path, FakeSession(states=(1, 3)))


def test_a_task_that_never_finishes_times_out(tmp_path):
    ticks = iter(range(0, 10_000, 100))
    with pytest.raises(bcut.BcutUnavailable):
        _run(tmp_path, FakeSession(states=(1,)), timeout_s=900, clock=lambda: next(ticks))


def test_network_errors_mean_unavailable(tmp_path):
    with pytest.raises(bcut.BcutUnavailable):
        _run(tmp_path, FakeSession(fail=requests.ConnectionError("reset")))


def test_asr_run_says_bcut_in_the_cloud():
    run = bcut.asr_run([{"start": 0.0, "end": 1.5, "text": "你好"}], elapsed_ms=900)
    assert run.engine == "bcut" and run.backend == "cloud"
    assert len(run.segments) == 1


def test_mp3_for_bcut_is_16k_mono_48kbps(tmp_path):
    from prometheus.transcribe.audio import build_mp3_cmd

    command = build_mp3_cmd(tmp_path / "in.m4a", tmp_path / "out.mp3")
    assert command[command.index("-ac") + 1] == "1"
    assert command[command.index("-ar") + 1] == "16000"
    assert command[command.index("-b:a") + 1] == "48k"
