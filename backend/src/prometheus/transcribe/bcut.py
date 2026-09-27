"""必剪 cloud ASR (PLAN 15.4.4, D-32).

Bilibili's free, keyless (and unofficial) speech recognition: ask for upload
slots, PUT the mp3 in the part size the server chooses, commit, create a task,
poll until it is done. Written from the request flow; no code is taken from
VideoCaptioner (GPL). Anything that goes wrong raises ``BcutUnavailable`` so the
caller can fall back to local transcription.
"""

import dataclasses
import json
import time
from pathlib import Path

import requests

API = "https://member.bilibili.com/x/bcut/rubick-interface"
# The desktop client's UA; the old bcut-asr defaults get HTTP 412 (tested 2026-09-26).
HEADERS = {"User-Agent": "Bilibili/1.0.0 (https://www.bilibili.com)"}
MODEL_ID = "8"
RESULT_MODEL_ID = 7
STATE_DONE = 4
STATE_FAILED = 3


class BcutUnavailable(RuntimeError):
    code = "EXTERNAL_API_FAILURE"


def _data(response) -> dict:
    if response.status_code != 200:
        raise BcutUnavailable(f"必剪返回 HTTP {response.status_code}")
    payload = response.json()
    if payload.get("code") != 0:
        raise BcutUnavailable(f"必剪返回错误 {payload.get('code')}: {payload.get('message', '')}")
    return payload.get("data") or {}


def _upload(session, data: bytes) -> str:
    grant = _data(session.post(f"{API}/resource/create", json={
        "type": 2, "name": "audio.mp3", "size": len(data), "ResourceFileType": "mp3", "model_id": MODEL_ID,
    }, timeout=30))
    size = grant["per_size"]
    etags = []
    for index, url in enumerate(grant["upload_urls"]):
        put = session.put(url, data=data[index * size:(index + 1) * size], timeout=120)
        if put.status_code != 200:
            raise BcutUnavailable(f"必剪上传分片失败：HTTP {put.status_code}")
        if put.headers.get("Etag"):
            etags.append(put.headers["Etag"])
    done = _data(session.post(f"{API}/resource/create/complete", json={
        "InBossKey": grant["in_boss_key"], "ResourceId": grant["resource_id"],
        "Etags": ",".join(etags), "UploadId": grant["upload_id"], "model_id": MODEL_ID,
    }, timeout=30))
    return done["download_url"]


def transcribe(mp3, *, session=None, sleep=time.sleep, clock=time.monotonic,
               timeout_s: float = 900.0, poll_s: float = 2.0) -> list:
    """Segments ``[{"start": s, "end": s, "text": str}]`` in seconds."""
    session = session or requests.Session()
    session.headers.update(HEADERS)
    try:
        resource = _upload(session, Path(mp3).read_bytes())
        task = _data(session.post(f"{API}/task", json={"resource": resource, "model_id": MODEL_ID},
                                  timeout=30))["task_id"]
        deadline = clock() + timeout_s
        while True:
            state = _data(session.get(f"{API}/task/result",
                                      params={"model_id": RESULT_MODEL_ID, "task_id": task}, timeout=30))
            if state.get("state") == STATE_DONE:
                break
            if state.get("state") == STATE_FAILED:
                raise BcutUnavailable("必剪识别任务失败")
            if clock() > deadline:
                raise BcutUnavailable("必剪识别超时")
            sleep(poll_s)
    except (requests.RequestException, KeyError, ValueError) as exc:
        raise BcutUnavailable(f"必剪请求失败：{exc}") from exc
    utterances = json.loads(state["result"]).get("utterances") or []
    return [{"start": item["start_time"] / 1000, "end": item["end_time"] / 1000, "text": item["transcript"]}
            for item in utterances]


def asr_run(segments: list, *, elapsed_ms: int):
    from prometheus.transcribe.local_whisper import build_asr_run

    run = build_asr_run({"segments": segments}, model=f"bcut model {MODEL_ID}", language="zh",
                        elapsed_ms=elapsed_ms, engine="bcut")
    return dataclasses.replace(run, backend="cloud", provider="bilibili")
