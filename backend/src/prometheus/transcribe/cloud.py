"""Cloud ASR via vendor paraformer (PLAN 8.5)."""

import json
import os
from pathlib import Path

from prometheus import paths
from prometheus.settings import store
from video_report_agent.asr import transcribe_audio as vendor_transcribe_audio
from video_report_agent.media_config import resolve_media_config


class CloudAsrError(RuntimeError):
    code = "EXTERNAL_API_FAILURE"


def transcribe_cloud(data_dir, item_id: str, wav_path) -> Path:
    settings = store.load(data_dir)
    api_key = (settings["asr"].get("dashscope_api_key") or "").strip()
    if not api_key:
        raise CloudAsrError("云端转写需要 DashScope API Key，请先在设置里填写。")
    os.environ["DASHSCOPE_API_KEY"] = api_key
    config = resolve_media_config(
        asr_backend="paraformer",
        asr_model=settings["asr"].get("cloud_model") or "paraformer-v2",
    )
    work = paths.work_dir(data_dir, item_id)
    run = vendor_transcribe_audio(
        Path(wav_path),
        model=config["asr_model"],
        language=config["asr_language"],
        backend=config["asr_backend"],
        base_url=config["asr_base_url"],
        parameters=config["asr_parameters"],
        task_path=work / "asr-task.json",
    )
    asr_path = work / "asr.json"
    asr_path.write_text(
        json.dumps(run.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8",
    )
    return asr_path
