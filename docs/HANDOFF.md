# 交接说明（2026-09-30，R7g 合并之后）

给新开的会话用：读完这份，再按 `AGENTS.md` 的「开工前必读」读 `docs/PLAN.md` 和 `docs/DECISIONS.md`，就能接着做。这份文件是某一时刻的快照，以 PLAN 的进度记录（§15.6）和 git 历史为准。

## 1. 现在做到哪了

- R1–R7g 全部完成并合并到 `main`，已推送。每个里程碑的 Done When 结果都记在 `docs/PLAN.md` §15.6。R7d–R7g 的注意事项见第 8–12 节。
- **R7h（按需生成）进行中，暂停在控制台界面这一步，见第 13 节**；做完 R7h 再做 R8。
- 按 PLAN §15.5，下一个里程碑是 **R8**：打包（安装包 ≤ 300MB，`PROMETHEUS_FORBID_DEV_PATHS=1` 冒烟）、README 全面重写、完整真实验收（E3 用 BV1yPb46xExH、E4 取消、E9 CI），最后请用户试用安装版，给出 E7 界面观感的最终判定。R8 还要带上第 9 节、第 11 节记下的几件事（耗时和 token 表、控制台的用时提示、随包 npm）。
- 第 5 节是 R7d 之前的界面修改流程，已经做完；以后有新的界面意见，照同样的流程走。

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

> 继续 Prometheus 项目（F:\project\Prometheus）。先读 docs/HANDOFF.md，再按 AGENTS.md 读 docs/PLAN.md 和 docs/DECISIONS.md。R1–R7f 已完成，下一步是 R8：先把 R8 的规格和 HANDOFF 第 9、11 节记下的事对一遍，有缺口先问我，确认后再开分支按红绿做。预览用 HANDOFF 第 2 节的方法启动。

## 8. R7d 进行中的注意事项（2026-09-28）

分支 `r7d-ui-review`。规格 PLAN 15.4.10 / E13，实现选择 DECISIONS D-42、D-43。E13 ① ② 的命令全部为 0，截图在 `docs/screenshots/r7d/`，等用户看过后记入 acceptance.md，再合并。

- **模型参数**：后端每次启动都会按当前配置重写 models.json 里的自定义供应商（上下文、最大输出、思考方式来自随包 Pi 的模型目录）。改设置时也会重写。验证方法：看 `<数据目录>/.prometheus/config/pi/models.json` 里 custom 模型有没有 `contextWindow`。
- **Key 片段**：设置页 Key 框的灰字会显示末 4 位。截图脚本 `app/scripts/screenshots-r7d.mjs` 在截图前会把它遮成圆点；以后任何截图、日志、提交里都不能出现 Key 片段。
- **端到端测试**：多个 agent 并行时，端到端测试用 `tmp/e2e.lock` 目录锁排队（共用 8765 端口）。列表切换有过渡动画，用鼠标手动拖拽前先 `settle(page)`（`app/e2e/helpers.ts`）等动画结束。
- **拖拽**：卡片拖拽是自己用指针事件做的（不是 HTML5 拖放，原因见 D-43）。按下卡片会阻止选字，拖动中整页不可选中。
- **预览数据（acceptance-output/r7-data）已被 R7d 的新后端处理过**：字幕合并成段落（细分段另存 segments.fine.json）、词库更新为带英英释义的版本、settings.json 迁移为多配置格式、当前配置的思考强度按用户要求改为「中」、罗素和卡巴拉已拖回「战争伦理」「神秘学」。改动前的备份在 `tmp/r7d/backup-preview/`（不入库）。
- **重启预览后端**：先确认 8766 的进程（父进程是 `.venv\Scripts\python.exe -m prometheus.server --port 8766`），`taskkill /PID <父进程> /T /F`，再用第 2 节的命令启动。不要碰 pid 22228。
- **待用户决定**：导入失败写明原因（规格草案在 PLAN 15.4.10，未提交）；设置页眼睛图标是否显示完整 Key；DeepSeek / 智谱预设要不要也加「获取 API Key」链接；R7e 的四个问题（补充说明框、写作方式、审校默认开、预算）。

