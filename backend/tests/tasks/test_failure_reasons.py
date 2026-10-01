"""「导入失败写明原因」(PLAN 15.4.10, E13 ①): the failing stage is kept and the error text is
sorted into one plain reason by fixed rules. Every sample below is in the real format of the
library that produces it; the comment above each group says where that format comes from.
yt-dlp samples were built offline by instantiating yt-dlp's own exception classes (2026.08.19)."""

import pytest
from conftest import BV_URL, wait_for_status
from prometheus import paths
from prometheus.ingest.download import IngestError
from prometheus.library import items as items_store
from prometheus.tasks import errors
from video_report_agent.pi import PiError

YT_HINT = (
    "Use --cookies-from-browser or --cookies for the authentication. See  "
    "https://github.com/yt-dlp/yt-dlp/wiki/FAQ#how-do-i-pass-cookies-to-yt-dlp  for how to manually "
    "pass cookies. Also see  https://github.com/yt-dlp/yt-dlp/wiki/Extractors#exporting-youtube-cookies  "
    "for tips on effectively exporting YouTube cookies"
)
BILI_HINT = (
    "Use --cookies-from-browser or --cookies for the authentication. See  "
    "https://github.com/yt-dlp/yt-dlp/wiki/FAQ#how-do-i-pass-cookies-to-yt-dlp  for how to manually pass cookies"
)
# yt-dlp extractor/common.py _request_webpage: 'Unable to download webpage: <HTTPError>' with the
# cause's repr; YoutubeDL.report_error prefixes 'ERROR: ' (networking/exceptions.py HTTPError).
BILI_412 = (
    "ERROR: [BiliBili] BV1xx411c7mD: Unable to download webpage: HTTP Error 412: Precondition Failed "
    "(caused by <HTTPError 412: Precondition Failed>)"
)

