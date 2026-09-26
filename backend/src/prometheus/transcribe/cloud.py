"""Cloud ASR via vendor paraformer (PLAN 8.5)."""


class CloudAsrError(RuntimeError):
    code = "EXTERNAL_API_FAILURE"


def transcribe_cloud(data_dir, item_id: str, wav_path):
    raise NotImplementedError