## 9. R7e 进行中的注意事项（2026-09-28）

分支 `r7e-report-depth`。规格 PLAN 15.4.11 / E14（用户确认过三轮，后来又加了配图和看大图），实现选择 DECISIONS D-44。R7d 已合并（上一节「待用户决定」的几项都已经定了、做完了）。

- **完整精读的流水线**（`backend/src/prometheus/report/full.py`，阶段 `keypoints`、`plan`、`report`）：要点账本（每 5 分钟一次一次性调用）→ 规划（一次 Pi 运行，不合格重做一次）→ 每章一次 Pi 运行（规则全文附在提示词里，省掉读文件的回合）→ 程序逐章检查（漏写、空洞、照抄、隐藏的每点篇幅检查、有信息的候选帧没用上），最多退回 2 轮 → 零基础读者审校（追问和要图，退回 1 次，丢了要点就撤回）→ 程序拼装 → `coverage.json`。开了配图时，每章写之前先有一次看图调用给候选帧标类型和内容（`figures/notes.py`）。
- **中间结果按输入的摘要保存**：`keypoints.json`、`plan.json` + `plan.meta.json`、`chapters/ch-NN.json`、`chapters/ch-NN.frames.json`。失败后「重试」只重做缺的部分；成功后清理只留 `coverage.json`。
- **不写字数**：规则、规划和反馈里都不出现字数（用户要求，理由见 D-44）。隐藏门槛在 `chapter_checks.py` 的 `THIN_BASE`、`THIN_RATIO`，用英文和卡巴拉校准为 24 和 1.0（D-44）；罗素只做复核，不参与校准。
- **规则面向未知视频**：depth.md 的示例用手冲咖啡，`test_depth_rules.py` 禁止出现评测样本的主题。
- **真实运行**（花钱，先问用户）：在 bash 里要先设好工具链变量，否则找不到 node / Pi / ffmpeg：
  `T=E:/tools/Prometheus-Desktop; export PROMETHEUS_TOOLS=$T PROMETHEUS_NODE=$T/node/node.exe PROMETHEUS_PI=$T/pi/node_modules/.bin/pi.cmd PROMETHEUS_FFMPEG=$T/ffmpeg/bin PYTHONUTF8=1`，
  然后 `uv run python scripts/report-eval/rewrite.py acceptance-output/r7-data <条目ID> [--frames]`。`--frames` 会给条目打开配图、重新下载视频抽帧，成功后清理；没有标签的条目会顺带跑一次分类补标签。跑完在日志末尾打印这次花了多少（Pi 用量是实数，一次性调用按字数估算）。
- **评测**：`uv run python scripts/report-eval/run.py acceptance-output/r7-data --items <ID> --label <名字> [--report <ID>=<HTML>]`，结果在 `acceptance-output/report-eval/`（不入库）。旧报告备份在 `old/`，第 1 层（只加规则）的英文报告在 `l1/`。
- **费用**：中转站没有提示缓存，Agent 每一轮都重发全部上下文。预算原定 60–80 美元，用户后来同意在 justwoker 上跑完英文、罗素和第四轮（15.4.11a）。按官方价估算，Claude 累计约 149 美元（含最后一轮评测约 3.2 美元）；gpt-6-luna 走订阅额度，不按 token 计。
- **补写已完成的报告**：`rewrite.py <数据目录> <条目ID> --patch`（15.4.11a-5）需要保留的 `keypoints.json`。它读的是已发布的精读，再跑一次就是在补过的版本上再补。卡巴拉和罗素补写前的页面在 `acceptance-output/report-eval/before-patch/`。每章的补写记录（`patch/ch-NN.json`）保留核实前的稿子，改了链接核实规则后重跑不再调用模型。
- **字幕核对**（用户 2026-09-29 问过有没有缺）：卡巴拉、罗素纠错后的文字和逐段识别结果一字不差。英文只差一个词：10–11 分钟附近识别出的「Kimike 3」被纠成了「Kimi K2」，讲者说的更可能是「Kimi K3」，疑似纠错改错了。没有缺段。
- **R8 要做的两件事**（用户 2026-09-29）：README 放一张「视频时长 → 用时」表（`docs/report-eval.md`「耗时」一节，所有跑过的都放），加上每个模型、每个思考档位的 token 区间（同一视频不同模型的 token 数在同一数量级，但会差 1.5–3 倍，有没有提示缓存对费用影响更大），再各举 gpt-6-luna 和 claude-opus-4-8 一个例子。控制台的链接输入框下面提示按当前模型估计的用时和费用。
- **用户的工作习惯**：需要用户定的事用弹窗问（AskUserQuestion），附推荐项；改规格要先问、得到同意再写进 PLAN；回答要说清楚改了什么、为什么。
- **README 要用的耗时数据**（用户 2026-09-29 要求）：`docs/report-eval.md` 的「耗时」一节，gpt-6-luna（ChatGPT 订阅经本机 CPA）在「最高」「超高」下各视频长度的实测时间。R8 重写 README 时写进去。
- **当前模型**：预览数据的配置已切回 justwoker 中转（claude-opus-4-8，「中」）；CPA 的 gpt-6-luna 配置保留但不用（用户 2026-09-29：先别用 Codex 订阅）。模型目录已从 pi.dev 更新过。