SAMPLES = [
    # ---- 视频本身 (resolve / download; yt-dlp extractor/bilibili.py, extractor/youtube/_video.py) ----
    # bilibili.py: initial_state trueCode -404
    ("download", None, (
        "ERROR: [BiliBili] BV1xx411c7mD: This video may be deleted or geo-restricted. "
        "You might want to try a VPN or a proxy server (with --proxy)"
    ), "VIDEO_NOT_FOUND"),
    # youtube/_video.py: raise_no_formats(<YouTube's playability reason>, expected=True)
    ("resolve", None, "ERROR: [youtube] dQw4w9WgXcQ: Video unavailable. This video has been removed by the uploader",
     "VIDEO_NOT_FOUND"),
    # bilibili.py trueCode -403: raise_login_required() (extractor/common.py default message + hint)
    ("download", None, f"ERROR: [BiliBili] BV1xx411c7mD: This video is only available for registered users. {BILI_HINT}",
     "VIDEO_LOGIN_REQUIRED"),
    # bilibili.py BiliBiliBangumiIE: raise_login_required('This video is for premium members only')
    ("download", None, f"ERROR: [BiliBiliBangumi] ep123456: This video is for premium members only. {BILI_HINT}",
     "VIDEO_LOGIN_REQUIRED"),
    # youtube/_video.py: 'sign in' reasons get the login hint appended
    ("download", None, (
        "ERROR: [youtube] dQw4w9WgXcQ: Sign in to confirm your age. This video may be "
        f"inappropriate for some users. {YT_HINT}"
    ), "VIDEO_LOGIN_REQUIRED"),
    ("download", None, (
        "ERROR: [youtube] dQw4w9WgXcQ: Private video. Sign in if you've been granted access "
        f"to this video. {YT_HINT}"
    ), "VIDEO_LOGIN_REQUIRED"),
    ("download", None, (
        "ERROR: [youtube] dQw4w9WgXcQ: Join this channel to get access to members-only content "
        "like this video, and other exclusive perks."
    ), "VIDEO_LOGIN_REQUIRED"),
    # extractor/common.py raise_geo_restricted() -> GeoRestrictedError; YoutubeDL adds the VPN line
    ("download", None, (
        "ERROR: [BiliBiliBangumi] ep123456: This video is not available from your location due "
        "to geo restriction\nYou might want to use a VPN or a proxy server (with --proxy) to workaround."
    ), "VIDEO_REGION_LOCKED"),
    ("resolve", None, (
        "ERROR: [youtube] dQw4w9WgXcQ: The uploader has not made this video available in your "
        "country\nYou might want to use a VPN or a proxy server (with --proxy) to workaround."
    ), "VIDEO_REGION_LOCKED"),
    # youtube/_video.py: an upcoming live stream's reason; bilibili.py BiliLiveIE 'Streamer is not live'
    ("resolve", None, "ERROR: [youtube] dQw4w9WgXcQ: This live event will begin in 3 hours.", "VIDEO_LIVE"),
    ("resolve", None, "ERROR: [bilibili:live] 21452505: Streamer is not live", "VIDEO_LIVE"),
    # utils/_utils.py UnsupportedError: 'Unsupported URL: <url>' (no extractor prefix)
    ("resolve", None, "ERROR: Unsupported URL: https://www.bilibili.com/festival/2026bnj", "LINK_UNSUPPORTED"),
    # ---- 网络 ----
    ("download", "DOWNLOAD_FAILURE", BILI_412, "BILIBILI_RISK_CONTROL"),
    # bilibili.py BilibiliSpaceBaseIE: 412 rewritten as 'Request is blocked by server (412)'
    ("resolve", None, (
        "ERROR: [bilibili:space:video] 123456: Request is blocked by server (412), please wait and try later."
    ), "BILIBILI_RISK_CONTROL"),
    # networking/_requests.py: requests ConnectionError -> TransportError(cause=e); urllib3 exceptions.py
    ("resolve", None, (
        "ERROR: [BiliBili] BV1xx411c7mD: Unable to download webpage: HTTPSConnectionPool("
        "host='www.bilibili.com', port=443): Max retries exceeded with url: /video/BV1xx411c7mD/ (Caused by "
        "NameResolutionError(\"HTTPSConnection(host='www.bilibili.com', port=443): Failed to resolve "
        "'www.bilibili.com' ([Errno 11001] getaddrinfo failed)\")) (caused by TransportError(...))"
    ), "SITE_UNREACHABLE"),
    ("resolve", None, (
        "ERROR: [youtube] dQw4w9WgXcQ: Unable to download webpage: HTTPSConnectionPool("
        "host='www.youtube.com', port=443): Max retries exceeded with url: /watch?v=dQw4w9WgXcQ (Caused by "
        "ConnectTimeoutError(<HTTPSConnection(host='www.youtube.com', port=443) at 0x1cb8b25f650>, 'Connection to "
        "www.youtube.com timed out. (connect timeout=20.0)'))"
    ), "SITE_UNREACHABLE"),
    # networking/_requests.py: requests ProxyError -> ProxyError(cause=e) (yt-dlp adds its bug-report line)
    ("download", None, (
        "ERROR: [youtube] dQw4w9WgXcQ: Unable to download webpage: HTTPSConnectionPool("
        "host='www.youtube.com', port=443): Max retries exceeded with url: /watch?v=dQw4w9WgXcQ (Caused by "
        "ProxyError('Unable to connect to proxy', NewConnectionError(\"HTTPSConnection(host='www.youtube.com', "
        "port=443): Failed to establish a new connection: [WinError 10061] 由于目标计算机积极拒绝，无法连接。\"))); "
        "please report this issue on  https://github.com/yt-dlp/yt-dlp/issues?q= , filling out the appropriate "
        "issue template. Confirm you are on the latest version using  yt-dlp -U"
    ), "SITE_UNREACHABLE"),
    # youtube/_video.py: the bot check reason + login hint; ingest/download.py CookiesRequired;
    # cookies.py CookieLoadError('failed to load cookies')
    ("download", "YOUTUBE_COOKIES_REQUIRED",
     f"ERROR: [youtube] dQw4w9WgXcQ: Sign in to confirm you’re not a bot. {YT_HINT}", "YOUTUBE_SIGN_IN"),
    ("resolve", "YOUTUBE_COOKIES_REQUIRED", "YouTube 需要 cookies.txt：请先在设置里导出 YouTube cookies 文件。",
     "YOUTUBE_SIGN_IN"),
    ("resolve", None, "CookieLoadError: failed to load cookies", "YOUTUBE_SIGN_IN"),
    # ---- 模型 (report: vendor pi.py PiError(errorMessage); classify: llm/one_shot.py OneShotError(stderr)) ----
    # Pi's errorMessage for an OpenAI-compatible provider: pi-ai dist/utils/error-body.js
    # formatProviderError -> '<status>: <JSON of the body's error>' (openai core/error.js APIError)
    ("report", "EXTERNAL_MODEL_FAILURE", (
        '401: {"message":"Incorrect API key provided: sk-****. You can find your API key at '
        'https://platform.openai.com/account/api-keys.","type":"invalid_request_error","param":null,'
        '"code":"invalid_api_key"}'
    ), "MODEL_KEY_INVALID"),
    # Anthropic: @anthropic-ai/sdk core/error.js makeMessage -> '<status> <JSON of the whole body>'
    ("report", "EXTERNAL_MODEL_FAILURE", (
        '403 {"type":"error","error":{"type":"permission_error","message":"Your API key does not have '
        'permission to use the specified resource."},"request_id":"req_011"}'
    ), "MODEL_KEY_INVALID"),
    # print mode (pi-coding-agent dist/modes/print-mode.js) writes errorMessage to stderr
    ("classify", "EXTERNAL_API_FAILURE", (
        '一次性文本调用失败（exit 1）：401: {"message":"Authentication Fails, Your api key: ****abcd is invalid",'
        '"type":"authentication_error","param":null,"code":"invalid_request_error"}'
    ), "MODEL_KEY_INVALID"),
    # pi-coding-agent dist/core/agent-session.js
    ("report", "EXTERNAL_MODEL_FAILURE", "No API key for deepseek/deepseek-chat", "MODEL_KEY_INVALID"),
    # DeepSeek 402 through the OpenAI-compatible adapter
    ("report", "EXTERNAL_MODEL_FAILURE", (
        '402: {"message":"Insufficient Balance","type":"unknown_error","param":null,"code":"invalid_request_error"}'
    ), "MODEL_NO_BALANCE"),
    # OpenAI's quota error is a 429 (pi-ai dist/utils/retry.js lists insufficient_quota as not retryable)
    ("classify", "EXTERNAL_API_FAILURE", (
        '一次性文本调用失败（exit 1）：429: {"message":"You exceeded your current quota, please check your plan '
        'and billing details.","type":"insufficient_quota","param":null,"code":"insufficient_quota"}'
    ), "MODEL_NO_BALANCE"),
    ("report", "EXTERNAL_MODEL_FAILURE", (
        '400 {"type":"error","error":{"type":"invalid_request_error","message":"Your credit balance is too low '
        'to access the Anthropic API. Please go to Plans & Billing to upgrade or purchase credits."}}'
    ), "MODEL_NO_BALANCE"),
    # 智谱 error 1113 (arrears) and 1302 (concurrency) through the OpenAI-compatible adapter
    ("report", "EXTERNAL_MODEL_FAILURE", '429: {"code":"1113","message":"您的账户已欠费，请充值后重试。"}',
     "MODEL_NO_BALANCE"),
    ("report", "EXTERNAL_MODEL_FAILURE",
     '429: {"code":"1302","message":"您当前使用该API的并发数过高，请降低并发，或联系客服增加限额。"}',
     "MODEL_RATE_LIMITED"),
    ("report", "EXTERNAL_MODEL_FAILURE", (
        '429 {"type":"error","error":{"type":"rate_limit_error","message":"Number of request tokens has '
        'exceeded your per-minute rate limit"}}'
    ), "MODEL_RATE_LIMITED"),
    ("report", "EXTERNAL_MODEL_FAILURE", '529 {"type":"error","error":{"type":"overloaded_error","message":"Overloaded"}}',
     "MODEL_BUSY"),
    # openai core/error.js makeMessage: no body -> '<status> status code (no body)'; an HTML body
    # from a relay is not JSON, so the text itself follows the status
    ("classify", "EXTERNAL_API_FAILURE", "一次性文本调用失败（exit 1）：503 status code (no body)", "MODEL_BUSY"),
    ("report", "EXTERNAL_MODEL_FAILURE", (
        "502 <html>\r\n<head><title>502 Bad Gateway</title></head>\r\n<body>\r\n"
        "<center><h1>502 Bad Gateway</h1></center>\r\n<hr><center>nginx</center>\r\n</body>\r\n</html>"
    ), "MODEL_BUSY"),
    # SDK APIConnectionTimeoutError / APIConnectionError; vendor pi.py's own timeout
    ("report", "EXTERNAL_MODEL_FAILURE", "Request timed out.", "MODEL_TIMEOUT"),
    ("report", "EXTERNAL_MODEL_FAILURE", "Pi generation timed out; see RPC log", "MODEL_TIMEOUT"),
    ("classify", "EXTERNAL_API_FAILURE", "一次性文本调用失败（exit 1）：Connection error.", "MODEL_TIMEOUT"),
    # pi-ai dist/utils/overflow.js documents these overflow messages
    ("report", "EXTERNAL_MODEL_FAILURE", (
        '400 {"type":"error","error":{"type":"invalid_request_error","message":'
        '"prompt is too long: 213462 tokens > 200000 maximum"}}'
    ), "MODEL_CONTEXT_TOO_LONG"),
    ("report", "EXTERNAL_MODEL_FAILURE", (
        '400: {"message":"This model\'s maximum context length is 131072 tokens. However, you requested '
        '150000 tokens (134000 in the messages, 16000 in the completion). Please reduce the length of the '
        'messages or completion.","type":"invalid_request_error","param":null,"code":"invalid_request_error"}'
    ), "MODEL_CONTEXT_TOO_LONG"),
    ("report", "EXTERNAL_MODEL_FAILURE", (
        '404: {"message":"The model `gpt-9` does not exist or you do not have access to it.",'
        '"type":"invalid_request_error","param":null,"code":"model_not_found"}'
    ), "MODEL_NOT_FOUND"),
    ("report", "EXTERNAL_MODEL_FAILURE", '404 {"type":"error","error":{"type":"not_found_error","message":"model: claude-opus-9"}}',
     "MODEL_NOT_FOUND"),
    ("report", "EXTERNAL_MODEL_FAILURE", (
        '400: {"message":"Model Not Exist","type":"invalid_request_error","param":null,"code":"invalid_request_error"}'
    ), "MODEL_NOT_FOUND"),
    # pi-coding-agent dist/core/model-resolver.js
    ("classify", "EXTERNAL_API_FAILURE", (
        '一次性文本调用失败（exit 1）：Model "deepseek/deepseek-v9" not found. Use --list-models to see available models.'
    ), "MODEL_NOT_FOUND"),
    # 完整精读's key points (one-shot calls) and plan (a Pi run) call the model too (PLAN 15.4.11)
    ("keypoints", "EXTERNAL_API_FAILURE", "一次性文本调用失败（exit 1）：503 status code (no body)", "MODEL_BUSY"),
    ("plan", "EXTERNAL_MODEL_FAILURE", '429 {"type":"error","error":{"type":"rate_limit_error"}}', "MODEL_RATE_LIMITED"),
    # A local CLIProxyAPI (Go) cut the stream of a long gpt-6-luna call at 「最高」 (English run 2026-09-29)
    ("keypoints", "EXTERNAL_API_FAILURE", "一次性文本调用失败（exit 1）：unexpected EOF", "MODEL_TIMEOUT"),
    # ... and its upstream proxy (v2rayN on 10809) resetting the connection (Kabbalah run 2026-09-29)
    ("keypoints", "EXTERNAL_API_FAILURE", (
        "一次性文本调用失败（exit 1）：read tcp 127.0.0.1:56032->127.0.0.1:10809: wsarecv: "
        "An existing connection was forcibly closed by the remote host."
    ), "MODEL_TIMEOUT"),
    # Codex CLI 0.159.0 and Claude Code 2.1.285 with an endpoint that is down or cuts the stream
    # (their real output against a local fake API, PLAN 15.4.13; agents/runs.py puts 「… 调用失败：」 first)
    ("report", "EXTERNAL_MODEL_FAILURE",
     "Codex CLI 调用失败：stream disconnected before completion: error sending request", "MODEL_TIMEOUT"),
    ("report", "EXTERNAL_MODEL_FAILURE",
     "Codex CLI 调用失败：Reconnecting... waiting for network (Connection failed: error sending request)",
     "MODEL_TIMEOUT"),
    ("keypoints", "EXTERNAL_MODEL_FAILURE", (
        "Claude Code 调用失败：API Error: Connection refused — a firewall or proxy may be blocking it (ECONNREFUSED)"
    ), "MODEL_TIMEOUT"),
    ("plan", "EXTERNAL_MODEL_FAILURE", "Claude Code 调用失败：Prompt is too long", "MODEL_CONTEXT_TOO_LONG"),
    # OpenAI's "Unsupported value" error (the wording its API uses for a parameter a model does not
    # accept, e.g. temperature); a thinking level passed through for a model the catalogue lacks
    ("report", "EXTERNAL_MODEL_FAILURE", (
        "400 Unsupported value: 'reasoning_effort' does not support 'max' with this model. "
        "Supported values are: 'low', 'medium', and 'high'."
    ), "MODEL_THINKING_UNSUPPORTED"),
    # ---- 本机 (transcribe/local.py; downloader/http.py 'unable to write data: <OSError>'; Windows OSError) ----
    ("transcribe", "CUDA_UNAVAILABLE", "尚未安装本地转写组件，请先在设置里启用本地转写。", "ASR_COMPONENTS_MISSING"),
    ("transcribe", "ASR_FAILURE", "本地转写进程异常结束（exit 3221225477），请查看 asr-worker.log。",
     "ASR_WORKER_CRASHED"),
    ("download", "DOWNLOAD_FAILURE", "ERROR: unable to write data: [Errno 28] No space left on device", "DISK_FULL"),
    ("finalize", None, "OSError: [WinError 112] 磁盘空间不足。: 'media.m4a'", "DISK_FULL"),
]


