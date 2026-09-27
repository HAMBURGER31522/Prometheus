# 交接说明（2026-09-27，R7c 合并之后）

给新开的会话用：读完这份，再按 `AGENTS.md` 的「开工前必读」读 `docs/PLAN.md` 和 `docs/DECISIONS.md`，就能接着做。这份文件是某一时刻的快照，以 PLAN 的进度记录（§15.6）和 git 历史为准。

## 1. 现在做到哪了

- R1–R7c 全部完成并合并到 `main`（R7c 的合并 commit 是 b4c029c，`main` 最新是 9710974，已推送）。每个里程碑的 Done When 结果都记在 `docs/PLAN.md` §15.6。
- 按 PLAN §15.5，下一个里程碑是 **R8**：打包（安装包 ≤ 300MB，`PROMETHEUS_FORBID_DEV_PATHS=1` 冒烟）、README 全面重写、完整真实验收（E3 用 BV1yPb46xExH、E4 取消、E9 CI），最后请用户试用安装版，给出 E7 界面观感的最终判定。
- **但用户在 R8 之前有新的界面修改意见。** 处理方式见第 5 节：先写规格、用户确认，再开分支按红绿做。

## 2. 界面预览（给用户看、自己截图都用这个）

两个进程都要在：

| 进程 | 端口 | 怎么启动 |
|---|---|---|
| Vite 开发服务器 | 1420 | `npm --prefix app run dev`（只监听 127.0.0.1） |
| 真实后端（真实数据） | 8766 | 见下面的命令 |

后端启动命令（Git Bash，先 `source tmp/_env.sh`）：

```
PROMETHEUS_TEST_DATA_DIR="$(pwd -W)/acceptance-output/r7-data" PYTHONUTF8=1 .venv/Scripts/python.exe -m prometheus.server --port 8766 --token shots
```

预览地址：`http://localhost:1420/?port=8766&token=shots`

- `acceptance-output/r7-data`（不入库）里有 3 个真实条目：罗素（8 分钟）、魔法卡巴拉（104 分钟，导图很大，默认折叠）、英文样本「我如何用 AI 高效学习」（B 站 BV11i8J65EDp，19 分钟，中外对照字幕）。离线词典已经下载到这个数据目录里。
- 这个数据目录的设置里存着用户的模型配置（justwoker 中转，Anthropic 协议，claude-opus-4-8）。**Key 只在这个本地文件里，不要抄进任何入库的文件、提交信息或命令输出。**
- 截图脚本（在 `app/` 目录下运行，否则找不到 Playwright）：`node scripts/screenshots.mjs <预览地址> <输出目录>`（所有页面）、`node scripts/screenshots-r7c.mjs <预览地址> <输出目录> "我如何用 AI 高效学习"`（R7c 新功能）。
- **Claude Code 会在内存紧张时关掉后台进程**（本机 16GB，常被其他软件占到只剩 2GB 左右），8766 的后端就被关过一次。被关后不要自己重启，先告诉用户；用户也可以在自己的 PowerShell 里运行后端，那样不会被回收。
- **不要碰 pid 22228 的 python**，那是用户装的安装版。

## 3. 环境与命令

`tmp/` 不入库。Git Bash 用的环境脚本 `tmp/_env.sh` 是 `E:\tools\Prometheus-Desktop\env.ps1` 的镜像，内容如下（丢了就按这个重建）：

```
# bash mirror of E:\tools\Prometheus-Desktop\env.ps1 (session only)
T='E:\tools\Prometheus-Desktop'
export PROMETHEUS_TOOLS="$T"
export PROMETHEUS_PYTHON="$T\python\cpython-3.12.14-windows-x86_64-none\python.exe"
export PROMETHEUS_NODE="$T\node\node.exe"
export PROMETHEUS_FFMPEG="$T\ffmpeg\bin"
export UV_PYTHON="$PROMETHEUS_PYTHON" UV_PYTHON_DOWNLOADS=never UV_CACHE_DIR='F:\project\Prometheus\.cache\uv'
export HF_HOME="$T\models"
export PATH="/e/tools/Prometheus-Desktop/node:/e/tools/Prometheus-Desktop/ffmpeg/bin:/e/tools/uv:$PATH"
export PYTHONUTF8=1
export PROMETHEUS_PI='E:\tools\Prometheus-Desktop\pi\node_modules\.bin\pi.cmd'
export PLAYWRIGHT_BROWSERS_PATH='E:\tools\playwright-browsers'
```

常用命令（R7c 结束时全部为 0）：

| 检查 | 命令 | R7c 时的结果 |
|---|---|---|
| 后端测试 | `.venv/Scripts/python.exe -m pytest backend/tests -q -m "not live"` | 318 passed |
| 后端 lint | `.venv/Scripts/ruff.exe check backend scripts` | 0 |
| 前端单测 | `npm --prefix app run test` | 34 passed |
| 设计 lint | `npm --prefix app run lint:design` | 0（颜色只能来自 tokens.css，曲线只能来自 motion.css） |
| 类型检查 | 在 `app/` 下 `npx tsc --noEmit` | 0 |
| 端到端 | `npm --prefix app run e2e` | 18 passed（自动起假流水线后端 8765，复用已开的 Vite） |
| 正式验收 | PowerShell：`. E:\tools\Prometheus-Desktop\env.ps1` 后 `verify.ps1` 与上面各项，读退出码 | 全 0 |

