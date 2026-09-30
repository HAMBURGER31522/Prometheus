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


KEPT = ["asr.json", "canonical-transcript.jsonl", "coverage.json", "input.json", "run.trace.jsonl", "mindmap.json",
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


# ---- the installed app (PLAN 15.4.16, installed run 2026-09-30): the backend owns a console host ----

def test_the_backends_own_console_host_is_never_killed(monkeypatch):
    """Started without a window by the Tauri shell, the backend has its own conhost.exe as a child; killing it
    with the task's processes left the next taskkill stuck and the whole backend unanswering."""
    from prometheus.tasks import processes

    killed = []
    monkeypatch.setattr(processes, "child_processes",
                        lambda parent=None: [(101, "conhost.exe"), (202, "python.exe"), (303, "Conhost.EXE")])
    monkeypatch.setattr(processes, "kill_tree", killed.append)
    assert processes.kill_children() == [202]
    assert killed == [202]


def test_taskkill_starts_without_a_console_of_its_own(monkeypatch):
    from prometheus.tasks import processes

    calls = []
    monkeypatch.setattr(processes.subprocess, "run", lambda command, **kwargs: calls.append(kwargs))
    monkeypatch.setattr(processes.sys, "platform", "win32")
    processes.kill_tree(4242)
    assert calls and calls[0].get("creationflags", 0) & 0x08000000  # CREATE_NO_WINDOW


def test_a_slow_cancel_does_not_stop_the_backend_answering(client, monkeypatch):
    from prometheus.tasks import processes

    started = threading.Event()

    def report(ctx):
        started.set()
        deadline = time.time() + 10
        while not ctx.cancel_requested and time.time() < deadline:
            time.sleep(0.02)
        raise RuntimeError("stopped")

    monkeypatch.setitem(client.app.state.queue.impls, "report", report)
    monkeypatch.setattr(processes, "kill_children", lambda: time.sleep(2) or [])
    item_id = _start(client)
    assert started.wait(timeout=15)
    cancelling = threading.Thread(target=lambda: client.post(f"/api/items/{item_id}/cancel"))
    cancelling.start()
    time.sleep(0.3)
    asked = time.time()
    assert client.get("/api/health").status_code == 200
    assert time.time() - asked < 1.0, "the backend stopped answering while a cancel was killing processes"
    cancelling.join(timeout=10)