@pytest.mark.parametrize(("stage", "code", "text", "expected"), SAMPLES)
def test_each_real_error_gets_its_reason(stage, code, text, expected):
    assert errors.classify(stage, text, code) == expected


def test_the_same_words_mean_different_things_in_different_stages():
    # A timeout while downloading is the network; while writing the report it is the model.
    assert errors.classify("download", "Request timed out.") == "SITE_UNREACHABLE"
    assert errors.classify("report", "Request timed out.") == "MODEL_TIMEOUT"
    # YouTube's 429 is not the model's rate limit, and there is no category for it.
    assert errors.classify("download", "ERROR: [youtube] x: HTTP Error 429: Too Many Requests") == "UNCLASSIFIED"
    assert errors.classify("report", '429 {"type":"error","error":{"type":"rate_limit_error"}}') == "MODEL_RATE_LIMITED"


def test_youtube_rate_limit_is_not_a_missing_video():
    # 'Video unavailable' followed by YouTube's rate-limit note (youtube/_video.py): the video is there.
    text = ("ERROR: [youtube] dQw4w9WgXcQ: Video unavailable. This content isn't available, try again later. "
            "The current session has been rate-limited by YouTube for up to an hour.")
    assert errors.classify("download", text) == "UNCLASSIFIED"
    assert errors.classify("download", "ERROR: [youtube] dQw4w9WgXcQ: Video unavailable") == "VIDEO_NOT_FOUND"


