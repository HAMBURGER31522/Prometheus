"""Why a task failed, in plain words (PLAN 15.4.10 「导入失败写明原因」).

When a stage fails the queue keeps that stage, stores classify()'s reason code as error_code and
the original error text as error_message (the console's 「详情」). The rules are fixed and match
the texts yt-dlp and Pi really produce (samples and their sources: tests/test_failure_reasons.py).
The same words mean different things in different stages (a timeout while downloading is the
network, while writing the report it is the model), so each rule names the stages it applies to.
"""

import re

from prometheus import paths

SITE_STAGES = ("resolve", "download")  # yt-dlp talks to the video site
MODEL_STAGES = ("keypoints", "plan", "report", "classify", "subtitle_fix", "mindmap")  # Pi calls the model

# code -> (reason, what to do). Rows that failed before 15.4.10 carry older codes and get neither.
REASONS = {
    # 视频本身
    "VIDEO_NOT_FOUND": ("视频不存在或已被删除。", "在浏览器里打开链接，确认视频还在。"),
    "VIDEO_LOGIN_REQUIRED": ("这个视频要登录、开通大会员或付费才能看。", "换一个公开、免费就能看的视频。"),
    "VIDEO_REGION_LOCKED": ("视频有地区限制，在当前网络所在的地区看不了。",
                            "在「设置 · 网络」里填一个能看这个视频的地区的代理，再点「重试」。"),
    "VIDEO_LIVE": ("这是直播，或者还没开播。", "等直播结束、有回放以后，导入回放的链接。"),
    "LINK_UNSUPPORTED": ("不支持这个链接。", "粘贴 B 站或 YouTube 的单个视频链接。"),
    # 网络
    "BILIBILI_RISK_CONTROL": ("B 站暂时拒绝了请求（HTTP 412 风控）。",
                              "等 10 分钟左右再点「重试」，短时间内不要连续导入很多视频。"),
    "SITE_UNREACHABLE": ("连不上视频网站（超时、域名解析失败或代理地址不对）。",
                         "检查网络；用了代理的话，到「设置 · 网络」核对代理地址，再点「重试」。"),
    "YOUTUBE_SIGN_IN": ("YouTube 要求登录验证，或者 cookies 已过期。",
                        "在浏览器里登录 YouTube，重新导出 cookies.txt，到「设置 · 网络」里选择它，再点「重试」。"),
    # 模型
    "MODEL_KEY_INVALID": ("模型的 Key 无效，或没有使用这个模型的权限。",
                          "到「设置 · 模型」核对 Key 和模型名，再点「重试」。"),
    "MODEL_NO_BALANCE": ("模型账户余额不足，或额度已用完。", "到模型平台充值或换一个有额度的 Key，再点「重试」。"),
    "MODEL_RATE_LIMITED": ("请求太频繁，或超过了并发上限。", "等几分钟再点「重试」。"),
    "MODEL_BUSY": ("模型服务繁忙或出错。", "过一会儿再点「重试」，或在「设置 · 模型」换一个模型。"),
    "MODEL_TIMEOUT": ("模型没有回应（超时或连不上）。", "检查网络和接口地址；中转站不稳定时，过一会儿再点「重试」。"),
    "MODEL_CONTEXT_TOO_LONG": ("内容太长，超过了模型能读的上下文长度。",
                               "在「设置 · 模型」换一个上下文更长的模型，再点「重试」。"),
    "MODEL_NOT_FOUND": ("模型名不存在。", "到「设置 · 模型」点「获取模型列表」，选一个列表里有的模型。"),
    "MODEL_THINKING_UNSUPPORTED": ("这个模型不支持所选的思考强度。",
                                   "在「设置 · 模型」把思考强度调低一档，保存后点「重试」。"),
    # 本机
    "ASR_COMPONENTS_MISSING": ("本地转写组件还没装。", "到「设置 · 转写」点「安装本地转写组件」，装好后点「重试」。"),
    "DISK_FULL": ("磁盘空间不足。", "清理数据目录所在的磁盘，腾出空间后点「重试」。"),
    "ASR_WORKER_CRASHED": ("本地转写进程出错了。",
                           "打开日志文件 {log} 查看原因；也可以在「设置 · 转写」改用「云端（必剪）」后点「重试」。"),
    "UNCLASSIFIED": ("未归类的错误。", "先点「重试」；还是失败的话，把下面的详情复制下来排查。"),
}


def _status(codes: str) -> str:
    """An HTTP status where Pi's provider messages put it: at the start, or right after 「：」."""
    return rf"(?:^|：)\s*(?:{codes})(?=[\s:]|$)"


