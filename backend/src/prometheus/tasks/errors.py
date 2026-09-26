"""Turn a stage failure into (error_code, Chinese guidance) for the UI (PLAN 15.2-1)."""

GUIDANCE = {
    "EXTERNAL_MODEL_FAILURE": "模型调用失败：请在「设置 · 模型」里点「测试模型」，检查 Key、模型名和网络；中转站超时可以稍后重试。",
    "EXTERNAL_API_FAILURE": "外部服务调用失败：请检查网络后重试。",
    "ENVIRONMENT_FAILURE": "运行环境异常：请重新安装 Prometheus，或检查本地转写组件是否完整。",
    "INPUT_REJECTED": "输入无法处理：请确认链接是可以公开访问的单个视频。",
    "URL_UNSUPPORTED": "不支持的链接：请粘贴 B 站或 YouTube 的单个视频链接。",
    "YOUTUBE_COOKIES_REQUIRED": "YouTube 要求登录验证：请在「设置 · 网络」里选择导出的 cookies.txt。",
    "DOWNLOAD_FAILURE": "视频下载失败：请确认视频可以公开访问，稍后重试。",
    "CUDA_UNAVAILABLE": "本地转写组件还没安装：请在「设置 · 转写」里启用本地转写。",
    "ASR_FAILURE": "转写失败：请查看数据目录 logs 下的 asr-worker.log。",
}


def describe(exc: BaseException) -> tuple[str, str]:
    code = getattr(exc, "code", None) or getattr(exc, "category", None)
    detail = str(exc).strip()
    if code in GUIDANCE:
        return code, f"{GUIDANCE[code]}（{detail}）" if detail else GUIDANCE[code]
    if code:
        return code, f"处理失败（{code}）：{detail}"
    return "IMPLEMENTATION_FAILURE", f"内部错误：{type(exc).__name__}: {detail}"