def test_anything_else_is_unclassified():
    assert errors.classify("report", "Pi exited before agent_settled; see pi.stderr.log") == "UNCLASSIFIED"
    assert errors.classify("download", "ERROR: unable to download video data: HTTP Error 403: Forbidden") == "UNCLASSIFIED"
    assert errors.classify("report", "KeyError: 'oops'") == "UNCLASSIFIED"
    assert errors.classify("report", "Pi generation timed out; see RPC log") == "MODEL_TIMEOUT"


def test_every_reason_has_a_chinese_sentence_and_an_action(tmp_path):
    codes = {expected for *_, expected in SAMPLES} | {"UNCLASSIFIED"}
    assert codes == set(errors.REASONS)  # every reason has a real sample
    for code in codes:
        reason, action = errors.explain(tmp_path, code)
        assert reason and action, code
        assert any("一" <= char <= "鿿" for char in reason + action), code
    assert errors.explain(tmp_path, "UNCLASSIFIED")[0] == "未归类的错误。"


def test_a_crashed_transcription_worker_points_at_its_log_file(tmp_path):
    _, action = errors.explain(tmp_path, "ASR_WORKER_CRASHED")
    assert str(paths.logs_dir(tmp_path) / "asr-worker.log") in action


def test_codes_from_before_the_change_have_no_reason(tmp_path):
    assert errors.explain(tmp_path, "EXTERNAL_MODEL_FAILURE") is None
    assert errors.explain(tmp_path, "MODEL_TIMEOUT") is not None