## 4. 规矩（细则见 AGENTS.md 和全局 CLAUDE.md）

- 规格先行：改变行为的需求，先写进 `docs/PLAN.md`（Goal / 规则 / Done When），**用户确认后**才动代码。规格部分只在用户同意后修改。
- 红绿：先写测试，看它**因断言**失败（不是导入错误、超时）；单独提交，提交信息末尾加 `(red)`；再写最少的实现提交。桩函数返回「合法但错误」的值。反向断言（「不应出现」）要配一个正向断言，免得桩直接让它通过。
- 每个里程碑一个分支，`merge --no-ff` 进 `main`，推送 `main` 和分支，把合并 commit 补进 PLAN §15.6。
- **不要对 venlacy / justwoker 中转发探测请求**（会封号），只发真实工作的请求；开发测试一律用假模型。会产生费用的真实调用只在里程碑需要时做。
- **不要在 bash heredoc、sed、`python -c` 里写反斜杠**（Windows 路径、正则），会被吃掉或变成奇怪字符；这类内容用 Write / Edit 工具或单独的 .py 文件写。
- 文件读写显式 `encoding="utf-8"`；`.ps1` 只写 ASCII。
- 回答用户用中文、用简单的词；产品上的选择用提问让用户选，不要替用户定。

## 5. 接下来：用户的界面修改意见

建议流程：

1. 让用户把意见说完（可以截图）。每条意见先弄清楚：现在是什么样、希望变成什么样、怎么算做完。有多种做法的，列 2–4 个选项让用户选。
2. 写进 `docs/PLAN.md`：新增 §15.4.10（界面修改，第二轮），并在 §15.5 里程碑表加一行（建议分支名 `r7d-ui-review`，Done When 用新编号 E13，含端到端测试和「停下来请用户看截图」）。给用户看改了哪些规格，确认后再开工。
3. 在 `r7d-ui-review` 分支上按红绿做：能用单测或端到端测试表达的都先写测试；纯视觉的（间距、颜色、动效）写不出有意义的测试，就用截图让用户判定，并在 `docs/acceptance.md` 记下结论。
4. 截图放 `docs/screenshots/r7d/`。

相关代码位置（按功能分文件夹）：

| 界面 | 前端 | 样式 |
|---|---|---|
| 侧栏、页签、阅读栏、放大缩小 | `app/src/shared/`（Sidebar、LibraryPage、ReaderTools、nav） | `app/src/shared/base.css` |
| 控制台 | `app/src/features/console/` | 同目录 css |
| 精读 | `app/src/features/report/`（ReportView；注入报告页的主题和脚本在 theme.ts） | `report.css`、theme.ts |
| 导图 | `app/src/features/mindmap/`（layout.ts 布局与卡片尺寸，MindmapView） | `mindmap.css` |
| 字幕、查词 | `app/src/features/subtitle/`（SubtitleView、Lookup、words.ts） | `subtitle.css` |
| 设置 | `app/src/features/settings/`（SettingsPage、ModelProfiles、SecretInput） | `settings.css` |
| 颜色与动效 | `app/src/shared/tokens.css`、`motion.css` | — |

## 6. 已知情况与坑

- E12 ③ 规格写的是「英文 YouTube 样本」，按用户意见改用了 B 站英文视频，记录在 `docs/acceptance.md`，规格正文没改。
- 英文样本没有配图：`POST /api/items` 不带 `figures` 时默认不配图，那次是直接调接口提交的。界面里提交会带上设置里的默认值。
- 旧条目（罗素、魔法卡巴拉）的 `subtitle_status` 为空，字幕页不显示「已纠错」标记。它们是字幕纠错功能加入之前生成的。
- 中转站偶尔超时（「Request timed out」），导图等阶段会失败，重试就好；这是外部问题，不是代码缺陷。
- 「在精读中查看」用的章节规则写在 `app/src/features/report/chapters.ts`，源码在运行时注入报告页（`Function.toString`）。生产构建已检查过函数能独立运行，但还没在安装版里实际点过，R8 冒烟时要试。
- 端到端测试共用一个假后端：`content.spec.ts` 会新建一个英文条目，而列表按完成时间倒序，之后的测试文件里「第一个条目」可能变成它。现有测试不受影响，新写的测试不要假设第一个条目是中文的。
- Git Bash 里 `echo "$json" | python` 会弄坏 JSON 里的转义引号。要解析接口返回，先 `curl -o` 存成文件再读。
- Vite 只监听 127.0.0.1；Playwright 会复用已经在 1420 运行的 Vite。
- `docs/acceptance.md` 第 78 行有一个 2026-09-26 留下的截断 key 前缀（`sk-eLFM…`），不是完整的 key。以后不要再写任何 key 片段。

## 7. 新窗口的开场白（复制给新会话）

> 继续 Prometheus 项目（F:\project\Prometheus）。先读 docs/HANDOFF.md，再按 AGENTS.md 读 docs/PLAN.md 和 docs/DECISIONS.md。R1–R7c 已完成，下一步本来是 R8，但我先有一些界面修改意见：先听我说完，按 HANDOFF 第 5 节把意见写成规格给我确认，确认后再开分支按红绿做。预览用 HANDOFF 第 2 节的方法启动。
