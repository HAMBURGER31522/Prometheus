"""faster-whisper conversion, device selection and call kwargs (PLAN 8.5)."""

import pytest
from prometheus.transcribe.local_whisper import (
    CudaUnavailable,
    assert_cuda_available,
    build_asr_run,
    build_transcribe_kwargs,
    pick_device,
)

RAW = {
    "segments": [
        {"start": 0.0, "end": 1.5, "text": "第一句"},
        {"start": 1.5, "end": 3.2, "text": "第二句"},
    ]
}


def test_asr_run_conversion_uses_vendor_schema():
    run = build_asr_run(RAW, model="large-v3-turbo", language="zh", elapsed_ms=250)
    assert run.backend == "local"
    assert run.provider == "local"
    assert run.engine == "faster-whisper"
    assert run.model == "large-v3-turbo"
    payload = run.to_dict()
    assert payload["segments"][0]["start_ms"] == 0
    assert payload["segments"][0]["end_ms"] == 1500
    assert payload["segments"][0]["text"] == "第一句"
    assert payload["segments"][1]["end_ms"] == 3200
    assert payload["segments"][0]["ordinal"] == 0


def test_device_selection():
    assert pick_device(True) == ("cuda", "float16")
    assert pick_device(False) == ("cpu", "int8")


def test_cuda_unavailable_error_code():
    with pytest.raises(CudaUnavailable) as error:
        assert_cuda_available(0)
    assert error.value.code == "CUDA_UNAVAILABLE"
    assert_cuda_available(1)


def test_transcribe_kwargs_chinese_gets_initial_prompt():
    kwargs = build_transcribe_kwargs("zh")
    assert kwargs["language"] == "zh"
    assert kwargs["initial_prompt"] == "以下是普通话的句子。"
    assert kwargs["vad_filter"] is True


def test_transcribe_kwargs_other_languages_have_no_prompt():
    for language in ("en", "ja", "de"):
        kwargs = build_transcribe_kwargs(language)
        assert kwargs["language"] == language
        assert "initial_prompt" not in kwargs
        assert kwargs["vad_filter"] is True