def test_details_are_the_whole_original_text_with_the_exception_type():
    long_tail = "x" * 5000
    exc = IngestError("DOWNLOAD_FAILURE", f"\x1b[0;31mERROR:\x1b[0m {BILI_412[len('ERROR: '):]} {long_tail}")
    assert errors.details(exc) == f"IngestError: {BILI_412} {long_tail}"
    assert errors.details(KeyError("oops")) == "KeyError: 'oops'"


def _start(client, url=BV_URL):
    return client.post("/api/items", json={"url": url, "figures": False}).json()["id"]


def test_a_failure_keeps_its_stage_reason_and_original_text(client, monkeypatch):
    def download_blocked(ctx):
        raise IngestError("DOWNLOAD_FAILURE", BILI_412)

    monkeypatch.setitem(client.app.state.queue.impls, "download", download_blocked)
    item_id = _start(client)
    row = wait_for_status(client, item_id, "failed")
    assert row["stage"] == "download"
    assert row["error_code"] == "BILIBILI_RISK_CONTROL"
    assert row["error_message"] == f"IngestError: {BILI_412}"
    reason, action = errors.explain(client.app.state.data_dir, "BILIBILI_RISK_CONTROL")
    assert (row.get("error_reason"), row.get("error_action")) == (reason, action)
    queued = next(r for r in client.get("/api/queue").json() if r["id"] == item_id)
    assert (queued.get("error_reason"), queued.get("error_action")) == (reason, action)