## 10. R7f 真实跑通的两份配置（2026-09-30，截图 `docs/screenshots/r7f/10-…`、`11-…`）

- **Codex CLI + anyrouter**（`anyrouter · Codex CLI`）：Agent 选 Codex CLI，接入方式「接口 + Key」，平台选「自定义」，接口地址 `https://anyrouter.top/v1`，协议 OpenAI 兼容，模型 `gpt-6-astra`，模型能看图打开，思考强度「超高」。「高级」按模型目录预填 272000 / 128000；anyrouter 自己说它的 gpt-6-astra 是 1M，想用满就把上下文窗口改成 1000000。要求 Codex 0.153 以上（应用自己的是 0.159.1）。整条流水线（完整精读、字幕、导图、归类）跑通，用时 38.5 分钟；中途 anyrouter 多次限流，都由重试接住。
- **Claude Code + justwoker**（`justwoker · Claude Code`）：Agent 选 Claude Code，接口地址 `https://api.justwoker.icu/v1`（应用会去掉末尾的 /v1 再交给 Claude Code），协议 Anthropic，模型 `claude-opus-4-8[1m]`（也可以只写 `claude-opus-4-8`，目录里是 1M 的模型会自动加 `[1m]`），思考强度「中」。整条流水线跑通，用时 25 分钟，截图 5 张。「超高」在 justwoker 上每章都被网关 100 秒超时（524）切断。2026-09-30 之后 justwoker 返回 403，用户说它坏了。
- anyrouter 的 Claude 模型当时用不了：claude-opus-5-5 被拒（「claude 模型供应难以保证」），claude-sonnet-5 要带 `[1m]`，带上后规划阶段一直 429。
- runanytime（`https://runanytime.hxi.me/v1`，Key 在本地设置里）：`gpt-6-astra` 和 `gpt-5.6-sol` 都能答；gpt-6-astra 是标准的 272k 上下文，没带上限时两章修改被拒（context_length_exceeded），已修（Codex 现在按上限提前压缩）。

## 11. R7f 之后（2026-09-30，已合并）

规格 PLAN 15.4.13 / E15，实现选择 DECISIONS D-45。每个配置可以选 Agent：Pi、Codex CLI、Claude Code。

