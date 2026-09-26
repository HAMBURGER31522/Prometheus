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