def test_retry_clears_the_failed_stage(client, monkeypatch):
    def report_times_out(ctx):
        raise PiError("EXTERNAL_MODEL_FAILURE", "Request timed out.")

    impls = client.app.state.queue.impls
    working = impls["report"]
    monkeypatch.setitem(impls, "report", report_times_out)
    item_id = _start(client)
    row = wait_for_status(client, item_id, "failed")
    assert (row["stage"], row["error_code"]) == ("report", "MODEL_TIMEOUT")
    impls["report"] = working
    assert client.post(f"/api/items/{item_id}/retry").status_code == 200
    row = wait_for_status(client, item_id, "done")
    assert (row["stage"], row["error_code"], row["error_message"]) == (None, None, None)


def test_a_row_failed_before_the_change_still_shows_its_message(client, monkeypatch):
    def report_times_out(ctx):
        raise PiError("EXTERNAL_MODEL_FAILURE", "Request timed out.")

    data_dir = client.app.state.data_dir
    old = items_store.create_item(data_dir, platform="bilibili", video_id="BV1old0000000",
                                  source_url="https://www.bilibili.com/video/BV1old0000000/", status="failed")
    message = "模型调用失败：请在「设置 · 模型」里点「测试模型」，检查 Key、模型名和网络；中转站超时可以稍后重试。（Request timed out.）"
    items_store.update_item(data_dir, old, stage=None, error_code="EXTERNAL_MODEL_FAILURE", error_message=message)
    monkeypatch.setitem(client.app.state.queue.impls, "report", report_times_out)
    new = _start(client)
    wait_for_status(client, new, "failed")
    rows = {row["id"]: row for row in client.get("/api/queue").json()}
    assert rows[old]["error_message"] == message
    assert (rows[old].get("error_reason"), rows[old].get("error_action")) == (None, None)
    assert rows[new].get("error_reason") == errors.explain(data_dir, "MODEL_TIMEOUT")[0]


def test_the_reserved_fake_link_fails_in_download_with_bilibili_risk_control(client):
    from prometheus.fake.pipeline import RISK_CONTROL_VIDEO

    item_id = _start(client, f"https://www.bilibili.com/video/{RISK_CONTROL_VIDEO}/")
    row = wait_for_status(client, item_id, "failed")
    assert (row["stage"], row["error_code"]) == ("download", "BILIBILI_RISK_CONTROL")
    assert "HTTP Error 412: Precondition Failed" in row["error_message"]
    other = wait_for_status(client, _start(client), "done")
    assert other["error_code"] is None
