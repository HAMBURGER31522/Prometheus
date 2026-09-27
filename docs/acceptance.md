# 验收记录

由执行 agent 填写客观结果；需要用户判定的条目（D4、D6）记录用户本人的结论和日期。

## 固定样本

| 用途 | 链接 | 时长 | 选定日期 |
|---|---|---|---|
| M3/M4 短视频（5–10 分钟，B 站） | https://www.bilibili.com/video/BV1bZhQ6VEQK/ （罗素：为了阻止末日，可以先点燃一场战争吗？· 大圆镜科普） | 498.4 秒 | 2026-09-25 |
| D5 长视频（约 3 小时，B 站） | **待选定**（见下方 M9 说明） | | |
| D7 YouTube 视频 | https://www.youtube.com/watch?v=jNQXAC9IVRw（M3 链路验证用）；D5 级 YouTube 样本待定 | | |
| R5 转写实测·中文 | https://www.youtube.com/watch?v=08PFXFA8Rs8 （影视飓风《UP主们都怎么做字幕？调研100位UP》；参考 = 作者上传的人工 zh-CN 字幕） | 777.9 秒 | 2026-09-26 |
| R5 转写实测·英文 | https://www.youtube.com/watch?v=BHY0FxzoKZE （TED · Wendy Suzuki《The Brain-Changing Benefits of Exercise》；参考 = TED 人工 en 字幕） | 783.0 秒 | 2026-09-26 |

R5 样本选择说明：B 站的 CC 字幕需要登录才能获取，所以两段样本都取自 YouTube（`E:\google\cookies.txt`，2026-09-26 直连可用，7897 代理当时未开）。李永乐老师等频道的字幕是烧录在画面里的，没有字幕轨道，不能当参考。筛选条件：时长 5–15 分钟，并且有**人工**字幕轨道（yt-dlp 的 `subtitles`，而不是 `automatic_captions`）。

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
- YouTube 链路（cookies）：**通过**（`test_youtube_cookies_chain_local_transcribe`，样本 Me at the zoo）。cookies=E:\google\cookies.txt 经代理 7897 下载成功；本地转写 language=en（非中文路径不传 initial_prompt 的行为同步验证）；转写 5 段。
- 云端转写（paraformer）：**用户指示暂缓**（2026-09-25，消息原文「那个云端先暂时不弄」），待 DashScope Key 后补跑；live 命令中该项为 skip。
- 用户提供的 LLM 供应商：OpenAI 兼容中转 `https://oapi.firedog.dev/v1`（key 本机环境变量提供，不入库），模型 gpt-6-sol / gpt-5.5 已实测可用；用于 M4 探针与 live。用户确认设计意图为任意供应商接入（custom 提供商）。
- 运行中发现并修复：uv 管理的 .venv 无 pip 模块 → 组件安装回退 `uv pip install`（提交 6192182）；live 测试改用稳定数据目录跨运行缓存（提交 fa72451、mkdir exist_ok 修复）

## M9 真实验收（2026-09-26 状态：部分就绪，部分待条件）

已完成（全部免费路径，本地转写 + 中转站 LLM）：
- 本地转写链路：8 分钟样本（86 段，device=cuda，22.7s）与 104 分钟样本（3716 段，GPU 6.4 分钟）均实证通过。
- 报告生成链路：BV1bZhQ6VEQK 经 custom 供应商（gpt-6-sol）11 分钟产出完整报告，D4/M4 全部断言通过（25 个 data-source-units、题头 Bilibili；、无外部引用、分类「战争伦理」）。
- 思维导图链路：7 个一级分支、7 个时刻链接、校验通过、mindmap_status=ok。
- 安装包：165MB（≤300MB），静默安装/卸载/数据保留冒烟通过（installed-smoke.ps1）。

