# 设计决策

只记录未来需要理解「为什么这样设计」的选择。旧决定被替代时保留原文，标注新的生效方案。
以下决策均于 **2026-09-25** 在规划阶段与用户确认；依据来自对 VRA（commit `d060dfb`）、BiliSum（v1.21.1）源码的阅读和本机实测。

---

**D-01 基于 VRA 二开，以 git subtree 引入**
问题：以哪个项目为基础。
决定：以 video-report-agent 为基础（精读报告质量是本项目的核心价值），用 `git subtree add`（不 squash）放进 `vendor/video-report-agent`，锁定在 `d060dfb`。
原因：保留上游历史，以后可以 `git subtree pull` 合并作者对 Skill 的更新；BiliSum 功能完善，但对本项目来说太多。
代价：对 vendor 的修改要尽量少并登记，否则合并上游时会冲突。

**D-02 许可证：MIT**
VRA 仓库没有 LICENSE。用户确认 VRA 作者（用户的朋友）同意二次开发，并同意按 MIT 发布。README 注明来源与授权。建议作者在上游补上 LICENSE。

**D-03 外壳用 Tauri 2，而不是 Electron**
原因：本机已有可用的 Rust 工具链（Artemis 项目，Rust 1.98.1 + MSVC），用户做过 Tauri；Tauri 使用系统自带的 WebView2（本机为 153 版），安装包比 Electron 约小 100MB。
代价：多一门语言（Rust）。Rust 侧只负责窗口、启动和关闭后端、原生对话框。

**D-04 后端用可移植 CPython，不用 PyInstaller**
原因：VRA 精读模式会让 Agent 通过 `VIDEO_REPORT_PYTHON` 执行绘图脚本，需要一个真实的 python.exe；PyInstaller 冻结后 `sys.executable` 不再是 Python 解释器。
决定：python-build-standalone 3.12.14 随安装包分发，依赖装进它的副本。

**D-05 Pi 在 Windows 上用原生 PowerShell 工具**
问题：Pi 的 bash 工具需要 Git Bash，用户电脑上不一定有。
决定：`--tools read,write,edit,powershell`，并通过追加系统提示告诉 Agent 用 `& $env:VIDEO_REPORT_PYTHON script.py` 运行 Python。
代价与风险：Agent 可以在工作目录里执行命令，这不是系统级沙箱，恶意字幕理论上可能诱导执行命令。用户接受这一风险，以保留精读模式的精确图表能力。

**D-06 只做精读（Standard）模式**
速览的作用由思维导图承担。

**D-07 配图由写报告的同一个 Agent 完成**
问题：怎么做图文结合。
决定：写作前按场景切换抽候选帧；Agent 用 Pi 的 `read` 工具看图、挑图，就地插入 `<figure>`；最后由程序把图片内联成 base64，报告仍是单个文件。配图规则放在单独的附加文件里，不修改 VRA 原 Skill 文件。
原因：图片放在正文最需要的位置；不需要 BiliSum 那样单独的视觉模型流水线和第二套模型配置。
代价：要求模型能看图（VRA 自定义的 `deepseek-flash` 可以，Pi 内置的 `deepseek-v4-flash` 不行），不支持看图时自动关闭配图；必须通过 A/B 验收（D6）证明文字质量没有下降。

**D-08 思维导图用 markmap**
BiliSum 的做法是 LLM 输出 JSON 节点树，再用 React Flow 自己画。markmap 直接渲染 Markdown 大纲，`.md` 本身可读，还能导入 XMind / Obsidian，布局代码少得多。导图由报告正文提炼，保证和文章一致。

**D-09 不限视频时长**
VRA 在 `ingest.py:21` 写死了 3 小时上限，单任务超时 30 分钟，文档里没有给出理由。默认模型 `deepseek-flash` 的上下文是 100 万 token，足以容纳十几个小时的中文转写。决定：去掉上限，Pi 超时改为 `1800 + 600 × ⌈时长(小时)⌉` 秒。

**D-10 转写：本地 + 云端，只面向 Windows**
VRA 原本有两个转写后端：MLX Whisper（只能在 Apple 芯片的 Mac 上运行，作者自己开发用）和百炼云端 paraformer（`paraformer.py`）。在 Windows 上，VRA 原本只有云端可用。
决定：新增本地 faster-whisper large-v3-turbo（默认，本机 RTX 4060 8GB），CUDA 运行库和模型在首次启用时下载到数据目录；原样保留 VRA 的百炼云端（paraformer / Fun-ASR），不做修改；**不考虑 macOS，不接入 MLX**。设置里二选一：选本地时云端的 Key 和模型输入框禁用，选云端时才能输入；切换不清空已保存的 Key。
不使用平台自带字幕，因为 VRA 的质量是在带时间戳的 ASR 转写上调出来的。
费用参考：paraformer-v2 官方标价 0.00008 元/秒（约 0.29 元/小时），只对识别出的说话部分计费（2026-09-25 查证）。

