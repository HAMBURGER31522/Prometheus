"""Task lifecycle (PLAN 15.2-1): cancel kills children, trace, messages, cleanup."""

import json
import subprocess
import sys
import threading
import time

from conftest import BV_URL, wait_for_status
from prometheus import paths
from prometheus.tasks import runner
from video_report_agent.pi import PiError


def _start(client):
    return client.post("/api/items", json={"url": BV_URL, "figures": False}).json()["id"]


def test_cancel_kills_the_child_process_of_the_running_stage(client, monkeypatch):
    spawned = {}
    ready = threading.Event()

    def report_with_child(ctx):
        # Like Pi or the whisper worker: the stage blocks on a long child process.
        child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(120)"])
        spawned["child"] = child
        ready.set()
        child.wait()
        raise RuntimeError("child process ended")

    monkeypatch.setitem(client.app.state.queue.impls, "report", report_with_child)
    item_id = _start(client)
    try:
        assert ready.wait(timeout=15)
        assert client.post(f"/api/items/{item_id}/cancel").status_code == 200
        row = wait_for_status(client, item_id, "cancelled", timeout=8)
        assert row["status"] == "cancelled"
        deadline = time.time() + 5
        while spawned["child"].poll() is None and time.time() < deadline:
            time.sleep(0.05)
        assert spawned["child"].poll() is not None, "stage child still running after cancel"
    finally:
        if spawned.get("child") and spawned["child"].poll() is None:
            spawned["child"].kill()


def test_every_stage_is_traced(client):
    item_id = _start(client)
    wait_for_status(client, item_id, "done")
    trace = paths.work_dir(client.app.state.data_dir, item_id) / "run.trace.jsonl"
    assert trace.is_file(), "run.trace.jsonl was not written"
    events = [json.loads(line) for line in trace.read_text(encoding="utf-8").splitlines()]
    finished = [event["stage"] for event in events if event["event"] == "end"]
    assert finished == runner.STAGES
    assert all(event["elapsed_s"] >= 0 for event in events if event["event"] == "end")


def test_model_failure_is_explained_in_chinese(client, monkeypatch):
    def report_times_out(ctx):
        raise PiError("EXTERNAL_MODEL_FAILURE", "Request timed out.")

    monkeypatch.setitem(client.app.state.queue.impls, "report", report_times_out)
    item_id = _start(client)
    row = wait_for_status(client, item_id, "failed")
    # PLAN 15.4.10: a plain reason and what to do; the original text stays as the details.
    assert row["error_code"] == "MODEL_TIMEOUT"
    assert "模型" in (row.get("error_reason") or "")
    assert row["error_message"] == "PiError: Request timed out."


def test_unexpected_failure_is_labelled_as_unclassified(client, monkeypatch):
    def report_breaks(ctx):
        raise KeyError("oops")

    monkeypatch.setitem(client.app.state.queue.impls, "report", report_breaks)
    item_id = _start(client)
    row = wait_for_status(client, item_id, "failed")
    assert (row["stage"], row["error_code"]) == ("report", "UNCLASSIFIED")
    assert row.get("error_reason") == "未归类的错误。"
    assert row["error_message"] == "KeyError: 'oops'"


KEPT = ["asr.json", "canonical-transcript.jsonl", "input.json", "run.trace.jsonl", "mindmap.json",
        "segments.json", "segments.raw.json", "segments.fine.json", "source.info.json", "transcript.md"]
SCRATCH = ["media.m4a", "media.info.json", "video.mp4", "audio.wav", "pi.events.jsonl",
           "SKILL.md", "report.html", "frames/f_000080.jpg", "sessions/a.jsonl"]


def _scribble(ctx):
    work = paths.work_dir(ctx.data_dir, ctx.item_id)
    for name in [*KEPT, *SCRATCH]:
        target = work / name
        target.parent.mkdir(parents=True, exist_ok=True)
        if not target.exists():
            target.write_text("x", encoding="utf-8")


def test_success_keeps_only_what_regeneration_needs(client, monkeypatch):
    monkeypatch.setitem(client.app.state.queue.impls, "download", _scribble)
    item_id = _start(client)
    wait_for_status(client, item_id, "done")
    work = paths.work_dir(client.app.state.data_dir, item_id)
    left = sorted(p.relative_to(work).as_posix() for p in work.rglob("*") if p.is_file())
    assert left == sorted(KEPT)


def test_failure_keeps_scratch_files_for_diagnosis(client, monkeypatch):
    def report_breaks(ctx):
        raise KeyError("oops")

    monkeypatch.setitem(client.app.state.queue.impls, "download", _scribble)
    monkeypatch.setitem(client.app.state.queue.impls, "report", report_breaks)
    item_id = _start(client)
    wait_for_status(client, item_id, "failed")
    work = paths.work_dir(client.app.state.data_dir, item_id)
    assert (work / "media.m4a").is_file()
    assert (work / "frames" / "f_000080.jpg").is_file()
