"""Local-ASR component install: CUDA libs and FunASR models into the data dir (PLAN 8.5, 15.4.4)."""

import os
import shutil
import subprocess
import sys

from prometheus import paths

CUDA_PACKAGES = (
    "nvidia-cublas-cu12==12.9.2.10",
    "nvidia-cudnn-cu12==9.26.0.51",
)


class ComponentInstallError(RuntimeError):
    code = "ENVIRONMENT_FAILURE"


def build_pip_cmd(data_dir, *, proxy: str = "") -> list:
    target = str(paths.cuda_dir(data_dir))
    command = [
        sys.executable, "-m", "pip", "install", "--no-deps",
        "--target", target, *CUDA_PACKAGES,
    ]
    if proxy.strip():
        command += ["--proxy", proxy.strip()]
    return command


def _has_pip() -> bool:
    probe = subprocess.run(
        [sys.executable, "-m", "pip", "--version"], capture_output=True, check=False,
    )
    return probe.returncode == 0


def install_components(data_dir, *, proxy: str = "") -> None:
    target = paths.cuda_dir(data_dir)
    target.mkdir(parents=True, exist_ok=True)
    env = None
    if _has_pip():
        # Packaged builds: the bundled interpreter ships pip (PLAN 8.5).
        command = build_pip_cmd(data_dir, proxy=proxy)
    else:
        # uv-managed dev venvs have no pip; uv takes over, proxy via env vars.
        uv = shutil.which("uv")
        if uv is None:
            raise ComponentInstallError(
                "当前 Python 没有 pip，也找不到 uv，无法安装本地转写组件。"
            )
        command = [
            uv, "pip", "install", "--no-deps", "--target", str(target), *CUDA_PACKAGES,
        ]
        env = dict(os.environ)
        if proxy.strip():
            env["HTTPS_PROXY"] = proxy.strip()
            env["HTTP_PROXY"] = proxy.strip()
    result = subprocess.run(
        command, capture_output=True, check=False, env=env,
    )
    if result.returncode != 0:
        raise ComponentInstallError(
            "CUDA 运行库安装失败：" + result.stderr.decode("utf-8", "replace")[-500:]
        )
    install_funasr_models(data_dir, proxy=proxy)


# FunASR ONNX exports (PLAN 15.4.4, D-39): only the files funasr-onnx reads.
MODELSCOPE_FILE = "https://www.modelscope.cn/api/v1/models/{model}/repo?Revision=master&FilePath={name}"
FUNASR_MODELS = (
    ("iic/speech_fsmn_vad_zh-cn-16k-common-onnx", ("model_quant.onnx", "config.yaml", "am.mvn")),
    ("iic/speech_paraformer-large-vad-punc_asr_nat-zh-cn-16k-common-vocab8404-onnx",
     ("model_quant.onnx", "config.yaml", "am.mvn", "tokens.json")),
    ("iic/punc_ct-transformer_cn-en-common-vocab471067-large-onnx",
     ("model_quant.onnx", "config.yaml", "tokens.json", "jieba_usr_dict")),
)


def funasr_model_dir(data_dir, model: str):
    return paths.funasr_dir(data_dir) / model.split("/", 1)[1]


def funasr_models_installed(data_dir) -> bool:
    return all((funasr_model_dir(data_dir, model) / name).is_file()
               for model, files in FUNASR_MODELS for name in files)


def _fetch(url: str, target, *, proxy: str = "") -> None:
    import urllib.request

    handlers = [urllib.request.ProxyHandler({"http": proxy, "https": proxy})] if proxy.strip() else []
    with urllib.request.build_opener(*handlers).open(url, timeout=60) as response, target.open("wb") as out:
        shutil.copyfileobj(response, out, length=1024 * 1024)


def install_funasr_models(data_dir, *, proxy: str = "", fetch=_fetch) -> None:
    """Download each missing file to <name>.part, then rename: a cut download never looks complete."""
    for model, files in FUNASR_MODELS:
        folder = funasr_model_dir(data_dir, model)
        folder.mkdir(parents=True, exist_ok=True)
        for name in files:
            target = folder / name
            if target.is_file():
                continue
            partial = folder / (name + ".part")
            try:
                fetch(MODELSCOPE_FILE.format(model=model, name=name), partial, proxy=proxy)
            except OSError as exc:
                raise ComponentInstallError(f"FunASR 模型下载失败（{model} / {name}）：{exc}") from exc
            partial.replace(target)