**D-11 YouTube 需要 cookies**
2026-09-25 实测：经本机代理（7897）访问 YouTube，不带 cookies 会返回 "Sign in to confirm you're not a bot"。决定：设置里提供「YouTube cookies.txt」选项。yt-dlp 的 JS 运行时复用随包分发的 Node。B 站只支持公开视频，不做登录。

**D-12 分类只有一层，由模型自动归入**
模型优先从已有分类里选，都不合适时新建；用户可以改名、移动、合并。三个内容页签共用同一套分类和标题，标题显示为「报告标题 + 小字原标题 / UP 主」。

**D-13 数据按条目存放**
`items/<ID>/{report,mindmap,subtitle,work}/`：删除或重新生成一个视频时只动一个文件夹；子文件夹名直接说明内容类型。

**D-14 不做的东西**
macOS 支持（包括 VRA 的 MLX 转写）、问答 / RAG、标签网络、B 站登录、平台字幕、合集或播放列表批量导入、本地文件导入、速览模式、PNG 长图、费用显示、深色模式、自动更新、多级分类。

**D-15 API Key 明文保存在数据目录**
和 VRA 的 `.env` 做法一致，Key 放在仓库之外的数据目录里。这是已知局限，没有接入 Windows DPAPI。

---

以下决策于 **2026-09-25** 发布前复查计划书时补充，依据是对 VRA、Pi 0.85.0、faster-whisper 1.2.1 源码的核对。

**D-16 Pi 直接用 node.exe 调用，长提示词走标准输入**
问题：VRA 用 `shutil.which("pi")` 找到的是 Windows 上的 `pi.cmd` 批处理文件，参数会先经过 cmd.exe 解析（`%`、`^`、`&` 等会被改写），而且命令行最长只有 8191 个字符；思维导图的输入是整篇报告的大纲，会超出这个长度。
决定：一律以 `node.exe cli.js` 调用 Pi（给 `PiRunner` 增加 `command_prefix` 参数）；一次性文本任务的提示词通过标准输入传入。

**D-17 PiRunner 显式传入配置目录**
问题：VRA 的 `pi.py` 在模块导入时按当前工作目录算出 `PI_AGENT_DIR`。首次启动时数据目录还没选，按原逻辑会写进安装目录。
决定：给 `PiRunner` 增加 `agent_dir` 参数（附录 A V2）。

**D-18 延迟导入 report_image，打包版不带 playwright**
问题：VRA 的 `paraformer.py` 在云端转写运行途中会导入 `pipeline`，而 `pipeline.py` 顶部导入了依赖 playwright 的 `report_image`。打包版为了控制体积去掉了 playwright，不修改的话每次云端转写都会在中途崩溃。
决定：把这条导入移进使用它的函数内部（附录 A V3，一行改动，可以提交给上游）。

**D-19 本地转写在子进程中运行**
原因：线程里的 CTranslate2 推理无法强制中断，放在子进程里才能真正取消任务；子进程退出后显存随之释放。VRA 对 MLX 转写也是这样做的。

**D-20 中文字幕做繁→简转换**
问题：Whisper 转写普通话时偶尔会输出繁体字。VRA 在整理转写时会用 OpenCC 转成简体，所以报告不受影响，但「原样字幕」直接取 ASR 输出。
决定（用户确认）：中文字幕做 OpenCC `t2s` 逐字转换（机械转换，不经 AI 改写，时间轴和断句不变）；转写时对中文传 `initial_prompt="以下是普通话的句子。"`，让模型尽量直接输出简体。

**D-21 应用内不打开外部网站**
报告、导图里的外部链接统一拦截，交给系统浏览器打开：报告通过接口返回时临时注入拦截脚本（不修改磁盘上的文件），导图在容器上拦截点击。

---

以下决策于 **2026-09-25** 里程碑 M0 实施期间补充。