# (code, stages it applies to or None for any, error codes that decide alone, text patterns (any
# of them), text that rules the patterns out). The first rule that matches wins.
_RULES = [
    # 本机
    ("DISK_FULL", None, (), (
        "No space left on device", r"\[Errno 28\]", r"\[WinError 112\]", "磁盘空间不足", "not enough space on the disk",
    ), None),
    ("ASR_COMPONENTS_MISSING", None, ("CUDA_UNAVAILABLE",), ("尚未安装本地转写组件",), None),
    ("ASR_WORKER_CRASHED", None, ("ASR_FAILURE",), ("本地转写进程异常结束",), None),
    # 网络与视频本身 (yt-dlp)
    ("YOUTUBE_SIGN_IN", SITE_STAGES, ("YOUTUBE_COOKIES_REQUIRED",), (
        "confirm you.re not a bot", "cookies are no longer valid", "failed to load cookies",
    ), None),
    ("BILIBILI_RISK_CONTROL", SITE_STAGES, (), (
        "HTTP Error 412", r"blocked by server \(412\)", r"rejected by server \(352\)",
        r"\[BiliBili\].*exceeded the rate limit",
    ), None),
    ("VIDEO_LIVE", SITE_STAGES, (), (
        "live event will begin", "Premieres in", "has not (?:yet )?started", "Streamer is not live",
    ), None),
    ("VIDEO_REGION_LOCKED", SITE_STAGES, (), (
        "geo restriction", "not made this video available in your country",
    ), None),
    ("VIDEO_LOGIN_REQUIRED", SITE_STAGES, (), (
        "only available for registered users", "premium members only", "purchase the course", "supporter-only",
        "Private video", "confirm your age", "members-only", "requires payment", "Login details are needed",
    ), None),
    # YouTube says 'Video unavailable' also when it rate-limits the session ('try again later').
    ("VIDEO_NOT_FOUND", SITE_STAGES, (), (
        "Video unavailable", "may be deleted", "has been removed", "no longer available", "does not exist",
        "HTTP Error 404",
    ), "try again later"),
    ("LINK_UNSUPPORTED", SITE_STAGES, ("URL_UNSUPPORTED", "INPUT_REJECTED"), ("Unsupported URL",), None),
    ("SITE_UNREACHABLE", SITE_STAGES, (), (
        "getaddrinfo failed", "Failed to resolve", "timed out", "Unable to connect to proxy",
        "Failed to establish a new connection", "Connection (?:refused|reset|aborted)", "RemoteDisconnected",
        "CERTIFICATE_VERIFY_FAILED",
    ), None),
    # 模型 (Pi): overflow wording after pi-ai's utils/overflow.js, which also rules out rate limits
    ("MODEL_CONTEXT_TOO_LONG", MODEL_STAGES, (), (
        "prompt is too long", "request_too_large", "exceeds the context window", "maximum context length",
        "context[_ ]length[_ ]exceeded", "reduce the length of the messages", "context window exceeds limit",
        "exceeded model token limit", "range of input length should be", "too many tokens",
    ), "rate limit|too many requests"),
    # before the 429 rule: OpenAI's insufficient_quota comes as a 429
    ("MODEL_NO_BALANCE", MODEL_STAGES, (), (
        _status("402"), "insufficient_quota", "Insufficient Balance", "credit balance is too low",
        "exceeded your current quota", "billing", "欠费", "余额不足",
    ), None),
    # a thinking level passed through for a model the catalogue lacks (PLAN 15.4.12)
    ("MODEL_THINKING_UNSUPPORTED", MODEL_STAGES, (), (
        r"(?:unsupported|not supported|does not support|invalid)[^\n]{0,80}reasoning[_. ]?effort",
        r"reasoning[_. ]?effort[^\n]{0,80}(?:unsupported|not supported|does not support|invalid)",
    ), None),
    # Pi's fatal 'not found' only: its 'not found for provider ... Using custom model id' is a warning
    ("MODEL_NOT_FOUND", MODEL_STAGES, (), (
        "model_not_found", "does not exist", "Model Not Exist", r"not_found_error\W+message\W+model",
        r'Model "[^"]*" not found\. Use --list-models', "模型不存在",
    ), None),
    ("MODEL_KEY_INVALID", MODEL_STAGES, (), (
        _status("401|403"), "authentication_error", "permission_error", "invalid_api_key", "Incorrect API key",
        "invalid x-api-key", "Authentication Fails", "No API key",
    ), None),
    ("MODEL_RATE_LIMITED", MODEL_STAGES, (), (
        _status("429"), "rate.?limit", "too many requests", "并发", "请求过多", "频繁",
    ), None),
    ("MODEL_BUSY", MODEL_STAGES, (), (
        _status(r"5\d\d"), "overloaded", "service.?unavailable", "server.?error", "provider.?returned.?error", "繁忙",
    ), None),
    ("MODEL_TIMEOUT", MODEL_STAGES, (), (
        "timed? ?out", "timeout", "Connection error", "fetch failed", "socket hang up", "ECONNRESET", "ETIMEDOUT",
        "ENOTFOUND", "EAI_AGAIN", "getaddrinfo",
    ), None),
]
_COMPILED = [
    (code, stages, codes, re.compile("|".join(patterns), re.IGNORECASE | re.MULTILINE),
     re.compile(unless, re.IGNORECASE) if unless else None)
    for code, stages, codes, patterns, unless in _RULES
]
_ANSI = re.compile(r"\x1b\[[0-9;]*m")  # yt-dlp colours 'ERROR:' when it writes to a console


def classify(stage, text: str, code=None) -> str:
    """The reason code for an error raised in ``stage``; ``code`` is the exception's own code."""
    for name, stages, codes, pattern, unless in _COMPILED:
        if stages is not None and stage not in stages:
            continue
        if code in codes or (pattern.search(text) and not (unless and unless.search(text))):
            return name
    return "UNCLASSIFIED"


def details(exc: BaseException) -> str:
    """The original error in full, as a traceback's last line: '<type>: <message>'."""
    return _ANSI.sub("", f"{type(exc).__name__}: {exc}").strip()


def describe(stage, exc: BaseException) -> tuple[str, str]:
    """(reason code, details) for a failure in ``stage``."""
    text = details(exc)
    return classify(stage, text, getattr(exc, "code", None) or getattr(exc, "category", None)), text


def explain(data_dir, code):
    """(reason, what to do) for the console, or None for a code from before 15.4.10."""
    if code not in REASONS:
        return None
    reason, action = REASONS[code]
    return reason, action.format(log=paths.logs_dir(data_dir) / "asr-worker.log")


def view(data_dir, row: dict) -> dict:
    """The fields the console adds to a row: error_reason and error_action (None if unknown)."""
    reason, action = explain(data_dir, row.get("error_code")) or (None, None)
    return {"error_reason": reason, "error_action": action}
