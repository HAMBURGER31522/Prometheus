# 验收记录

由执行 agent 填写客观结果；需要用户判定的条目（D4、D6）记录用户本人的结论和日期。

## 固定样本

| 用途 | 链接 | 时长 | 选定日期 |
|---|---|---|---|
| M3/M4 短视频（5–10 分钟，B 站） | https://www.bilibili.com/video/BV1bZhQ6VEQK/ （罗素：为了阻止末日，可以先点燃一场战争吗？· 大圆镜科普） | 498.4 秒 | 2026-09-25 |
| D5 长视频（约 3 小时，B 站） | 待定 | | |
| D7 YouTube 视频 | 待定 | | |

## D4 极简设计（用户判定）

- 截图：`docs/screenshots/`
- 用户结论：待定

## D5 真实链路耗时

| 组合 | 入队 → 完成 | 预算 | 结果 |
|---|---|---|---|
| 云端转写 · 不配图 | | ≤ 20 分钟 | |
| 本地转写 · 不配图 | | ≤ 25 分钟 | |
| 云端转写 · 配图 | | ≤ 30 分钟 | |

## D6 配图 A/B（用户判定）

- A/B 报告位置：`acceptance-output/ab-<日期>/`（不提交）
- `inspect_report` 结果：待定
- 用户结论：待定

## D7 / D8 / D9 / D10

待定

## M3 live 测试记录（2026-09-25）

- 样本：BV1bZhQ6VEQK（罗素：为了阻止末日，可以先点燃一场战争吗？· 大圆镜科普，498.4 秒）
- 本地转写链路：**通过**（`test_bilibili_local_transcribe_to_transcript`）。resolve → download（media.m4a）→ ffmpeg 16kHz wav → faster-whisper large-v3-turbo。
  - worker 日志：`asr backend=local device=cuda model=large-v3-turbo`（RTX 4060，GPU 转写耗时 22.7 秒）
  - asr.json：86 段，language=zh；transcript.md 与 vendor 黄金格式一致（86 个 unit 行）
  - CUDA 组件与模型缓存于 `acceptance-output/live-data/`（组件约 600MB，模型约 1.5GB）
- 云端转写（paraformer）：待 DASHSCOPE_API_KEY（2026-09-25 用户首次提供的字符串疑似显示层损坏，已请求重新提供）
- YouTube 链路（cookies）：待 PROMETHEUS_TEST_YT_COOKIES
- 运行中发现并修复：uv 管理的 .venv 无 pip 模块 → 组件安装回退 `uv pip install`（提交 6192182）；live 测试改用稳定数据目录跨运行缓存（提交 fa72451、mkdir exist_ok 修复）