**D-22 根工作区依赖后端包；httpx 只进 dev 组**
问题：Done When 和 CI 的命令是根目录下的 `uv run pytest backend/tests`，而 `uv run` 只同步根项目的依赖；如果根项目不声明依赖，CI 的新环境装不上 backend 与 VRA。
决定：根 `pyproject.toml` 的 `dependencies = ["prometheus-backend"]`（经 `tool.uv.sources` 指向工作区），形成 prometheus → prometheus-backend → video-report-agent 的链；`httpx==0.28.1` 放根 dev 组（fastapi 的 TestClient 需要，仅测试用，VRA 本身也依赖它）。
代价：根项目成为元包；后续给 backend 加依赖仍只改 `backend/pyproject.toml`。

**D-23 前端补两个规格未列出的类型包**
问题：`tsc --noEmit` 编译 React 需要 `@types/react` / `@types/react-dom`，第 4 节版本表没有列出（类型包不是技术选型）。
决定：devDependencies 增加 `@types/react==19.3.0`、`@types/react-dom==19.3.0`，与 react 19.3.0 同步升级。

**D-24 占位应用图标**
问题：`tauri-build` 在 Windows 上必须有 `src-tauri/icons/icon.ico` 才能生成资源文件，`cargo check` 才能通过；规格未规定图标内容。
决定：用标准库脚本生成 32×32、强调色 #c8562e 的占位 ICO（PNG 压缩格式）提交进仓库；正式图标在 M8 打包时再定。

---

以下决策于 **2026-09-26** M4 实施期间补充。

**D-25 LLM 供应商：任意 OpenAI 兼容端点（custom 提供商路径验证）**
问题：用户使用第三方 OpenAI 兼容中转（`https://oapi.firedog.dev/v1`，模型 gpt-6-sol / gpt-5.5）而非 DeepSeek 官方；确认接入面。
决定：一切模型调用都走 Pi 的 provider 机制：内置 deepseek/zhipu 之外，任何 OpenAI 兼容端点通过设置页的 custom 提供商接入（baseUrl + apiKey + model 写入 models.json，api=openai-completions），PiRunner / 一次性文本调用统一从设置读取。用户确认这就是设计意图（「任意供应商接入并非只能 deepseek」）。
代价：Pi 只说 OpenAI 兼容协议；非兼容 API 需要用户自建中转。

**D-26 探针结论（M4 第 1 步）**
问题：Pi 的 PowerShell 工具能否执行 Python 绘图脚本（D-05 风险）。
决定与证据：在真实转写（BV1yPb46xExH，86 段）上手动运行 Pi（`--tools read,write,edit,powershell`，custom 提供商 gpt-6-sol），Agent 成功编写 plot.py 并以 `& $env:VIDEO_REPORT_PYTHON plot.py` 执行，生成 chart.png（45,578 字节，matplotlib 3.11.2）。结论：PowerShell 工具链可用，D-05 风险解除；matplotlib 加入开发 .venv（打包时随依赖安装）。
注意：中转站账号有严格并发限制（多请求并发报 gateway_concurrency_limit），Pi 的串行调用模式兼容，偶发 429 需重试。

**D-27 M5 配图暂缓，流水线先行**
问题：M5 的完成标准（D6）需要用户本人并排阅读 A/B 报告签字，阻塞后续里程碑。
决定：M4/M6 先行（报告、分类、导图全部落地，figures 阶段在流水线中保持关闭，`figures=False && model_supports_images=False`）；M5 的候选帧/figures.md/内联逻辑待用户可参与 A/B 时再实现。应用功能不受影响（配图是可选开关）。

**D-28 input.json 字段集**
问题：PLAN 8.6 要求 input.json 含「vendor 写入的字段」+ platform/title 等，但 vendor 的字段含 media_config（转写运行时配置，与报告 Agent 无关，且本地路径不调用 resolve_media_config）。
决定：input.json = url、video_id、report_mode=standard、transcript_mode=asr-only、ocr_mode=off、ocr_roi、subtitle_file、platform（Bilibili/YouTube）、title、uploader、attribution（`{平台}；{uploader}；《{title}》；{url}`，与 vendor 格式一致）。media_config 字段不进 input.json。

---

以下决策于 **2026-09-26** 第二阶段规格确认时补充（详见 PLAN 第 15 节）。

**D-29 界面方向：C 液态玻璃（墨夜外壳 + 浅色纸页报告）**
依据：用户在三个可交互原型（A 宣纸·墨 / B Mica / C 液态玻璃）中选定 C。报告不做深色：Agent 生成的图表按白纸配色，深色背景下会看不清。
用户的修改意见：侧栏不能遮挡内容；滚动条静止时淡出、滚动时显现；打开条目后侧栏高亮停留在当前页签；三个内容页签使用同一套「分类 → 条目 → 内容」版式；字幕按时间戳完整展示原文。

