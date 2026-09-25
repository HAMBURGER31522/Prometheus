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

**D-10 转写：本地 + 云端**
本地 faster-whisper large-v3-turbo（默认，本机 RTX 4060 8GB），CUDA 运行库和模型在首次启用时下载到数据目录；保留 VRA 已实现的百炼云端（paraformer / Fun-ASR）。不使用平台自带字幕，因为 VRA 的质量是在带时间戳的 ASR 转写上调出来的。

**D-11 YouTube 需要 cookies**
2026-09-25 实测：经本机代理（7897）访问 YouTube，不带 cookies 会返回 "Sign in to confirm you're not a bot"。决定：设置里提供「YouTube cookies.txt」选项。yt-dlp 的 JS 运行时复用随包分发的 Node。B 站只支持公开视频，不做登录。

**D-12 分类只有一层，由模型自动归入**
模型优先从已有分类里选，都不合适时新建；用户可以改名、移动、合并。三个内容页签共用同一套分类和标题，标题显示为「报告标题 + 小字原标题 / UP 主」。

**D-13 数据按条目存放**
`items/<ID>/{report,mindmap,subtitle,work}/`：删除或重新生成一个视频时只动一个文件夹；子文件夹名直接说明内容类型。

**D-14 不做的东西**
问答 / RAG、标签网络、B 站登录、平台字幕、合集或播放列表批量导入、本地文件导入、速览模式、PNG 长图、费用显示、深色模式、自动更新、多级分类。

**D-15 API Key 明文保存在数据目录**
和 VRA 的 `.env` 做法一致，Key 放在仓库之外的数据目录里。这是已知局限，没有接入 Windows DPAPI。