未做（诚实清单，按用户指示留口子）：
1. D5 三组合中的两个云端组合：待 DashScope API Key（用户指示「那个云端先暂时不弄」）。
2. D5 约 3 小时样本视频：选定流程受阻——B 站搜索/空间/热门接口当晚持续风控限流（搜索需 cookies 且 1–2 次请求即封，热门榜 300 条无 2:50–3:10 视频）。**需要用户提供 BV 号**，或换时段重新搜索。
3. D5 预算风险提示：中转站并发限制 + 响应速度可能使「本地转写不配图 ≤ 25 分钟」超标；换 DeepSeek 官方 Key 重跑可对照。
4. D7 YouTube 完整验收：M3 已验证 cookies 下载链路 + 本地转写（en 5 段）；D5 级完整跑通待 3 小时样本或 YouTube 长视频样本。
5. D10 CI：本次会话结束前需确认 GitHub Actions 绿（由收尾自动验证）。

## M5 配图（2026-09-26 状态：代码完成，live trial 受阻于中转站订阅）

已完成：
- 帧提取与筛选（TDD 5 用例）：ffmpeg 场景抽帧 + showinfo 解析 + 20 秒间隔/每小时 20 帧/总 80 帧/稀疏补帧规则；真实视频抽帧成功（BV1bZhQ6VEQK 保留 20 帧候选）。
- figures.md 正式规则文本（含「不要自己转 base64」关键约束）；frames 阶段接入流水线；报告阶段 figures 旗标贯通（frames.json 存在 + 设置声明支持看图时启用）；定稿 base64 内联逻辑（M4 已测）。

未做/受阻（诚实说明）：
1. **带配图的完整报告 live trial 未跑成**：中转站 oapi.firedog.dev 对图片输入（multimodal content）返回 `SUBSCRIPTION_NOT_FOUND — No active subscription found for this group`（gpt-6-sol / gpt-5.5 / gpt-6-luna 全部如此；纯文本正常）。Agent 读取帧图片后的下一次模型请求即 403。
2. 解除条件：需要一个支持看图的供应商——计划书默认的 DeepSeek 官方 `deepseek-flash` 即支持图片（vendor models.json input 含 image）。提供 DeepSeek Key 后即可跑 A/B（D6 需用户并排阅读签字）。
3. D5/D6 的 A/B 对比：待上述条件 + 配图版报告生成成功后进行。

补充（2026-09-26）：用户随后提供的第二个中转站 `https://ai.venlacy.com/v1`（key sk-eLFM…，分组 codex）实测：`/v1/models` 仅列出 gpt-5.6-sol，但 chat/completions 与 responses 两种接口均返回 `No available channel for model gpt-5.6-sol under group codex`——该分组当前无可用通道，key 暂不可用。两个中转站均无法进行配图（多模态）请求，M5 的 A/B 解除条件不变：需要支持看图的供应商（如 DeepSeek 官方 deepseek-flash）。

## E7 界面观感与动效（用户判定）

### 第一轮（2026-09-27，R7 截图 `docs/screenshots/r7/` 与浏览器预览）

用户没有否定方向 C 的整体效果，提出以下意见（已写入 PLAN 15.4.7–15.4.9，由 R7b / R7c 处理）：

- 缺陷：魔法卡巴拉报告的目录，点击章节后变成白页。原因：srcdoc 页面把 `#s3` 解析到软件自己的地址。已修复（1b31ea8），并补了端到端测试。
- 侧栏希望能往左收起，给正文让出空间，动效要丝滑；正文要能放大缩小。用户选择：收成图标窄条。
- 导图展开后的要点内容太少（例：「三套卡巴拉体系」只有一句）。用户选择：每个要点加 2–4 句详解，并能跳到精读对应章节。
- 英文视频：精读照样是中文；字幕中英对照（每段英文下方是中文）；光标停在单词上显示释义，并能切换各大词典。用户选择：离线词典 ECDICT，加一键切换到有道、剑桥、柯林斯、必应、韦氏。
- 报告里的图片希望能点击后浮动放大（参考 Discourse），用滚轮缩放，点击图片外缩回原位置。
- 设置：下拉框的展开箭头太靠外、展开的列表太方正；API Key 要有眼睛图标；思考强度默认「中」；希望能获取模型列表；模型设置太简陋（不需要 ModelGate 那么庞大）。参考 CC Switch。
- 云端转写：默认必剪，同时支持自己接的接口。用户选择：增加「自定义（OpenAI 兼容转写接口）」。

最终判定待安装版试用后给出（R8）。