**D-30 思维导图改为 BiliSum 式知识树，替代 D-08 的 markmap**
问题：markmap 大纲过于简略；用户要求参考 BiliSum 的设计与写作思路。
决定：分层 JSON（root/theme/topic/leaf，节点带摘要和时间锚点），React Flow 画布加自写的横向树布局；另外导出 `思维导图.md` 供 Obsidian / XMind 使用。D-08 不再生效。

**D-31 知识库存储：可读文件夹 + PDC 式 AI 索引，替代 D-13**
问题：`items/<32位ID>` 在资源管理器里认不出是哪个视频；中间文件每小时视频约 220MB，库会越积越大。
决定：按「分类 / 日期 标题 / 精读.html·精读.md·思维导图.md·字幕.srt·字幕.txt·来源.url」存放；库根目录放 `llms.txt` 和 `index.json`（参考 PDC 协议「给人的 HTML 与给 AI 的 Markdown/JSON 两条通道 + 分层索引」的思路）；内部数据放隐藏的 `.prometheus\`；任务成功后清理中间文件。
实测（BV1yPb46xExH，104 分钟）：最终成果 1.4MB，中间文件 391MB；清理后每个视频约 2.5MB。

**D-32 云端转写改为必剪（免费，无需配置），替代 D-10 的百炼云端**
依据：用户的 DashScope Key 属于国际站（新加坡），那里没有 `paraformer-v2`；用户希望云端免费、开箱即用。2026-09-26 实测：原版 bcut-asr 返回 412；改用 VideoCaptioner 维护版的请求头后可用，8 分钟音频上传 16.5 秒、识别 12.9 秒，得到 192 段带时间戳的结果，中文错字比 Whisper 少，但几乎没有标点。
代价：这是非官方的逆向接口，随时可能失效或限流，所以失败时自动退回本地转写。

**D-32a 本地转写引擎待实测后由用户选定**
公开基准显示 Whisper-large-v3 的中文明显落后（WenetSpeech net 字错率 9.86%，Qwen3-ASR-1.7B 为 4.97%）。先在真实样本上比较 4 个引擎再定（PLAN 15.4.3）。

**D-33 自定义提供商支持 OpenAI / Anthropic 两种协议**
依据：用户的 justwoker 中转只开放 Anthropic 协议（`/v1/messages`，`/v1/chat/completions` 被 Cloudflare 拦截，返回 403）；venlacy 中转走 OpenAI 协议。2026-09-26 实测：两者的文本和图片输入都正常（justwoker `claude-opus-4-8`，venlacy `gpt-6-sol`）。中转站返回「分组无可用通道」时，是该 Key 所在分组没有上游，与模型能否识图无关。

**D-34 「重新生成导图」只重跑导图，条目保持 done（2026-09-26，R4）**
问题：PLAN 8.8 规定按钮调用 `POST /items/{id}/regenerate` 带 `{"only": "mindmap"}`，但没说明重跑期间条目处于什么状态，也没说明和整条流水线的队列如何配合。另外，任务成功后缓存里的报告副本已被清理。
决定：
- 只接受 `done` 条目（否则返回 409 `NOT_DONE`）。队列只重跑 `mindmap` 和 `publish` 两个阶段，报告改从知识库的 `精读.html` 读取。
- 重跑期间条目始终是 `done`（精读和字幕照常可读）。`mindmap_status` 为 NULL 表示「生成中」，结束后变为 `ok` 或 `failed`。出错、被取消或应用中途退出（启动时修正），都只把 `mindmap_status` 记为 `failed`。
- 导图重跑排在整条流水线任务的前面：它只要一两分钟，而且用户正在等它。
- 删除条目时，先停掉该条目正在进行或排队中的重跑。
原因：数据库对 `mindmap_status` 有 CHECK 约束（只允许 `ok`/`failed`），用 NULL 表示「待生成」就不用改表结构；而且普通流水线在导图阶段之前本来就是 NULL。条目保持 `done`，重跑失败时就不会把已完成的精读变成「失败」。
代价：重跑任务只保存在内存里，应用退出后不会自动续跑，需要用户再点一次按钮（此时 `mindmap_status` 已被改为 `failed`，按钮会重新出现）。控制台的任务队列里看不到导图重跑，进度只显示在导图页。

**D-35 本地转写：中文用 FunASR paraformer-zh，其他语言用 faster-whisper turbo（用户 2026-09-27 选定，替代 D-32a）**
依据：R5 实测（`docs/asr-bench.md`）。中文 13 分钟样本：FunASR 字错率 7.46%，识别 7 秒；whisper 7.86%，识别 30 秒。英文样本：whisper 词错率 2.78%；FunASR 用的是中文模型，12.98%，不可用。Qwen3-ASR 更慢，要 7GB 显存，也没有更准，不采用。
决定：本地转写按语言切换引擎，中文走 FunASR（paraformer-zh + fsmn-vad + ct-punc），其他语言仍走 faster-whisper turbo。
代价（用户选择时已知）：要额外带上 torch（约 4GB，自带 CUDA 运行库）和 FunASR 的模型（约 2.1GB），体积约增加 6GB，所以只能在首次使用时下载，不能放进安装包；另外需要一条可靠的语言判断规则。组件的下载方式和语言判断规则在 R6 定下后补记。

**D-36 必剪的结果不补标点，原样使用（用户 2026-09-27 选定）**
依据：必剪几乎不输出标点（每 100 字 0.9 个）。字幕按 2 秒左右一段显示，本来就很少用标点；精读 Agent 读没有标点的中文也没问题。补标点要么多带一个标点模型，要么多一次大模型调用，都不划算。

**D-37 字幕纠错放在精读之后，并参考报告（用户 2026-09-27 同意；D-36 中「不补标点」一条作废）**
问题：转写难免有同音错字（例如「记忆引擎」识别成「记忆迎亲」），必剪的结果还几乎没有标点。用户要求最终呈现的字幕必须有标点，并希望按上下文改正错字。
调研：BiliSum 的做法是优先使用 B 站自带字幕，再加 FunASR 热词；VRA 不改字幕，由写报告的 Agent 在写作时按上下文纠正（SKILL.md「纠错与显著信息」），纠错记录另存，字幕栏仍是原始识别。两者都没有「纠正字幕本身」这一步。
决定：新增 `subtitle_fix` 阶段（PLAN 15.4.6），在报告写好之后运行，把报告当作专有名词的参考；只改识别错字、补全标点，不改说法和时间，程序逐段校验改动幅度，超限的分段保留原文。原始识别另存为 `segments.raw.json`，字幕页可以切换查看。
原因：报告里的名词已经被 Agent 按上下文改对了，用它作参考比单凭上下文猜更可靠；放在精读之后，不影响 VRA 报告的生成流程和质量。
代价：每个视频多一次模型调用（输入和输出都约等于字幕字数的 token 数）；纠错失败时字幕保持原样。

**D-38 YouTube 人工字幕优先（用户 2026-09-27 同意）**
依据：作者上传的人工字幕比任何转写都准（R5 用它当参考答案）；借鉴 BiliSum 优先使用平台字幕的做法。
决定：YouTube 视频有与原语言匹配的人工字幕时，直接用它，跳过转写；不用自动字幕和机器翻译字幕。B 站字幕需要登录 cookie，本阶段不做。

**D-39 FunASR 用 ONNX 版在 CPU 上运行（2026-09-27，执行 agent 决定并告知用户）**
问题：用户选择的是 FunASR（D-35）。R5 实测的是 PyTorch 版，但它需要额外带 4GB 的 torch，而且只能从 download.pytorch.org 下载（本机实测约 30KB/s），首次使用基本下不完。
实测（R5 中文样本，同一套 paraformer-large + fsmn-vad + ct-punc，官方 int8 ONNX 版，onnxruntime CPU 32 线程）：字错率 7.97%（PyTorch 版 7.46%，whisper 7.86%）；替换错误 78 个，是本地引擎里最少的（PyTorch 版 119，whisper 87）；多出来的主要是零散的一两个字的删除。识别 13 分钟音频用 23.5 秒，不占显存。
决定：发布 ONNX 版。只需下载约 1.3GB 的模型（全部来自 ModelScope，国内速度快），不需要 torch，也不需要 NVIDIA 显卡。`funasr-onnx` 声明了 `numpy<=1.26.4`，需要验证它在 numpy 2 下能正常工作，并用 uv 的 override 解除这一限制。
代价：字错率比 PyTorch 版高约 0.5 个百分点（在单个样本的误差范围内）；在较慢的 CPU 上识别会慢一些。

**D-35 / D-38 补记（2026-09-27，R6 实现后）**
- 语言判断：本地转写的子进程先用 faster-whisper 的 `detect_language` 判断语言（有 CUDA 用 GPU，否则用 CPU）。`zh` 走 FunASR（释放 whisper 后在 CPU 上运行），其他语言继续用 whisper。粤语（`yue`）也走 whisper，因为 paraformer-zh 是普通话模型。
- 组件：「安装本地转写组件」一次装好 CUDA 运行库（PyPI）和 FunASR 的 ONNX 模型（约 1.23GB，走 ModelScope 的文件接口，先写到 `.part`，下载完整后再改名，中断的下载不会被当成已安装）。转写前要求两者都已安装。
- 顺带修复：R3 之后，CUDA 运行库一直装到数据目录根部的 `runtime\cuda`，而转写代码从 `.prometheus\runtime\cuda` 查找，新装的机器会一直报「组件未安装」。
- numpy 2：funasr-onnx 0.4.3 的 VAD 把只有 1 个元素的数组当标量用，numpy 2 会报错。用子类把长度数组转成标量，没有改动它的代码。实测软件自身环境（numpy 2.5.3）下字错率与实测环境一致（7.97%）。
- YouTube 人工字幕：yt-dlp 经常拿不到视频的原语言（2026-09-27 检查 4 个视频，3 个为空）。按规格，这种情况照常转写，不猜语言，所以这项功能目前只对标注了语言的视频（例如 TED）生效。


**D-40 导图由简到繁：骨架 + 检索填充 + 逐条校验（用户 2026-09-27）**
问题：用户希望导图越往外越丰富，末端要点可以比主题多写；只在提示词里要求「多写点」，模型会泛泛复述，甚至编造。
决定：两步生成（PLAN 15.4.9）。第二步按主题分批，用检索给每个要点准备原文资料：时间所在章节的全文，加上全篇 BM25 检索到的最相关 2 段。写作规范要求只依据资料、必须带具体信息；程序逐条检查长度、是否只是复述、依据率和具体信息，不合格的带着问题重写一次。用评测脚本在真实报告上量化效果。
原因：检索让模型写的内容有出处；确定性校验把「丰富」变成可以检查的指标；评测让效果可以复查，不靠主观感觉。
代价：每个导图多 3–6 次模型调用（每个主题一次，最多 3 个并发）。

**D-40 补记（2026-09-27，R7c 实测后）**
用用户的模型（claude-opus-4-8）在两篇真实报告上跑了 6 轮评测（`docs/mindmap-eval.md`），按没过的原因改了 5 处，都先写失败测试：
- 根节点只写 ≤ 20 字的 label，不写 summary（规格原本就是 root ≤ 20 字，代码还沿用旧的 40 字上限）；骨架提示词要求 topic 比所属 theme 写得更具体。
- 骨架的那一次重试，改为把上次的 JSON 连同问题交回、只改这些问题。原因：35 个要点的树从头重写，修好一处又在别处超长。
- 时间归属：取「包含这个时刻的最窄章节」，但时刻落在某章最后 2 秒时不算那一章。原因有二：章节首尾会重叠 1 秒而要点常落在章节起点；有的报告开头是跨越多个章节的总览章（罗素一篇的第一章是 02:15–08:40），按「最先匹配」或「最近开始」都会把 02:40 的要点归到总览章，给它错的资料，写出与自己摘要无关的详解（第 6 轮之后在截图里发现）。后端检索和精读页的跳转用同一条规则，前端那份的源码直接注入报告页，两边都有单测。
- 模型常在 JSON 字符串里用不转义的英文双引号；解析失败时按要点编号切出每条详解，不丢整个主题。
第 6 轮两篇都过线：覆盖率 100% / 98%，依据率 0.73 / 0.82，具体信息 100%。

**D-41 中外对照字幕、查词、自定义云端转写的实现选择（2026-09-27，执行 agent 决定，规格见 PLAN 15.4.9）**
- 转写语言：以 asr.json 的 `language` 为准；不是 `zh` / `yue` 就在纠错的同一次调用里要中文翻译。必剪不返回语言，而用户给的英文测试样本是 B 站视频，所以必剪的结果按字幕文字判断（拉丁字母多于汉字即为英文），否则英文视频会被当成中文而没有译文。
- 翻译每批 60 段（纠错是 120 段），因为回复里每段有原文和译文两份。英文样本实测时，有的批次回复里只有纠错、没有译文（同一提示词重放一次又正常），所以：一批回复里一段译文都没有时重问一次；并在参考材料（可长达 1.2 万字）之后、字幕分段之前再写一遍输出格式。改后译文覆盖率 97.9%，其余是「the」「SVG」这类不需要翻译的碎片。译文单独校验：要有汉字、不能与原文相同、字数不能比原文多出 10 个以上（防止把相邻分段的内容并进来）；不合格只丢译文，纠错照常。
- 查词：ECDICT 的 `ecdict.csv`（66MB，GitHub 以 gzip 传输约 23MB；本机实测约 0.17MB/s，约 2 分钟）在第一次查词时下载，流式建成 SQLite，只保留有中文释义的单词。词形还原优先用 ECDICT 自带的 exchange 字段（went → go，并注明「过去式」），查不到再按常见后缀还原。没有找到可靠的国内镜像，下载源只有 GitHub；下载失败时浮窗里仍可以打开在线词典。
- 自定义云端转写：OpenAI 兼容的 `/audio/transcriptions`，`response_format=verbose_json`。超过 20MB 的音频按平均码率估算，每块取上限的 95%，在该段后半部分最后一个静音（ffmpeg silencedetect，-35dB，0.4 秒）的中点切开，`-c copy` 切块，依次上传，再加回每块的起点时间。接口地址、Key、模型名缺一项、返回里没有分段时间、请求失败或超时，都改用本地转写并在条目上提示。

**D-42 界面修改第二轮的选择（用户 2026-09-27 确认，规格见 PLAN 15.4.10）**
- 分类：阅读页原来的分类下拉框看起来像筛选器，实际一选就移动条目；分类被移空后会从列表里隐藏，下拉框里就没有它了，条目也移不回去（预览数据里三篇都因此进了「学习方法」）。改为：分类列表显示全部分类；阅读页用「⋯ → 移到…」；条目列表支持把文章拖到分类上；分类行带「✎ 改名」「🗑 删除」按钮（用户要求删除按钮要看得见）。删除非空分类时，条目移到「未分类」。合并不放到界面上。「重新生成」不再重新归类，人工归类以人为准。
- 设置：Key 输入框不再填掩码（参考 ModelGate「留空保持原密钥」）；常用供应商只收官方平台（参考 CC Switch 的预设，但不收返利中转）；思考强度开放 xhigh / max。
- 模型参数：自定义模型原来只写了 id 和能否看图，Pi 于是按默认的 128k 上下文、16k 输出、预算式思考运行。改为按随包 Pi 的模型目录（pi-ai 的 providers/data）补齐参数，目录里没有的用 models.dev 快照中的上下文和输出上限。原因：这是精读在长视频上丢细节的直接原因之一（卡巴拉的转写约 8 万 token，会触发 Pi 的自动压缩）。
- 字幕：Whisper 和必剪的分段太碎（卡巴拉的中位数 1.3 秒，英文样本 0.7 秒），逐行阅读很累。改为合并成 10–15 秒一段，在纠错和翻译之前合并，这样译文按整句翻译。代价：导出的 SRT 每条 10–15 秒，给播放器当字幕会偏长。
- 精读加宽：模板固定 860px，改为随窗口变宽，最宽 1280px；隐藏报告自带的左侧目录，由工具栏的「目录」按钮代替。
- 查词：用 ECDICT 自带的英文释义（WordNet 来源），离线、不花 token；剑桥、牛津没有免费接口，只提供在浏览器打开的按钮。

**D-43 R7d 的实现选择（2026-09-27/28，执行 agent 与两个子 agent 决定，规格见 PLAN 15.4.10）**
- **拖拽用指针事件，不用 HTML5 拖放。** 实测 Chromium 不会从 `<button>` 上开始 HTML5 拖放（文章卡片原来是按钮）；而且 Tauri 2 在 Windows 上默认接管窗口的拖放（为了拖文件进窗口），网页里的 HTML5 拖放会失效。改成：按下卡片移动超过 6px 后出现跟随鼠标的小标签，松开时看鼠标下面是哪个分类；Esc 取消。文章卡片改为 `div role="button"`，键盘 Enter / 空格照样打开。
- **补全标签和摘要**：复用「重新生成导图」的机制，只重跑 classify + publish，条目始终是 done；归类阶段只在条目第一次完成时定分类，所以这里只会更新标签和摘要。缓存里的报告副本清理后，从知识库的精读.html 读取。失败不另外提示，条目仍然没有标签，按钮留着可以再点。
- **模型参数**（设置子 agent）：
  - 同一个模型 id 在 Pi 自带目录里有多条时，优先用与配置协议相同的 API 那一条，其次是接口地址所属站点的那一条，最后按文件名取第一条；`compat` 只从协议相同的条目复制。
  - models.dev 快照 `backend/src/prometheus/llm/model-limits.json`（2289 个模型，由 `scripts/update-model-limits.py` 从 models.dev 生成）；同一模型在多家的上下文和输出上限不同时，取多数一致的一组，平局取较小的。
  - DeepSeek / 智谱的思考档位按实际运行的 models.json 判断，其次是 Pi 自己的目录。选了模型不支持的档位时，显示并保存成 Pi 实际会用的档位（向上取最近的，没有就向下），例如 deepseek-flash 和 kimi-k3 上「中」会变成「高」。
  - 「高级」里的上下文和最大输出只在用户改动时保存；换模型或换供应商后清空，重新按目录填。
  - **后端每次启动时按当前配置重写一次自定义供应商**（执行 agent 补）。否则已安装的版本要在设置里点一次「保存」才会生效，在那之前仍按 128k 上下文、16k 输出运行。
- **Key 输入框留空 = 保留原 Key**（模型配置与自定义转写都一样），代价是不能在页面上清空 Key。
- **获取模型列表**：接口地址已经以 `/v1` 结尾时，不再重试 `/v1/models`，避免对中转多发一次请求。403 的正文提到 Cloudflare，或者响应头 `server: cloudflare` 且正文不是 JSON，判为「请求被 Cloudflare 拦截」；JSON 格式的 403 仍判为「Key 无效或无权限」。
- **常用供应商**（2026-09-27 按各平台官方文档核对，不含返利链接，单测会拒绝 `aff=`、`invite`、`utm_`、`ref=`、`/i/` 这类链接）：
  - Kimi：`https://api.moonshot.cn/v1`，OpenAI 协议，kimi-k3。
  - 通义千问：`https://dashscope.aliyuncs.com/compatible-mode/v1`，OpenAI 协议，qwen3.8-max。
  - MiniMax：`https://api.minimax.cn/anthropic`，Anthropic 协议，MiniMax-M3。
  - 豆包（火山方舟）：`https://ark.cn-beijing.volces.com/api/v3`，OpenAI 协议，doubao-seed-2-1-pro-260628。
  - 硅基流动：`https://api.siliconflow.cn/v1`，OpenAI 协议，deepseek-ai/DeepSeek-V4-Flash。
  - OpenRouter：`https://openrouter.ai/api/v1`，OpenAI 协议，anthropic/claude-sonnet-5。
  - Anthropic：`https://api.anthropic.com`，Anthropic 协议，claude-sonnet-5。没有用官方推荐的 claude-opus-5-5，因为随包的 Pi（模型目录日期 2026-09-04）还不认识它，会发出旧式的思考参数，而 4.6 之后的模型已经不接受。手动填 opus-5-5 也会遇到同样的问题，需要升级 Pi。
  - OpenAI：`https://api.openai.com/v1`，OpenAI 协议，gpt-6-astra。没有用 gpt-6-sol，因为按 OpenAI 的说明，它在 Chat Completions 接口上只有 reasoning_effort 为 none 时才能调用函数，而本项目的 OpenAI 协议走的正是 Chat Completions。
- **字幕纠错分批**：原来固定每批 120 段（翻译 60 段）。合并成 10–15 秒的段落后，每段 50–150 字，按段数分批会让一次请求变得很大，所以改为「最多 120 段且约 2500 字」（翻译为最多 60 段且约 1250 字），与 15.4.6「每次最多 120 段（约 2500 字）」的本意一致。
- **字幕合并的实测**（预览数据，只读，函数 `subtitle/paragraphs.group_segments`）：卡巴拉 104 分钟，3895 段变为 453 段，中位数 14.0 秒，98% 在 10–15 秒；英文样本 19 分钟，872 段变为 94 段，中位数 11.7 秒，88% 在 10–15 秒；两篇的文字都一字不差。
- **英英释义**：最多 3 条，优先选与第一条中文释义词性相同的；旧词库（没有 `definition` 列）在查词结果里标 `needs_update`，浮窗提示更新，更新前照常显示中文释义。
- **报告自带目录隐藏以后**，原来点目录链接的端到端测试改为：往正文插一个指向第 3 章的链接去点，验证页内跳转仍在报告内（防白页的保护不变）。