- **私有副本**：Codex CLI 和 Claude Code 装在 `E:\tools\Prometheus-Desktop\agents\`（codex、claude 两个 npm 目录），配置目录在 `<数据目录>/.prometheus/config/codex`、`…/claude`。子进程从干净的环境变量启动（去掉继承来的 `ANTHROPIC_*`、`CLAUDE*`、`CODEX_*`、`OPENAI_*`），用户自己的 Claude Code、Codex、superpowers 都碰不到。
- **文件保护**：三个 Agent 都在 Windows 低完整性级别下运行（`backend/src/prometheus/agents/contain.py`），只能写这次运行的工作目录和自己的配置目录。开发测试用假模型接口 `agents/fake_api.py`（提示词里的 `DELETE:`、`OUTSIDE:`、`WRITE:`、`HTML:` 让它去做对应的事）。
- **测试**：`uv run pytest backend/tests -q -m agents` 会启动真实的 CLI 副本（对假接口，不花钱），默认的 `-m "not live"` 会跳过它们，要单独跑。
- **更新**：设置页「检查更新」。更新先装到 `E:\tools\Prometheus-Desktop\.staging`，自检（Pi 还要跑 VRA 的 PiRunner）通过才替换旧版本。现在用的是系统里的 npm；R8 打包时要把 npm 一起带上。
- **当前配置**：预览数据的当前配置是 `chatgpt-codex`（「ChatGPT · Codex CLI（官方登录）」，gpt-6.1-sol，「高」），走用户的 ChatGPT 订阅。另外两份跑通过的配置见第 10 节。justwoker 返回 403，已坏。
- **罗素条目现在的内容**：精读是 Claude Code（justwoker，claude-opus-4-8[1m]「中」）那次的，字幕纠错和导图是官方登录那次的。R7e 版本的精读在 `acceptance-output/report-eval/r7f/russell-before-r7f.html`，Codex（anyrouter）那篇在同一目录。
- **还没验证的**：Codex、Claude Code 输出到上限被截断时的表现；Codex 在中转上自动压缩上下文的表现（Russell 没用到）。
- **不稳定的单测**：8 次完整后端测试里有 1 次一个测试失败，重跑就过，名字没记下。以后遇到用 `-rf` 跑，把名字记下来再查。
- **Claude Code 那篇有 1 条补充说明与视频矛盾**（E15 ④），用户决定如实记录、照样验收。之后加的三条规则（谁说的就是谁说的、每章都跑编者观点、PowerShell 下的 Python 写法）见 PLAN 15.4.13 末尾，还没在真实视频上跑过。

## 12. R7g 之后（2026-09-30，已合并）

规格 PLAN 15.4.14 / E16，实现选择 DECISIONS D-46。完整精读现在：每章两位读者（问题照问）、读者和判定低一档思考、补充说明三步写透、收尾检查（没画的图、没补的背景说明、只有一两句的补充、处理用语、免责句过密）只退回一次、拒答或空回复会重试或标明、同时写 5 章（限流降到 3、再降到 1）、Pi 的压缩预留是窗口的三成。

- **没验证的**：恢复照问之后没有再实跑；E14 评分没做。英文的改前改后在 `acceptance-output/report-eval/r7g/`（不入库）。
- **接口**：agentrouter 只让 Claude Code / Codex 用，规划那种长对话 22 分钟无响应，两个 Key 的额度池都用光了；runanytime 的 sonnet 实际上限约 10 万（带 [1m] 也一样），配置里「高级」填了 10 万，这个题材（战争、杀人）常被上游拒答，也常断流。不要向 venlacy、justwoker 发探测请求。
- **预览数据现在的样子**：罗素条目显示的是 sonnet 改前那一版（runanytime，14565 字），英文条目显示的是 sonnet 改后那一版（19093 字）；当前配置是 chatgpt-codex（官方登录）。跑改前基线用过的 git worktree 已删除，要再跑就 `git worktree add ../prometheus-main main`，用 `PYTHONPATH` 指向它的 backend/src。
- **查到但没做的**：已有测试 `test_a_viewpoint_pass_that_loses_a_point_is_undone` 的条件永远不成立（假 Pi 在编者观点那一步收到的是第一次的提示词），测的是空；Claude Code 和 Codex 的事件要等运行结束才写进日志，运行中看不到进度（Pi 是边跑边写）；「获取上下文长度」按钮大多数接口拿不到，只能当可选项；Pi 压缩在实际运行里为什么没触发还没确诊，下次实跑失败时先把章节工作区整个复制出来再重试。
- **用户的新想法（待写规格）**：精读、字幕、导图可以分开选，不是每个视频都要三样。事实：字幕纠错有精读时拿它当参考（人名、术语更准），没有也能纠（R6b 在不给报告的条件下测过：whisper 8.17% → 7.01%，必剪 6.17% → 5.86%）；导图现在从精读的章节结构生成，不写精读就要改成从转写或要点账本生成。

## 13. R7h 进行中（2026-09-30 暂停）：按需生成

分支 `r7h-on-demand`（未推送）。规格 PLAN 15.4.15 / E17，用户已确认。做到：规格（e7c6e23）；三个圆圈的联动逻辑 `app/src/features/console/outputs.ts`（红 34452c3 → 绿 61ed34c：勾导图带上精读、取消精读带走导图、至少留一样、localStorage 记住上次选择，第一次三个都勾）。

**已查清的事实**
- 流水线步骤顺序在 `backend/src/prometheus/tasks/runner.py` 的 `STAGES`：resolve、download、transcribe、transcript、frames、keypoints、plan、report、finalize、subtitle_fix、mindmap、classify、publish。`run_item(ctx, impls, stages=...)` 可以只跑其中一部分。
- 字幕纠错 `subtitle/fix.py` 的 `_reference()`：有精读就拿它当参考，没有就返回空串照样纠（R6b 就是在不给报告的条件下验收的）。
- 导图 `mindmap/generate.py` 读精读 HTML 的章节结构，所以导图必须和精读绑在一起。
- 归类 `tasks/stages.py` 的 `classify` 读已发布精读的标题、导语和各章标题；没有精读时要改成视频标题（`source_title`）加转写开头。
- 提交接口 `api/items.py` 的 `create_item` 现在只收 `url`、`figures`；前端 `api.addItem(url, figures)` 只有控制台一个调用者。

**接下来按这个顺序做**（每步先写失败的测试、单独提交 `(red)`，再写实现）
1. ~~控制台界面~~（完成：红 2465dd5 → 绿 613abfb，截图 `docs/screenshots/r7h/`，截图脚本 `app/scripts/screenshots-r7h.mjs` 只点不提交）。原来的说明：半成品补丁在 `tmp/r7h-console-wip.patch`（`git apply` 即可），还缺：`api.ts` 加 `export type ReportDepth = "full" | "standard"`，`addItem(url, { figures, outputs, depth })`；`console.css` 加三个圆圈（胶囊按钮，`aria-pressed`，按下时实心圆点加强调色）、两格的分段切换（`.segmented.two .thumb` 宽度按 2 格算）、第二行的 `.importer-options`（没勾精读时变灰）。排法：第一行链接框、三个圆圈、「开始」；第二行「精读：标准 / 完整」和「配图」。颜色只能用 tokens.css，过渡曲线只能用 motion.css（`lint:design` 会查）。**截图给用户看，确认后再做后端。**
2. 后端提交参数：`items` 表加列保存 outputs 和 depth（旧条目视为三样都要、按设置的档位）；检查至少一样、导图必须带精读、depth 只取 standard / full。
3. 流水线按条目的 outputs 选步骤；精读的档位用条目自己的 depth，而不是设置里的。
4. 没有精读时：归类用视频标题加转写开头；发布只写有的文件，文件夹名用视频标题；字幕纠错不带参考。
5. 阅读页：没生成的标签页显示「没有生成」和「现在生成」；接口复用 regenerate 的思路，只跑缺的步骤，不重新转写；补精读时导图一起补，旁边可选「标准 / 完整」和「配图」（默认沿用设置，开了配图只重新下载视频画面，补完后视频和截图照样清掉）；没纠错的字幕页显示原文，顶上「字幕没有纠错」和「现在生成」（只跑纠错）。用户 2026-09-30 选定，PLAN 15.4.15 已改。
6. 前端单测、端到端测试（三个圆圈联动、记住选择、切换变灰、提交带参数、「没有生成」和「现在生成」），截图请用户看，结论记进 acceptance.md。
7. live：当前配置（Codex 官方登录，走订阅），用户 2026-09-30 定用 BV1EJ4m1t7Zs（不删罗素）：① 只勾字幕；② 阅读页「现在生成」按「标准」补精读和导图；③ 删掉重交，只勾精读和导图（标准）；每次记下用时。
8. Done When 逐条跑、写进 PLAN 进度记录，合并推送（推送前跑 `tmp/key_scan_all.py` 查 Key）。
