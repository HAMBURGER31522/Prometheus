# Prometheus 计划书

> 规格已于 2026-09-25 由用户确认。本文件既是**规格**（第 1–3 节），也是**执行计划**（第 4 节起）。
> 读者：执行开发的 AI Agent。开工前先读 `AGENTS.md`、`docs/DECISIONS.md` 和 `E:\tools\Prometheus-Desktop\使用说明.md`。
> 第 1–3 节（Goal / Boundaries / Done When）**只有用户同意才能修改**。其余章节的实现细节可以按实际情况修正，但要在 `docs/DECISIONS.md` 记录原因。

---

## 1. Goal

把 video-report-agent（下称 VRA）二开成 Windows 桌面软件 **Prometheus**：
- 粘贴 B 站或 YouTube 链接后，自动产出三件套：**精读报告**（保持 VRA 原有写作质量，加配图）、**思维导图**、**原样字幕**；
- 三件套在同一套「分类 → 标题」索引下浏览；
- 界面极简，视觉语言和 VRA 报告一致。

## 2. Boundaries

### 2.1 做

| 范围 | 内容 |
|---|---|
| 导航 | 左侧五个页签，顺序固定：**控制台 / 知识库 / 思维导图 / 字幕 / 设置** |
| 索引 | 知识库、思维导图、字幕三个页签共用同一套分类和标题。三级浏览：分类列表 → 条目列表 → 内容。条目标题显示为「报告标题」，下方小字显示「原视频标题 · UP 主 · 时长 · 导入日期」 |
| 导入 | 单个视频链接：B 站 BV 号、完整链接、`b23.tv` 短链、`?p=N` 分 P；YouTube 的 `watch?v=`、`youtu.be/`、`shorts/` 链接。可以一次粘贴多行，按顺序排队，**串行**处理。每次导入可以单独开关「配图」 |
| 时长 | **不限时长**。Pi 超时 = `1800 + 600 × ⌈时长秒数 / 3600⌉` 秒 |
| 转写 | 二选一，在设置里切换：**本地** faster-whisper `large-v3-turbo`（默认；CUDA 运行库和模型在首次启用时下载到数据目录）；**云端**百炼（沿用 VRA 的 paraformer 适配器，需要 DashScope Key）。只面向 Windows，不接入 VRA 的 MLX 后端（仅限 Mac） |
| 字幕 | ASR 原始分段，不经 AI 改写；中文字幕只做 OpenCC 繁→简的逐字转换（不改时间轴）。界面显示为带时间戳的列表，点击时间戳在浏览器里打开视频对应时刻。可以导出 SRT / TXT |
| 精读 | 只做 Standard 模式，报告一律中文。通过 Pi 驱动 VRA Skill；Pi 使用 `read,write,edit,powershell` 工具 |
| 配图 | 写作前按场景切换抽候选帧，由写报告的 Agent 看图、挑图、就地插入 `<figure>`；程序最后把图片内联为 base64。配图规则放在附加文件里，**不修改 VRA 原 Skill 文件**。当前模型不能看图时自动关闭配图并提示 |
| 思维导图 | 由报告正文提炼 Markdown 大纲，用 markmap 渲染；一级分支带跳转到视频时刻的链接 |
| 分类 | 只有一层。报告完成后由模型从已有分类里选一个，都不合适时新建；用户可以改名、移动条目、合并分类、删除空分类 |
| 设置 | 模型提供商 / 模型 / API Key（自定义 OpenAI 兼容提供商需填 Base URL，并勾选「支持看图」）；**转写方式（本地 / 云端）**：选本地时，DashScope Key 和云端模型输入框置灰、不能输入；选云端时才能输入，同时「启用本地转写」按钮置灰；切换不会清空已保存的 Key；选云端但 Key 为空时不能保存；代理地址；YouTube cookies.txt 路径；配图默认开关；数据目录（首次启动时选择） |
| 条目操作 | 重新生成（复用已有转写）、删除（整个条目文件夹）、取消进行中的任务、重试失败的任务。同一个视频重复导入时提示「已存在」，可选重新生成 |
| 仓库 | MIT 许可。VRA 以 git subtree 放在 `vendor/video-report-agent`（不 squash，锁定 `d060dfb`）。每个里程碑一个分支，合并后推送到 `origin` |

### 2.2 明确不做

macOS 支持（包括 VRA 的 MLX 转写）、问答 / RAG、标签网络、B 站登录、使用平台自带字幕、合集或播放列表批量导入、本地文件导入、速览（Brief）模式、PNG 长图、费用显示、深色模式、自动更新、多级分类、多语言界面、加密保存 API Key（Key 明文存数据目录，与 VRA 的 `.env` 做法一致）。

## 3. Done When

每条都写明「怎么判、谁来判」。命令默认在 `F:\project\Prometheus`、已执行 `. E:\tools\Prometheus-Desktop\env.ps1` 的 PowerShell 中运行，**以退出码 0 为通过**。

| # | 判据 | 判定命令 / 判定人 |
|---|---|---|
| **D1** | 上游 VRA 全部测试在本机 Windows 通过（只允许跳过 mlx 专属用例） | `uv run --package video-report-agent --extra enhancement --directory vendor/video-report-agent pytest -q`（如果参数需要调整，在 M1 定稿后写回本行，之后不再改） |
| **D2** | 后端测试全绿；第 12 节各里程碑列出的测试都存在；M0、M2–M8 每个里程碑分支上都至少有一个 `(red)` 提交，而且它比对应的 `feat`/`fix` 提交更早（M1 的「红」是上游已有的失败测试，豁免这一条） | `uv run pytest backend/tests -q -m "not live"`；`uv run ruff check backend`；`git log --oneline --grep "(red)" main` 按里程碑逐一核对（由执行 agent 在第 13 节贴出结果） |
| **D3** | 前端单测 + E2E 全绿。E2E 断言：① 侧栏五项的顺序；② 知识库、思维导图、字幕三个页签显示的分类名和条目标题**完全一致**；③ 点进条目后分别看到报告 iframe、markmap SVG、字幕行；④ 设置保存后刷新页面仍然保留；⑤ 控制台导入一条链接后，队列出现该条并最终显示「完成」（后端假流水线模式）；⑥ 设置里选「本地」时 DashScope Key 和云端模型输入框为 disabled，选「云端」时可以输入、「启用本地转写」按钮变为 disabled；来回切换后已填的 Key 仍在；选云端且 Key 为空时点保存会失败并显示提示；⑦ 点击报告里的原视频链接和导图里的时刻链接时，`openExternal` 收到对应地址，iframe 和应用页面都没有跳转 | `npm --prefix app run test`；`npm --prefix app run e2e` |
| **D4** | 界面所有颜色、字体只在 `app/src/shared/tokens.css` 里定义，且取值都来自第 9.2 节色板；五个页面的截图保存在 `docs/screenshots/` | `npm --prefix app run lint:design`；**「极简」由用户看截图判定**，结论记入 `docs/acceptance.md` |
| **D5** | 真实链路：一个时长约 3 小时的公开 B 站视频产出三件套。报告：没有外部资源引用、`data-source-units` ≥ 30、包含 `<h1>` 和 `section-time`、不残留 `{{VIDEO_DESCRIPTION}}`；导图：`##` 一级分支 ≥ 3；字幕：SRT 能解析，最后一条的结束时间与视频时长相差 ±60 秒以内。端到端耗时（从入队到完成）：云端转写且不配图 ≤ 20 分钟；本地转写且不配图 ≤ 25 分钟；云端转写且配图 ≤ 30 分钟 | `scripts/acceptance/live.ps1`（会产生 API 费用，手动触发） |
| **D6** | 加入配图规则后，文字质量不下降：同一份转写、同一模型和推理档位，分别用「原版 Skill」和「原版 Skill + 配图规则 + 候选帧」各生成一份报告，两份都通过 VRA 的 `inspect_report` 程序检查 | `scripts/acceptance/ab-figures.ps1` 判程序检查；**质量由用户并排阅读后签字**，记入 `docs/acceptance.md` |
| **D7** | 一个 YouTube 视频（带 cookies、经代理）跑通 D5 的全部产物断言（这一条不计时） | `scripts/acceptance/live.ps1 -Url <YouTube 链接>` |
| **D8** | NSIS 安装包 ≤ 300MB；静默安装后能启动，后端在 30 秒内 `/api/health` 返回 200；静默卸载后数据目录仍然保留 | `scripts/acceptance/installed-smoke.ps1` |
| **D9** | 在设置里首次启用本地转写：CUDA 运行库和模型下载到数据目录；一段 10 分钟样例音频转写成功，日志中出现 `device=cuda` | `scripts/acceptance/local-asr.ps1` |
| **D10** | 远程 `main` 与本地 `main` 一致；GitHub Actions（windows-latest）上的 CI 通过 | `git fetch origin; git rev-parse main origin/main`（两行相同）；CI 状态为绿 |

---

## 4. 技术栈与精确版本

所有版本号均在 2026-09-25 查证。锁文件（`uv.lock`、`app/package-lock.json`、`app/src-tauri/Cargo.lock`）提交进仓库，依赖声明使用**精确版本**（`==` / 不带 `^`）。

| 层 | 技术 | 版本 | 说明 |
|---|---|---|---|
| 桌面外壳 | Tauri | crate `tauri` 2.11.6、`tauri-build` 2.x；`@tauri-apps/cli` 2.11.5；`@tauri-apps/api` 2.11.1 | CLI 与 Artemis 项目同版本，本机已验证可用 |
| Tauri 插件 | dialog / opener | crate 与 npm 均为 `tauri-plugin-dialog` 2.7.3、`tauri-plugin-opener` 2.5.5 | 选择数据目录和 cookies 文件；在浏览器打开视频时刻 |
| Rust | stable | 1.98.1（MSVC） | 共用 `E:\tools\Artemis-Desktop` 的工具链 |
| 前端 | React / React DOM | 19.3.0 | 不使用 UI 组件库、路由库、状态管理库 |
| 前端 | TypeScript | 7.0.2 | |
| 前端 | Vite | 8.3.1；`@vitejs/plugin-react` 6.1.1 | |
| 思维导图 | markmap-lib / markmap-view | 0.18.12 | |
| 前端测试 | Vitest 5.0.2；`@testing-library/react` 16.3.3；jsdom 30.1.1；`@playwright/test` 1.63.0 | | |
| 后端运行时 | CPython | 3.12.14（python-build-standalone） | VRA 要求 `>=3.12,<3.13` |
| 后端框架 | FastAPI 0.141.1；uvicorn 0.54.0；pydantic 2.13.5 | | 存储用标准库 `sqlite3`，不用 ORM |
| 下载 | `yt-dlp[default]` | 2026.8.19 | 带 `yt-dlp-ejs`；YouTube 的 JS 运行时用随包 Node |
| 本地转写 | faster-whisper 1.2.1（→ ctranslate2 4.8.2） | 模型 `large-v3-turbo` = `mobiuslabsgmbh/faster-whisper-large-v3-turbo` | CUDA：`nvidia-cublas-cu12==12.9.2.10`、`nvidia-cudnn-cu12==9.26.0.51`，首次启用时安装 |
| 云端转写 | VRA paraformer 适配器 | 随 vendor | 需要 DashScope Key |
| Agent | Pi（`@earendil-works/pi-coding-agent`） | 0.85.0 | 必须与 VRA 一致 |
| Agent 运行时 | Node.js | 22.23.3 | 同时作为 yt-dlp 的 JS 运行时 |
| 媒体 | FFmpeg（BtbN LGPL 共享库版） | n8.1.3 | |
| Python 工具 | uv 0.12.9；pytest 9.1.1；ruff 0.16.9 | | |

**允许的回退**（必须记入 DECISIONS）：如果 TypeScript 7 或 Vite 8 与 Tauri / markmap / Vitest 出现无法绕过的兼容问题，可以回退到 TypeScript 5.9.x、Vite 7.x 的最新补丁版。除此以外，不得替换第 4 节的任何技术选型。

## 5. 工具链

见 `E:\tools\Prometheus-Desktop\使用说明.md`。要点：
- 每个终端先运行 `. E:\tools\Prometheus-Desktop\env.ps1`；`verify.ps1` 的退出码必须为 0。
- `UV_PYTHON` 已指向 3.12.14，`UV_PYTHON_DOWNLOADS=never`。
- `PLAYWRIGHT_BROWSERS_PATH=E:\tools\playwright-browsers`；缺少浏览器时运行 `npx playwright install chromium` 和 `uv run playwright install chromium-headless-shell` 补装。

## 6. 仓库结构

```
Prometheus/
├── AGENTS.md  CLAUDE.md  README.md  LICENSE  .gitignore
├── pyproject.toml            uv 工作区根：members = ["backend", "vendor/video-report-agent"]
├── uv.lock
├── .github/workflows/ci.yml
├── docs/
│   ├── PLAN.md  DECISIONS.md  acceptance.md
│   └── screenshots/          D4 截图
├── scripts/
│   ├── package.ps1           组装运行时并打 NSIS 安装包
│   └── acceptance/           live.ps1  ab-figures.ps1  installed-smoke.ps1  local-asr.ps1
├── vendor/
│   └── video-report-agent/   上游 VRA（git subtree，锁定 d060dfb；修改只限附录 A）
├── backend/
│   ├── pyproject.toml        name = "prometheus-backend"
│   ├── src/prometheus/
│   │   ├── server.py         应用工厂、命令行参数、鉴权中间件
│   │   ├── paths.py          数据目录布局（唯一定义各文件路径的地方）
│   │   ├── api/              按功能分文件：health / items / categories / content / settings / asr_components
│   │   ├── library/          SQLite 表结构、迁移、条目与分类的读写
│   │   ├── tasks/            串行队列、阶段定义、取消、超时
│   │   ├── settings/         settings.json 读写、Pi 的 models.json 生成、模型能力查询
│   │   ├── ingest/           链接解析、yt-dlp 下载（音频 / 配图用视频）、元数据
│   │   ├── transcribe/       local_whisper.py、cloud.py、components.py（CUDA 与模型安装）
│   │   ├── subtitle/         分段保存、SRT/TXT 导出
│   │   ├── report/           Pi 工作区组装、运行、定稿；overlays/figures.md；classify.py
│   │   ├── figures/          抽帧、候选筛选、清单
│   │   ├── mindmap/          报告大纲提取、生成、校验
│   │   └── fake/             假流水线（PROMETHEUS_FAKE=1，E2E 用）
│   └── tests/
│       ├── fixtures/
│       ├── <与功能同名的测试文件>
│       └── live/             pytest 标记 live，会调用真实服务
└── app/
    ├── package.json  package-lock.json  vite.config.ts  tsconfig.json  playwright.config.ts
    ├── scripts/lint-design.mjs
    ├── e2e/                  Playwright 用例
    ├── src/
    │   ├── main.tsx  App.tsx
    │   ├── features/
    │   │   ├── console/      控制台：导入框、队列
    │   │   ├── report/       知识库：精读报告查看
    │   │   ├── mindmap/      思维导图查看
    │   │   ├── subtitle/     原样字幕查看与导出
    │   │   └── settings/     设置
    │   └── shared/
    │       ├── tokens.css    唯一定义颜色、字体、间距的地方
    │       ├── api.ts        后端客户端（带 token）
    │       ├── platform.ts   Tauri 能力的封装（浏览器 E2E 时走替身）
    │       ├── Sidebar.tsx
    │       └── LibraryBrowser.tsx  三个内容页签共用的「分类 → 条目 → 内容」组件
    └── src-tauri/
        ├── Cargo.toml  Cargo.lock  tauri.conf.json  build.rs
        ├── src/main.rs       窗口、后端进程的启动与关闭、backend_info 命令
        └── resources/runtime/   打包时由 scripts/package.ps1 生成（不提交）
```

## 7. 数据目录

用户首次启动时选择数据目录。Tauri 的应用配置目录里只存一个 `app.json`（内容为 `{"data_dir": "..."}`）。

```
<数据目录>/
├── prometheus.db
├── config/
│   ├── settings.json
│   └── pi/                      PI_CODING_AGENT_DIR（models.json、会话）
├── runtime/cuda/                本地转写的 CUDA 库（pip --target）
├── models/                      faster-whisper 模型
├── logs/backend.log
└── items/<条目ID>/              条目 ID 为 32 位小写十六进制
    ├── report/report.html       精读报告（单文件，图片已内联）
    ├── mindmap/mindmap.md       思维导图
    ├── subtitle/segments.json   ASR 原始分段 [{start, end, text}]（秒）
    ├── subtitle/subtitle.srt
    └── work/                    Pi 工作区：input.json、source.info.json、asr.json、transcript.md、
                                 frames/、sessions/、run.trace.jsonl、pi.events.jsonl、音视频临时文件
```

- `backend/src/prometheus/paths.py` 是唯一拼接这些路径的地方。
- 条目完成后删除 `work/` 里的音视频文件，保留日志、`asr.json`、`transcript.md`（重新生成时复用）。

### 7.1 SQLite 表结构（`prometheus.db`，schema_version = 1）

```sql
CREATE TABLE schema_version (version INTEGER NOT NULL);
CREATE TABLE categories (
  id         INTEGER PRIMARY KEY,
  name       TEXT NOT NULL UNIQUE,
  created_at TEXT NOT NULL                 -- ISO 8601 UTC
);
CREATE TABLE items (
  id              TEXT PRIMARY KEY,
  platform        TEXT NOT NULL CHECK (platform IN ('bilibili','youtube')),
  video_id        TEXT NOT NULL,           -- B 站为 "BVxxxx" 或 "BVxxxx?p=N"；YouTube 为 11 位 ID
  source_url      TEXT NOT NULL,
  source_title    TEXT,
  uploader        TEXT,
  duration_s      REAL,
  report_title    TEXT,                    -- 报告的 <h1>
  category_id     INTEGER REFERENCES categories(id),
  figures         INTEGER NOT NULL,        -- 0/1
  status          TEXT NOT NULL CHECK (status IN ('queued','running','done','failed','cancelled','interrupted')),
  stage           TEXT,                    -- 见 8.3
  mindmap_status  TEXT CHECK (mindmap_status IN ('ok','failed')),
  error_code      TEXT,
  error_message   TEXT,
  created_at      TEXT NOT NULL,
  started_at      TEXT,
  finished_at     TEXT,
  UNIQUE (platform, video_id)
);
```

- 后端启动时，把 `status='running'` 的条目改为 `interrupted`，由用户手动重试。
- 只有 `status='done'` 的条目出现在三个内容页签中。

## 8. 后端设计

### 8.1 进程与鉴权

- Tauri 启动时先在 Rust 里取一个空闲端口（绑定 `127.0.0.1:0` 后立即释放），生成 32 字节随机 token，然后启动：
  `runtime\python\python.exe -m prometheus.server --host 127.0.0.1 --port <端口> --token <token> --config-dir <Tauri 应用配置目录> --runtime-dir <runtime 目录>`
  并设置环境变量 `PYTHONUTF8=1`，`PATH` 前置 `runtime\node` 和 `runtime\ffmpeg`，Windows 进程创建标志带 `CREATE_NO_WINDOW`（子进程会继承这个隐藏的控制台，不会弹出黑窗口）。
- 开发模式：如果设置了环境变量 `PROMETHEUS_BACKEND_CMD`，Rust 改用它启动后端（例如 `uv run python -m prometheus.server`）。
- 测试模式：设置了环境变量 `PROMETHEUS_TEST_DATA_DIR` 时，直接使用它作为数据目录，跳过首次启动的目录选择（M7 的 E2E 和 M8 的安装冒烟测试会用到）。
- 后端启动后把实际端口写入 `<数据目录>/logs/backend.port`（数据目录已设置时），供验收脚本读取。
- Tauri 命令 `backend_info` 向前端返回 `{port, token}`。
- 数据目录还没设置时，除 `/api/health` 和 `/api/app/data-dir` 以外的接口都返回 409 `{"code": "DATA_DIR_NOT_SET"}`；设置之后立即初始化数据目录和数据库，不需要重启。
- 除 `GET /api/health` 以外，所有接口都要求请求头 `Authorization: Bearer <token>`。给 iframe 用的内容类 GET 接口也接受 `?token=`。
- **跨域**：前端页面的来源是 Tauri 的 `http://tauri.localhost`（Windows 上的 Tauri 2），开发时是 Vite 开发服务器（`http://localhost:1420`），而后端在 `http://127.0.0.1:<端口>`，属于跨域。后端用 CORS 中间件只放行这几个来源；`tauri.conf.json` 的 CSP 需要允许 `connect-src` 和 `frame-src` 指向 `http://127.0.0.1:*`，`img-src` 允许 `data:`。前端访问后端时一律使用 `http://127.0.0.1:<端口>` 的绝对地址（iframe 的 `src` 也一样）。
- 退出：Tauri 在 `RunEvent::Exit` 时结束后端进程；后端每 2 秒检查一次父进程是否还在，不在就自行退出。后端退出前先取消当前任务，并用 `taskkill /PID <pid> /T /F` 结束它的子进程树（Pi、ffmpeg）。

### 8.2 接口（前缀 `/api`）

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/health` | `{"status":"ok"}`，不需要鉴权 |
| GET / PUT | `/app/data-dir` | 读取、设置数据目录（首次启动用） |
| GET / PUT | `/settings` | 读写设置（返回时 Key 用掩码表示） |
| POST | `/settings/test-model` | 用第 8.6 节「一次性文本调用的统一写法」发一个简短提示，返回是否成功；再按第 8.7 节判断模型能否看图 |
| POST | `/asr-components/install` | 开始安装本地转写组件；`GET /asr-components` 查询状态和进度 |
| POST | `/items` | `{url, figures}` → 201 `{id}`；链接不支持 → 422 `{code}`；已存在 → 409 `{id}` |
| GET | `/items?status=&category_id=` | 条目列表 |
| GET / PATCH / DELETE | `/items/{id}` | 详情 / 修改 `category_id` / 删除整个条目文件夹 |
| POST | `/items/{id}/regenerate` | `{figures}`，复用已有转写；需要配图但视频文件已被清理时，重新下载视频流 |
| POST | `/items/{id}/cancel`、`/items/{id}/retry` | |
| GET | `/queue` | 未完成和最近 20 条已完成的任务（控制台每秒轮询一次） |
| GET | `/categories` | `[{id, name, count}]`（count 只统计 done 条目） |
| PATCH / DELETE | `/categories/{id}` | 改名（重名 → 409）/ 删除（非空 → 409） |
| POST | `/categories/{id}/merge` | `{into_id}`，把条目移过去并删除原分类 |
| GET | `/items/{id}/report` | `text/html` |
| GET | `/items/{id}/mindmap` | `text/markdown` |
| GET | `/items/{id}/subtitle?format=json\|srt\|txt` | |

### 8.3 任务流水线

串行执行：同一时刻只有一个条目处于 `running`。阶段依次为：

| stage | 做什么 | 产物 |
|---|---|---|
| `resolve` | 解析链接、获取元数据（yt-dlp，不下载） | `work/source.info.json`，并填写 items 表的元数据字段 |
| `download` | 下载音频（`bestaudio`）；开了配图时另外下载 ≤480p 的视频流 | `work/media.*`、`work/video.*` |
| `transcribe` | 用 ffmpeg 转成 16kHz 单声道 wav，再做 ASR | `work/asr.json`、`subtitle/segments.json`、`subtitle/subtitle.srt` |
| `transcript` | 调用 vendor 的 `build_transcript` 生成规范转写，写 `transcript.md`（格式与 vendor `pipeline.py` 第 188–194 行一致） | `work/transcript.md` 等 |
| `frames` | 仅在开了配图且模型能看图时执行：抽候选帧 | `work/frames/*.jpg`、`work/frames/frames.json` |
| `report` | 组装 Pi 工作区并运行 Pi | `work/report.html` |
| `finalize` | 填写视频简介占位符、内联图片、注入配图样式、提取 `<h1>` | `report/report.html` |
| `mindmap` | 生成并校验思维导图 | `mindmap/mindmap.md`；失败时只把 `mindmap_status` 记为 `failed`，条目仍然算完成 |
| `classify` | 自动归入分类 | 更新 `category_id` |

- 每个阶段在 `work/run.trace.jsonl` 里记录开始和结束时间（沿用 vendor 的 `RunTrace`）。D5 的耗时从这里计算。
- 取消：结束当前阶段的子进程树，状态记为 `cancelled`。
- 错误码沿用 vendor 的分类（`INPUT_REJECTED`、`EXTERNAL_API_FAILURE`、`ENVIRONMENT_FAILURE`、`IMPLEMENTATION_FAILURE` 等），另加 `URL_UNSUPPORTED`、`YOUTUBE_COOKIES_REQUIRED`（yt-dlp 报 "Sign in to confirm you're not a bot"）、`CUDA_UNAVAILABLE`。`error_message` 用面向用户的中文说明应该怎么处理。

### 8.4 ingest（链接与下载）

链接解析是纯函数：`parse_url(text) -> Source(platform, video_id, canonical_url, page)`。必须覆盖的用例：

| 输入 | 结果 |
|---|---|
| `https://www.bilibili.com/video/BV1xJYT6EEYc/` | bilibili，`BV1xJYT6EEYc`，p=1 |
| `https://www.bilibili.com/video/BV1xJYT6EEYc/?p=3&spm_id_from=333` | bilibili，`BV1xJYT6EEYc?p=3` |
| `BV1xJYT6EEYc` | bilibili，p=1 |
| 带【标题】的 B 站分享文案（其中含链接） | 从文案中提取链接 |
| `https://b23.tv/<短码>` | 跟随 HTTP 跳转后再解析（测试里模拟跳转） |
| `https://www.youtube.com/watch?v=jNQXAC9IVRw&t=10s` | youtube，`jNQXAC9IVRw` |
| `https://youtu.be/jNQXAC9IVRw` | 同上 |
| `https://www.youtube.com/shorts/<11位ID>` | youtube |
| YouTube 播放列表链接、B 站合集 / 空间链接、其他网站 | 拒绝，`URL_UNSUPPORTED` |

- B 站的规范化可以复用 vendor `ingest.py` 里的解析函数，但**不得**调用它的时长校验（`MAX_VIDEO_SECONDS`）。本项目不设时长上限，要有测试：元数据时长为 5 小时的视频可以正常入队。
- yt-dlp 选项：`writeinfojson`；`proxy` 取自设置；YouTube 额外加 `js_runtimes={"node": {"path": <node.exe>}}` 和 `cookiefile`（未配置 cookies 时直接报 `YOUTUBE_COOKIES_REQUIRED`，不去请求）。
- 配图用的视频流格式：`bv*[height<=480][ext=mp4]/bv*[height<=480]/wv*`。

### 8.5 transcribe（转写）

- **本地**（`transcribe/local_whisper.py`）：
  - **在独立子进程里运行**（`python -m prometheus.transcribe.local_whisper <音频> <输出 asr.json> ...`），不在后端进程内加载模型。理由：取消任务时可以直接结束子进程（线程无法强制中断）；转写结束后显存随子进程退出一起释放（VRA 对 MLX 也是这样做的，见 vendor `asr.py` 第 212–219 行）；
  - 子进程启动时，把 `<数据目录>/runtime/cuda` 下每个 `nvidia/*/bin` **同时**加入 `PATH` 前部并调用 `os.add_dll_directory`，然后才导入 ctranslate2（cuDNN 9 的部分 DLL 是运行中按需加载的，只靠 `add_dll_directory` 可能找不到）；
  - `WhisperModel("large-v3-turbo", device="cuda", compute_type="float16", download_root=<数据目录>/models)`；
  - 检测不到 CUDA 设备时，改用 `device="cpu", compute_type="int8"`，并在任务上提示「未检测到 NVIDIA GPU，转写会很慢」；CUDA 库还没安装时报 `CUDA_UNAVAILABLE`；
  - 先用 `WhisperModel.detect_language`（faster-whisper 1.2.1 `transcribe.py` 第 1768 行）判断语言；检测为中文（`zh`）时，`transcribe` 传 `language="zh"` 和 `initial_prompt="以下是普通话的句子。"`，让模型尽量直接输出简体；其他语言只传检测到的 `language`。`vad_filter=True`；
  - 输出转换成 vendor 的 `AsrRun` 结构，写 `asr.json`，然后交给 vendor 的 `build_transcript`；
  - 日志写一行 `asr backend=local device=<cuda|cpu> model=large-v3-turbo`（D9 靠它判定）。
- **组件安装**（`transcribe/components.py`）：用随包 Python 执行 `-m pip install --target <数据目录>/runtime/cuda nvidia-cublas-cu12==12.9.2.10 nvidia-cudnn-cu12==9.26.0.51`，然后预下载模型；代理取自设置；进度通过 `GET /asr-components` 查询。
- **云端**（`transcribe/cloud.py`）：调用 vendor 的 `transcribe_audio(backend="paraformer", ...)`，参数由 vendor 的 `resolve_media_config` 给出，`DASHSCOPE_API_KEY` 取自设置。
- **字幕**：`segments.json` 取 `asr.json` 的原始分段（不是规范化之后的单元）；识别语言为中文时，对文本做 OpenCC `t2s` 逐字转换（与 vendor `transcript_foundation.py` 第 224–234 行使用的转换器相同），时间轴和断句不变。SRT 格式：序号、`HH:MM:SS,mmm --> HH:MM:SS,mmm`、文本、空行，编码 UTF-8 无 BOM。TXT 格式：每行 `[HH:MM:SS] 文本`。

### 8.6 report（精读报告）

- 工作区 `work/` 的内容与 vendor 的 `pipeline.py` 保持一致：`input.json`（vendor 写入的字段，加上 `platform`：`"Bilibili"` 或 `"YouTube"`；`report_mode` 固定为 `"standard"`；`title`、`uploader`、`attribution`、`url`）、`transcript.md`、`source.info.json`。
- 调用 vendor 的 `PiRunner`，参数经附录 A 的 V2 扩展：
  - `command_prefix=[<node.exe>, <pi 包>\dist\bundle\cli.js]`：**直接用 node 运行 Pi，不经过 `pi.cmd`**。原因：`pi.cmd` 是批处理文件，参数会先经过 cmd.exe 解析，`%`、`^`、`&`、`|`、引号和换行都可能被改写，而且 cmd.exe 的命令行上限只有 8191 个字符；直接调用 node.exe 的上限是 32767 个字符，也没有转义问题；
  - `agent_dir=<数据目录>/config/pi`：vendor 的 `pi.py` 在**模块导入时**就用当前工作目录算出 `PI_AGENT_DIR`（`pi.py` 第 15–16 行），首次启动时数据目录还没选，按原逻辑会落到安装目录里，所以必须显式传入；
  - `tools="read,write,edit,powershell"`；
  - `extra_prompt`：「本机为 Windows，命令工具是 PowerShell；运行 Python 用 `& $env:VIDEO_REPORT_PYTHON script.py`；脚本和中间文件只写在当前工作区。报告一律用简体中文撰写，专有名词和术语可以保留原文。」开了配图时再追加：「另读 figures.md，按其中规则使用 frames/ 里的候选帧。」
  - `extra_files`：开了配图时加入 `report/overlays/figures.md`；
  - `timeout`：按第 2.1 节的公式；
  - `VIDEO_REPORT_PYTHON` 由 `PiRunner` 自动设为 `sys.executable`（打包后就是随包的 python.exe，开发时是 `.venv` 的 python），不需要另外设置；传给 Pi 的环境变量里要有 `PYTHONUTF8=1`，这样 Agent 执行的 Python 脚本输出中文时不会因 GBK 编码出错。
- 保留 vendor 的完成判定：等待 `agent_settled`，并且最后一条 assistant 消息的 `stopReason == "stop"`。
- **定稿**（`report/finalize.py`）：用 vendor 的 `fill_video_description` 填写简介；把 `src="frames/..."` 替换为 `data:image/jpeg;base64,...`；如果有 `<figure class="report-figure">`，在 `</head>` 前注入一段配图样式（只使用模板的 CSS 变量：边框 `var(--line)`、说明文字 `var(--muted)`、13px）；提取第一个 `<h1>` 的文本作为 `report_title`；最后检查：`<img>`、`<script>`、`<link>`、`<iframe>` 都不能引用外部地址（`<a href>` 不受限制）。
- **一次性文本调用的统一写法**（分类、思维导图、「测试模型」都用它，封装在 `settings/` 里的一个函数中）：
  `<node.exe> <cli.js> -p --no-tools --no-session --offline --no-extensions --no-skills --no-prompt-templates --no-themes --no-context-files --provider <p> --model <m> --thinking <t> --api-key <key>`，工作目录设为该条目的 `work/`，环境变量 `PI_CODING_AGENT_DIR=<数据目录>/config/pi`；**提示词全文通过标准输入传入**（Pi 的 print 模式会把管道输入并入提示词，见 Pi README 第 550 行），不放在命令行参数里。那组 `--no-*` 参数与 VRA 的 `pi.py` 一致，避免 Pi 读取工作目录及其上级目录里的 AGENTS.md 等上下文文件。
- **分类**（`report/classify.py`）：用上面的统一写法。输入为已有分类名（最多 50 个）、报告标题、导语段、所有 `<h2>` 标题；要求只输出 JSON `{"category": "名称"}`；规则：优先选已有分类；新分类名为 2–8 个汉字的名词短语，不能用「其他 / 综合 / 杂项」这类名字。解析或校验失败时重试一次，仍然失败就归入「未分类」。

### 8.7 figures（配图）

- 模型能力：`settings/` 通过 `<node.exe> <cli.js> --offline --list-models` 的输出判断当前模型的 `images` 列是否为 `yes`（自定义提供商以设置里的勾选为准）。**没有 Key 时 Pi 不会列出任何模型**（2026-09-25 实测，输出 "No models available"），所以调用时要在环境变量里提供当前 Key：`PI_API_KEY`，以及 Pi 内置提供商读取的 `<提供商名大写>_API_KEY`（例如 `DEEPSEEK_API_KEY`）。不能看图时跳过 `frames` 阶段，并在任务上提示。
- 抽帧：`ffmpeg -i video -vf "select='gt(scene,0.3)',showinfo,scale=960:-2" -fps_mode vfr -q:v 4`，从 stderr 解析 `pts_time`。
- 筛选（纯函数，要有单测）：
  - 两帧间隔不少于 20 秒；
  - 每小时最多 20 帧，全片最多 80 帧；
  - 场景帧少于 5 张时，每 5 分钟均匀补一帧，直到满足上限；
  - 文件命名为 `f_<6位秒数>.jpg`；
  - `frames.json` 为 `[{"file", "t", "label": "MM:SS 或 HH:MM:SS"}]`。
- `report/overlays/figures.md` 的规则（M5 时写成正式文本，要点如下）：
  1. 候选帧在 `frames/`，清单是 `frames/frames.json`；
  2. 写每个大章节之前，用 read 工具查看该章节时间范围内的候选帧；
  3. 只选画面承载了正文没有的信息的帧，例如幻灯片、图表、公式板书、代码、软件界面、实物展示、地图；不选口播人像、转场、片头片尾、广告画面；
  4. 每个大章节最多 1 张，全篇最多 12 张；没有合适的就不配，不为配图而配图；
  5. 插在首次讨论该画面内容的段落之后，写法为 `<figure class="report-figure" data-frame-t="秒数" data-source-units="..."><img src="frames/f_000332.jpg" alt="..."><figcaption>画面要点 · 05:32</figcaption></figure>`；说明文字写画面里的关键信息，与正文互补、不重复；
     **图片只用 `frames/...` 相对路径引用，不要自己转成 base64**，程序会在交付后自动内联。这是对 SKILL.md「自包含、无外部依赖」要求的唯一例外，必须在规则里明说；否则 Agent 可能自己把图片写成 base64，一张 960px 的截图就是约十万个字符的输出，费用和耗时都会暴涨；
  6. 画面里的数字、文字与转写冲突时，核对后只写能确认的内容；
  7. 其余所有规则（来源绑定、篇幅、措辞、商业推广排除）以 SKILL.md 和 standard.md 为准，配图不改变它们。

### 8.8 mindmap（思维导图）

- 输入：从 `report.html` 提取的大纲，包括 `<h1>`、导语、每个 `<h2>` 及其 `section-time`、`<h3>`，以及正文段落（纯文本）。
- 调用：第 8.6 节「一次性文本调用的统一写法」（报告大纲可能超过一万字，必须经标准输入传入），要求只输出 Markdown。
- 格式要求：
  - 一行 `# 报告标题`；
  - 3–7 个 `##` 一级分支，每个一级分支末尾带时间链接 `[05:32](<视频时刻链接>)`，时间取对应章节 `section-time` 的起点；
  - 最深到 `####`，其下可以用 `-` 列表；
  - 每个节点的文字不超过 40 个字（**不含**末尾的时间链接）；
  - 不写报告里没有的内容。
- 视频时刻链接：B 站 `https://www.bilibili.com/video/<BV>/?p=<N>&t=<秒>`；YouTube `https://www.youtube.com/watch?v=<ID>&t=<秒>s`。
- 校验失败时带上错误说明重试一次；仍然失败则 `mindmap_status='failed'`，界面上提供「重新生成导图」按钮（`POST /items/{id}/regenerate` 带 `{"only": "mindmap"}`）。

### 8.9 settings（设置）

`<数据目录>/config/settings.json`：

```json
{
  "llm": {"provider": "deepseek", "model": "deepseek-flash", "api_key": "", "thinking": "low",
          "custom": {"base_url": "", "supports_images": false}},
  "asr": {"backend": "local", "dashscope_api_key": "", "cloud_model": "paraformer-v2"},
  "network": {"proxy": "", "youtube_cookies_file": ""},
  "figures_default": true
}
```

- `asr.backend` 只有 `local` 和 `cloud` 两个值（`cloud` 对应 vendor 的 `paraformer` 后端）。vendor 的 `resolve_media_config`（`media_config.py` 第 38–40 行）在不传参数时默认用 `mlx`，而且只接受 `mlx` / `paraformer`：因此**只有云端路径**调用它，并显式传 `asr_backend="paraformer"`；本地路径不调用它，`build_transcript` 需要的 `ocr_backend` 直接传 `"rapidocr"`（OCR 处于关闭状态），并且要有测试保证环境变量 `ASR_BACKEND` 不会影响本地路径。
- 校验：`asr.backend == "cloud"` 且 `dashscope_api_key` 为空时，`PUT /settings` 返回 422 `{"code": "DASHSCOPE_KEY_REQUIRED"}`。切换 `asr.backend` 时不清空已保存的 `dashscope_api_key` 和 `cloud_model`。
- 提供商选项：`deepseek`、`zhipu`（沿用 VRA 的 `models.json`）、`custom`（OpenAI 兼容：写入 `models.json` 的 `custom` 提供商，`api` 为 `openai-completions`）。
- 首次运行时把 vendor 的 `defaults/models.json` 复制到 `config/pi/models.json`，之后只改 `custom` 这一项。
- `GET /settings` 返回的 Key 只显示后 4 位。

## 9. 前端设计

### 9.1 极简原则（依据）

- NN/g 可用性启发式第 8 条：界面里不放无关或很少用到的信息，每多一个元素都会稀释关键信息 —— https://www.nngroup.com/articles/aesthetic-minimalist-design/
- iA「Web Design is 95% Typography」：把文本当作界面，靠行距、留白和克制的用色保证可读性 —— https://ia.net/topics/the-web-is-all-about-typography-period
- Bear、Things 3 的共同做法：只用一个强调色；动效只用来给出反馈；不堆功能。

落到本项目的具体规则：
1. 只有一个强调色（`--accent`），只用在：当前页签指示条、主按钮、键盘焦点环、链接悬停；
2. 不用渐变、不用大面积阴影（只允许弹出层用一层 `0 1px 3px rgba(36,45,53,.08)`）、不用插画或装饰图标；
3. 不用 toast 通知、不用骨架屏；任务状态直接以文字写在队列里；
4. 动效只有 hover / 选中的颜色过渡，时长 120ms；在 `prefers-reduced-motion` 下取消；
5. 状态不能只靠颜色表达，失败状态同时显示「失败」文字；
6. 每个页面只有一个主操作按钮。

### 9.2 设计令牌（`app/src/shared/tokens.css`，取自 VRA 报告模板）

```css
:root {
  --paper: #fff;      --canvas: #f2f5f7;  --ink: #414b55;   --heading: #242d35;
  --muted: #65717d;   --accent: #c8562e;  --line: #e9edf0;  --wash: #fff8e8;
  --font-ui: -apple-system, BlinkMacSystemFont, "PingFang SC", "Microsoft YaHei", sans-serif;
  --font-mono: ui-monospace, monospace;
  --space-1: 4px; --space-2: 8px; --space-3: 12px; --space-4: 16px; --space-6: 24px; --space-8: 32px;
  --radius: 6px;
  --text-sm: 12px; --text-base: 14px; --text-lg: 16px; --text-xl: 20px;
  --shadow-pop: 0 1px 3px rgba(36,45,53,.08);
}
```

`lint:design` 脚本的规则：扫描 `app/src/**/*.{css,tsx,ts}`，除了 `tokens.css` 以外，出现 `#xxx`、`rgb(`、`hsl(`、`font-family` 字面量即报错（`rgba(36,45,53,.08)` 只允许出现在 `tokens.css` 中定义为 `--shadow-pop`）；`tokens.css` 里的颜色值必须属于上面这个列表。

### 9.3 布局与页面

- 窗口默认 1200×800，最小 960×640，标题为「Prometheus」。
- 左侧栏宽 184px，背景 `--canvas`，纯文字页签，当前项左侧有 2px `--accent` 竖条；右侧内容区背景 `--paper`。
- **首次启动**：只显示一个说明句和一个「选择数据目录」按钮（Tauri 目录对话框）。
- **控制台**：
  - 多行输入框（占位文字「粘贴 B 站或 YouTube 链接，每行一个」）、「配图」复选框（默认值取自设置）、主按钮「导入」；
  - 下方是队列列表，每行显示：标题（元数据出来之前显示链接）、当前阶段的中文名（解析 / 下载 / 转写 / 整理转写 / 抽帧 / 写作 / 定稿 / 导图 / 归类）、已用时间，以及操作「取消 / 重试 / 查看」。「查看」跳转到知识库里的该条目；
  - 重复导入时，在该行内联提示「已存在」，并给出「重新生成」按钮。
- **知识库 / 思维导图 / 字幕**：都使用 `LibraryBrowser`，只有第三级的内容渲染器不同。
  - 第一级：分类行（名称 + 条目数）。分类名可以原地重命名；「合并到…」和「删除」（只对空分类显示）放在行尾的「⋯」菜单里；
  - 第二级：条目行（主行为报告标题，副行为「原标题 · UP 主 · 时长 · 日期」）。「移动到…」「重新生成」「删除」放在「⋯」菜单里；
  - 第三级：顶部是面包屑「页签名 / 分类 / 报告标题」。
    - 知识库：`<iframe sandbox="allow-scripts" src="http://127.0.0.1:<端口>/api/items/{id}/report?token=...">`，占满宽度；
    - 思维导图：markmap 渲染（可以缩放、拖拽、折叠），右上角「导出 .md」；
    - **外部链接不能在应用内打开**：报告题头有原视频链接，页尾有站点链接，导图的一级分支带时刻链接。在 sandbox iframe 或 Tauri 窗口里直接点击，会把视频网站加载进应用内部。处理方法：
      - 报告：`GET /items/{id}/report` 返回页面时，在 `</body>` 前**临时注入**一小段脚本（不修改磁盘上的 `report.html`）：拦截 `a[href^="http"]` 的点击，调用 `preventDefault()`，然后 `parent.postMessage({type: "open-external", href}, "*")`；前端收到消息、确认来源是这个 iframe 后，调用 `platform.openExternal`；
      - 导图：在 markmap 容器上监听点击，遇到 `<a>` 就阻止默认行为，改为调用 `platform.openExternal`；
      - 对应 D3 的第 ⑦ 条断言；
    - 字幕：分段列表，每行为 `[时间] 文本`；点时间通过 opener 插件在浏览器打开视频时刻；右上角「导出 SRT / 导出 TXT」。列表使用 CSS `content-visibility: auto` 应对上千行。
  - 三个页签共享同一个「当前分类 / 当前条目」状态：在知识库里打开一个条目后切到思维导图，直接显示同一条目的导图。
- **设置**：「模型」「转写」「网络」「数据」四组表单，底部一个「保存」主按钮。「测试模型」按钮显示结果文字（是否可用、能否看图）。
  - 「转写」组最上方是一个二选一的分段控件「本地 / 云端」，下面依次是：「启用本地转写」按钮（显示下载进度文字）、DashScope Key 输入框、云端模型输入框；
  - 选「本地」时，DashScope Key 和云端模型两个输入框用原生 `disabled` 属性禁用，外观置灰（文字 `--muted`、背景 `--canvas`）；选「云端」时恢复可输入，同时「启用本地转写」按钮变为 `disabled`；
  - 切换不会清空已经填写的内容；
  - 选「云端」且 Key 为空时点「保存」：不提交，在 Key 输入框下方显示「请填写 DashScope API Key」。

### 9.4 platform.ts

封装 `pickDirectory()`、`pickFile()`、`openExternal(url)`、`backendInfo()`。在 Tauri 中调用插件和命令；在浏览器 E2E 中（`import.meta.env.VITE_E2E === "1"`）返回固定的测试值，`openExternal` 记录调用以供断言。

## 10. 打包

`scripts/package.ps1` 依次执行：
1. 运行 `verify.ps1`，退出码不为 0 就停止；
2. 按 `E:\tools\Prometheus-Desktop\使用说明.md` 第 4 节，把 python、node.exe、pi、ffmpeg（不含 ffplay）复制到 `app/src-tauri/resources/runtime/`；
3. `uv export --package prometheus-backend --no-dev --no-hashes --no-emit-workspace --no-emit-package playwright --no-emit-package mlx-whisper > build/requirements.txt`，然后用 runtime 里的 python 执行 `-m pip install --no-deps --target runtime\python\Lib\site-packages -r build\requirements.txt`，再**以非 editable 方式**安装 backend 和 vendor 两个本地包（同样 `--no-deps`）。`--no-emit-workspace` 是必需的：否则导出的清单里会包含指向源码目录的 `-e ./vendor/...` 行，安装包会依赖开发机上的源码；
4. 检查 `runtime\python\Lib\site-packages\video_report_agent\skills\video-report\SKILL.md`、`assets\report-template.html`、`defaults\models.json` 都存在（Skill 和模板是非 Python 文件，要确认被打进了包里），缺任何一个就停止；
5. 删除 runtime 里的 `__pycache__`、`test/`、`tests/`；
6. `npm --prefix app run build`，然后 `npm --prefix app run tauri build -- --bundles nsis`；
7. 把安装包复制到 `E:\tools\Prometheus-Desktop\release\`，打印大小。

体积参考（2026-09-25 实测，用 xz -6 压缩，接近 NSIS 的 LZMA）：node.exe 22MB、pi 17MB、Python 基础解释器 16MB、ffmpeg（不含 ffplay）51MB，合计 103MB；加上 Python 依赖包，估计安装包在 170–210MB，低于 D8 的 300MB 上限。

`tauri.conf.json`：`identifier` 为 `com.hamburger31522.prometheus`，`productName` 为 `Prometheus`，`bundle.resources` 包含 `resources/runtime/**/*`，NSIS 的 `installMode` 为 `currentUser`。

测试（保证打包时去掉 playwright 不会出错）：先把 `sys.modules["playwright"]` 设为 `None`（这样任何导入 playwright 的尝试都会立即报错），然后导入 `prometheus.server`、`video_report_agent.pipeline`、`video_report_agent.paraformer`，都必须成功。
注意 vendor 的 `paraformer.py` 在云端转写**运行途中**（第 100、234 行）会临时 `from .pipeline import write_json`，而 `pipeline.py` 顶部导入了依赖 playwright 的 `report_image`。所以只检查「导入后台时没有加载 playwright」是不够的：不做附录 A 的 V3，打包版的每一次云端转写都会在中途崩溃。

## 11. Git 与 CI

- 远程：`origin` = https://github.com/HAMBURGER31522/Prometheus.git；另加 `upstream-vra` = https://github.com/imexlovery/video-report-agent.git。
- 分支：见第 12 节每个里程碑。合并方式：`git merge --no-ff`，合并后 `git push origin main <分支>`。禁止强推。
- 提交顺序：`test(scope): ... (red)` → `feat(scope): ...`。
- 以后合并上游：`git subtree pull --prefix=vendor/video-report-agent upstream-vra main`（不加 `--squash`），合并后必须重跑 D1、D2、D6。
- CI（`.github/workflows/ci.yml`，运行在 windows-latest）：安装 uv 0.12.9 和 Python 3.12.14、Node 22.23.3；运行 `uv run pytest backend/tests -q -m "not live"`、`uv run ruff check backend`、`npm --prefix app ci`、`npm --prefix app run test`、`npm --prefix app run lint:design`。E2E、D1 和打包只在本机运行。
- 因此，**非 live 的后端测试不得依赖 ffmpeg、node、Pi、GPU 等外部程序或硬件**：用替身（桩函数、伪造的子进程输出）。需要真实程序的测试一律标记 `live`。

## 12. 里程碑

每个里程碑：在分支上开发 → 按红绿方式完成 → 运行 Done When 命令，全部退出码为 0 → 在第 13 节登记 → 合并到 main 并推送。

### M0 仓库骨架（分支 `m0-bootstrap`）

1. 运行 `verify.ps1`，退出码必须为 0。
2. 引入 VRA：
   ```powershell
   git remote add upstream-vra https://github.com/imexlovery/video-report-agent.git
   git fetch upstream-vra main
   git subtree add --prefix=vendor/video-report-agent d060dfb
   ```
3. 根目录 `pyproject.toml`（uv 工作区；`requires-python = "==3.12.*"`；`[tool.uv] environments = ["sys_platform == 'win32'"]`，只为 Windows 解析依赖，避免 VRA 的 `mlx` 可选依赖（只有 macOS 的包）干扰锁文件；dev 组包含 pytest==9.1.1、ruff==0.16.9；pytest 注册 `live` 标记）；`backend/pyproject.toml`（依赖为第 4 节列出的精确版本，以及工作区里的 `video-report-agent`）；运行 `uv lock` 和 `uv sync --all-packages`。
4. 后端：`server.py` 实现 `/api/health` 和 token 鉴权。先写 `tests/test_health.py`（包括不带 token 访问其他接口返回 401），看到它失败，再实现。
5. 前端：手工创建 `app/`（按第 4 节锁定版本；`vite.config.ts` 设 `server.port = 1420`、`strictPort: true`，与 `tauri.conf.json` 的 `devUrl` 和后端 CORS 白名单保持一致），加一个 Vitest 冒烟测试；创建 `src-tauri`（按第 10 节写 `tauri.conf.json`，窗口按第 9.3 节）；`lint-design.mjs` 和 `tokens.css` 按第 9.2 节。
6. CI 工作流按第 11 节。
7. 到 `E:\tools\Prometheus-Desktop\使用说明.md` 第 3 节补上 `uv sync`、`npm ci` 的实测结果。

**Done When**：`uv run pytest backend/tests -q` = 0；`npm --prefix app run test` = 0；`npm --prefix app run build` = 0；`cargo check --manifest-path app/src-tauri/Cargo.toml` = 0；`npm --prefix app run lint:design` = 0；`git cat-file -t d060dfb` 输出 `commit`（证明上游历史保留）；推送后 CI 为绿。

### M1 上游 VRA 的 Windows 兼容（分支 `m1-windows-portability`）

已知失败（2026-09-25 在本机 Windows 上运行：196 通过、45 失败）：
- 约 33 处读写文件没有指定编码（中文 Windows 默认 GBK）；
- `execution.py` 使用了 POSIX 专有的 `os.killpg` 和 `start_new_session`；
- 使用 `zoneinfo` 但没有声明 `tzdata` 依赖（Windows 没有系统时区库）；
- 部分测试把 shell 脚本当作可执行文件（`WinError 193`）；
- 图片相关测试缺少 Playwright 浏览器（属于环境问题，补装即可）。

这里的「红」就是上游现有的失败测试：先运行一次 D1 命令，保存失败清单，然后逐类修复。修改内容限于附录 A 的 V1。**不允许**为了通过而削弱断言；测试替身改成跨平台写法（例如用 Python 脚本代替 shell 脚本）。

**Done When**：D1 = 0；附录 A 已登记全部修改；`uv run --directory vendor/video-report-agent ruff check src tests` 的错误数不多于修改前的 7 个。

### M2 后端核心：库、队列、设置（分支 `m2-backend-core`）

先写的测试（每项都要先红）：
- 数据目录布局的创建；表结构与 `schema_version`；
- 新建条目：成功 201，重复 409，链接不支持 422；
- 分类：改名、重名 409、合并、删除非空分类 409、`count` 只统计 done 条目；
- 鉴权：401；`?token=` 只对内容类 GET 接口有效；数据目录未设置时返回 409 `DATA_DIR_NOT_SET`，设置后无需重启即可使用；CORS 只放行第 8.1 节列出的来源；
- 队列：两个条目时第二个保持 queued，直到第一个结束；取消；启动时把 running 改为 interrupted；
- 设置：保存、读取、Key 掩码；首次运行复制 `models.json`；`custom` 提供商写入 `models.json`；`asr.backend='cloud'` 且 Key 为空时返回 422 `DASHSCOPE_KEY_REQUIRED`；切换 `asr.backend` 后已保存的 Key 仍在；`asr.backend` 只接受 `local` / `cloud`；
- 假流水线（`PROMETHEUS_FAKE=1`）：用 `backend/tests/fixtures/` 里的现成报告、导图、字幕，在 3 秒内完成全部阶段。报告夹具使用 `vendor/video-report-agent/docs/examples/report.html`。

**Done When**：D2 的两条命令 = 0，并且上面每一项都有对应测试。

### M3 导入、转写、字幕（分支 `m3-ingest-transcribe-subtitle`）

先写的测试：
- 第 8.4 节链接表中的每一行；
- 5 小时时长可以入队；Pi 超时公式（0.5 小时 → 2400 秒，3 小时 → 3600 秒，10 小时 → 7800 秒）；
- 未配置 cookies 时 YouTube 立即报 `YOUTUBE_COOKIES_REQUIRED`；yt-dlp 抛出 "Sign in to confirm" 时映射为同一个错误码；
- `AsrRun` 转换（用伪造的 faster-whisper 分段）；设备选择逻辑（用桩函数模拟有 / 没有 CUDA 设备）；中文时传 `language="zh"` 和 `initial_prompt`，其他语言不传 `initial_prompt`；
- 本地转写在子进程中运行，取消任务会结束该子进程（用一个会一直等待的假子进程测试）；环境变量 `ASR_BACKEND=mlx` 不影响本地路径；
- SRT / TXT 格式（包含超过 1 小时的时间戳）；中文字幕做繁→简转换（例如「這個視頻」→「这个视频」），非中文字幕不变；
- `transcript.md` 的格式与 vendor 一致（黄金文件比对）。

live 测试（`-m live`）：一个 5–10 分钟的公开 B 站视频（选定后写进 `docs/acceptance.md`），用云端和本地转写各跑到 `transcript.md`；一个 YouTube 视频（cookies 路径通过环境变量 `PROMETHEUS_TEST_YT_COOKIES` 提供，缺少时停下来向用户要）。

**Done When**：D2 = 0；`uv run pytest backend/tests/live/test_ingest_live.py -m live -q` = 0。

### M4 精读报告与自动分类（分支 `m4-report`）

1. **先做探针**：在一份真实的转写上，用 `--tools read,write,edit,powershell` 手动跑一次 Pi，确认 Agent 能用 PowerShell 执行 Python 绘图脚本。把结论写进 DECISIONS（这是探针，代码不保留）。
2. vendor 修改 V2（`PiRunner` 增加参数）和 V3（`pipeline.py` 延迟导入 `report_image`），并配测试：默认参数下生成的命令与修改前完全相同；传入 `agent_dir` 后不再使用当前工作目录。
3. 先写的测试：工作区文件与 `input.json` 字段；生成的 Pi 命令以 `node.exe` 和 `cli.js` 开头（不是 `pi.cmd`）、包含 `powershell`、不包含 `bash`、只提供 standard 模式；超时参数；一次性文本调用把提示词写进标准输入而不是命令行参数，并带齐那组 `--no-*` 参数（用一段超过 9000 字的提示词验证）；定稿后的检查项（外部引用检测、`<h1>` 提取、简介占位符不残留）；分类的解析、校验和回退到「未分类」。

**Done When**：D2 = 0；`uv run pytest backend/tests/live/test_report_live.py -m live -q` = 0，该测试断言：M3 那个短视频的报告存在，`data-source-units` ≥ 10，有 `section-time`，题头包含「Bilibili；」，没有外部资源引用，并且已归入某个分类。

### M5 配图（分支 `m5-figures`）

先写的测试：候选帧筛选函数（间隔、每小时上限、总上限、均匀补帧）；`showinfo` 输出解析；`--list-models` 输出的能力解析；定稿时的图片内联（不残留非 data 的 `img src`）与样式注入；只有开了配图时才附加 `figures.md` 和相应提示。

然后编写 `report/overlays/figures.md` 的正式文本，以及 `scripts/acceptance/ab-figures.ps1`：取一个已完成条目的 `transcript.md`，在两个全新的工作区里分别生成 A（原版）和 B（原版 + 配图），输出到 `acceptance-output/ab-<日期>/`，并对两份都运行 vendor 的 `inspect_report`。

**Done When**：D2 = 0；`ab-figures.ps1` = 0；**停下来请用户阅读 A/B 两份报告**，把用户结论记入 `docs/acceptance.md`（D6）。用户不认可时，按用户意见修改 `figures.md`，再重新做 A/B。

### M6 思维导图（分支 `m6-mindmap`）

先写的测试：用 `vendor/video-report-agent/docs/examples/report.html` 做大纲提取（标题层级和 `section-time`）；导图校验规则（一级分支数量、深度、节点长度、链接）；两个平台的时刻链接；失败重试一次，之后记为 `mindmap_status='failed'`。

**Done When**：D2 = 0；`uv run pytest backend/tests/live/test_mindmap_live.py -m live -q` = 0（针对 M4 生成的条目）。

### M7 前端（分支 `m7-frontend`）

先写的测试（Vitest）：侧栏的顺序；`LibraryBrowser` 三级切换与面包屑；三个页签共享当前条目状态；字幕时间格式和时刻链接；设置表单校验；转写方式切换时各输入框和按钮的 `disabled` 状态，以及切换后已填内容保留。然后写 E2E（Playwright，后端用假流水线，前端 `VITE_E2E=1`）覆盖 D3 的 ①–⑦（E2E 的后端由 `playwright.config.ts` 的 `webServer` 启动：`uv run python -m prometheus.server --port 8765 --token e2e --config-dir <临时目录>`，并设置 `PROMETHEUS_FAKE=1`、`PROMETHEUS_TEST_DATA_DIR=<临时目录>`；前端的 `platform.backendInfo()` 在 E2E 模式下返回这个固定端口和 token），并把五个页面的截图保存到 `docs/screenshots/`。之后接入 Tauri：后端进程的启动与关闭、`backend_info`、`platform.ts`。

**Done When**：D3、D4 的命令 = 0；`npm --prefix app run tauri dev` 能打开窗口并显示控制台（附一张截图）；**停下来请用户查看截图**，把结论记入 `docs/acceptance.md`（D4）。

### M8 打包（分支 `m8-packaging`）

实现第 10 节的 `scripts/package.ps1`，以及 `scripts/acceptance/installed-smoke.ps1`：
- 安装：`<安装包> /S /D=<临时目录>`；
- 启动时设置环境变量 `PROMETHEUS_TEST_DATA_DIR`，跳过数据目录选择；
- 轮询 `/api/health`（端口由后端写入 `<数据目录>/logs/backend.port` 供脚本读取）；
- 关闭程序，运行 `<临时目录>\uninstall.exe /S`，确认数据目录仍然存在。

**Done When**：D8 = 0；安装包已复制到 `E:\tools\Prometheus-Desktop\release\`；使用说明第 3 节已补上 `tauri build` 的实测结果。

### M9 真实链路验收（分支 `m9-acceptance`）

1. 选一个公开、时长 2 小时 50 分到 3 小时 10 分、以讲解为主的 B 站视频，把 BV 号写进 `docs/acceptance.md`，之后不再更换。
2. `scripts/acceptance/live.ps1` 用安装后的程序（或开发版后端）依次运行三种组合：云端转写不配图、本地转写不配图、云端转写配图。逐项断言 D5 的产物条件，并从 `run.trace.jsonl` 计算耗时。
3. 用一个 YouTube 视频跑 D7；运行 `local-asr.ps1` 验证 D9。
4. 需要的 Key 和 cookies 通过环境变量提供：`PROMETHEUS_TEST_LLM_KEY`、`DASHSCOPE_API_KEY`、`PROMETHEUS_TEST_YT_COOKIES`。缺少时停下来向用户要。
5. 全部通过后更新 README，打标签 `v0.1.0` 并推送。

**Done When**：D5、D7、D9、D10 全部满足，结果（包括每种组合的耗时）记入 `docs/acceptance.md`。

## 13. 进度记录

| 里程碑 | 状态 | 完成日期 | 合并 commit | Done When 结果（命令 = 退出码） |
|---|---|---|---|---|
| M0 仓库骨架 | 完成 | 2026-09-25 | f1ac34c | `uv run pytest backend/tests -q` = 0；`npm --prefix app run test` = 0；`npm --prefix app run build` = 0；`cargo check --manifest-path app/src-tauri/Cargo.toml` = 0；`npm --prefix app run lint:design` = 0；`git cat-file -t d060dfb` = `commit`；CI 绿（windows-latest，run 36188439025） |
| M1 Windows 兼容 | 完成 | 2026-09-25 | 32b41d8（merge） | D1：`uv run --package video-report-agent --extra enhancement --directory vendor/video-report-agent pytest -q` = 0（241 passed；基线 29 failed / 212 passed）；`uv run --directory vendor/video-report-agent ruff check src tests` = 5 个错误 ≤ 基线 7 个；附录 A V1 已登记；Playwright 浏览器补装到 chromium-1243（环境问题，不改代码） |
| M2 后端核心 | 完成 | 2026-09-25 | 949dc07（merge） | D2：`uv run pytest backend/tests -q -m "not live"` = 0（46 passed）；`uv run ruff check backend` = 0；M2 测试清单（数据目录布局、表结构、条目 201/409/422、分类、鉴权/门控/CORS、队列串行/取消/interrupted、设置/掩码/models.json、假流水线 3 秒内完成）全部在 backend/tests 有对应用例，先红（ac2bd1a，36 失败）后绿（a997553） |
| M3 导入/转写/字幕 | 完成（云端 live 按用户指示暂缓） | 2026-09-25 | c5f1db5（merge） | D2：`uv run pytest backend/tests -q -m "not live"` = 0（95 passed）；`uv run ruff check backend` = 0；live：`uv run pytest backend/tests/live/test_ingest_live.py -m live -q` = 0（**2 passed 1 skipped**：B 站本地转写 device=cuda 86 段；YouTube cookies 链路本地转写 en 5 段；云端 paraformer 项按用户指示「那个云端先暂时不弄」挂起，待 DashScope Key 补跑）；红绿提交 511f3ae/8eb05d5 → ce6f213 等；链接解析表/超时公式/cookies 门控/AsrRun/子进程取消/繁简转换/黄金文件测试齐全 |
| M4 精读与分类 | 完成 | 2026-09-26 | fb50048（merge） | D2：offline pytest = 0（120 passed）、ruff = 0；探针：PowerShell 工具执行 matplotlib 绘图成功（chart.png 45,578 字节，DECISIONS D-26）；live：`test_report_live` = 0（11 分钟，BV1bZhQ6VEQK 经 custom 供应商 gpt-6-sol：data-source-units=25、section-time=9、题头含「Bilibili；」、无外部引用、无占位符残留、自动分类「战争伦理」）；红绿提交 e6a09e9 → de96ae9/169839d → d232d9f |
| M5 配图 | 进行中（代码完成；live trial 受阻，详见 acceptance.md） | 2026-09-26 | — | 代码全部落地并有测试：抽帧筛选（20 秒间隔/每小时 20 帧/总 80 帧/稀疏补帧，5 用例）、showinfo 解析、figures.md 正式规则、frames 阶段接入流水线、figures 旗标贯通报告阶段、定稿 base64 内联；真实视频抽帧实证（BV1bZhQ6VEQK 保留 20 帧候选）。**未做**：带配图的完整报告 live trial 与 A/B——中转站 oapi.firedog.dev 对图片输入返回 SUBSCRIPTION_NOT_FOUND（订阅不含多模态），venlacy.dev 分组无可用通道；解除条件：支持看图的供应商（如 DeepSeek 官方 deepseek-flash）+ 用户 A/B 签字（D6） |
| M6 思维导图 | 完成（随 M4 分支落地，见 DECISIONS） | 2026-09-26 | 同 M4 | 离线：大纲提取（vendor 示例 9 章）/校验规则/两平台时刻链接测试全绿；live：报告导图 7 分支、7 个时刻链接、mindmap_status=ok（并入 test_report_live 验证）；Vendor 示例与黄金链路复用 |
| M7 前端 | 完成（D4 极简判定待用户查看截图） | 2026-09-26 | 387a7eb（merge） | D3：E2E ①–⑦ 全部通过（app/e2e/d3.spec.ts + app.smoke.spec.ts，7 用例；含跨页签一致性、报告 iframe/导图 SVG/字幕行、设置持久化、转写切换禁用规则、外链拦截）；`npm --prefix app run build` = 0；`npm --prefix app run test`（Vitest）与 `lint:design` = 0；运行中发现并修复 CORS 预检被鉴权中间件拦截的生产 bug（3fdc15b）；D4：截图 docs/screenshots/console.png、report.png 待用户判定 |
| M8 打包 | 完成（D9 长视频本地转写验收顺延至 M9 一并执行） | 2026-09-26 | 9e188d6（merge） | `scripts/package.ps1` = 0（一键全流程，含打包资产校验与 300MB 体积断言）；NSIS 安装包 `Prometheus_0.1.0_x64-setup.exe` = **165MB**，已复制到 `E:\tools\Prometheus-Desktop\release`；D8：`scripts/acceptance/installed-smoke.ps1` = 0（静默安装 → 启动 → backend.port 轮询 /api/health 30 秒内 healthy → 静默卸载 → 数据目录保留）；Rust 壳实现后端进程启动/关闭 + backend_info + CREATE_NO_WINDOW；使用说明第 3 节已补 tauri build 实测 |
| M9 真实验收 | 进行中（本地免费路径已实证；两项受阻，详见 acceptance.md） | 2026-09-26 | — | 已实证：本地转写（8 分钟样本 86 段 device=cuda；104 分钟样本 3716 段 GPU 6.4 分钟）、报告/分类/导图链路（BV1bZhQ6VEQK 全断言通过）、165MB 安装包 + D8 安装冒烟。**未做**：① 云端转写组合与 D5 云端断言——等 DashScope Key（用户指示先不弄）；② D5 约 3 小时样本视频选定——B 站搜索/空间接口持续风控（cookies 亦 1–2 次即封），热门榜 300 条无命中，需用户提供 BV 号或换时段重搜；③ scripts/acceptance/live.ps1 驱动脚本待写（各阶段已有 live 级实证） |

## 14. 风险与对策

| 风险 | 对策 |
|---|---|
| Pi 的 PowerShell 工具与 bash 行为不同，影响精读模式的绘图 | M4 先做探针；不行就停下来问用户（可选方案：随包附带 Git Bash，或者关闭执行工具） |
| YouTube cookies 过期、账号被风控 | 报错时明确提示重新导出 cookies；建议使用小号 |
| B 站风控（HTTP 412） | 指数退避重试 3 次；仍然失败就提示稍后再试 |
| CUDA DLL 与 ctranslate2 版本不匹配 | 由 D9 发现；把 cuDNN 回退到与 ctranslate2 4.8.2 发布说明一致的 9.x 版本，并记入 DECISIONS |
| 配图拉低文字质量 | D6 把关；用户不认可就改规则；配图可以按条目关闭 |
| 超长视频的 Agent 上下文 | `deepseek-flash` 有 1M 上下文；自定义模型上下文不足时，由 Pi 自动压缩，并在任务上提示可能影响质量 |
| 安装包超过 300MB | 先检查 pi 的 `node_modules` 和 Python 的 `site-packages` 中可以删除的部分；仍然超出就停下来问用户 |
| 任务运行时弹出黑色控制台窗口 | 后端以 `CREATE_NO_WINDOW` 启动，子进程会继承隐藏的控制台；M7 用 `tauri dev`、M8 用安装版各跑一个真实任务，人工确认没有弹窗，有的话给后端发起的子进程也加上这个标志 |
| 转写内容里的恶意指令（Agent 能执行命令） | 追加系统提示，把素材声明为数据；限定工作目录；不向 Pi 传递 API Key 以外的密钥。用户已接受残余风险（D-05） |
| 上游 VRA 以后更新 Skill | `git subtree pull` 后重跑 D1、D2、D6 |

---

## 15. 第二阶段（2026-09-26 起）

> 起因：2026-09-26 的审查（`docs/REVIEW-2026-09-26.md`）发现，通过流水线真实运行时多个阶段必崩；前端基本没有设计；数据目录用户无法浏览。第二阶段的规格已由用户确认（2026-09-26）。第 1–14 节中与本节冲突之处，以本节为准。

### 15.1 Goal

把 Prometheus 修到**通过界面真正可用**；前端按 C 方向（液态玻璃）从零重写；知识库改成人和 AI 都能直接读的文件夹结构；用实测数据选定转写引擎。

### 15.2 Boundaries

**做：**

1. **修完审查问题**（REVIEW 第 5–17 项）：
   - 取消任务时结束整个子进程树；
   - 安装版只用自带运行时（后端使用 `--runtime-dir`，删除写死的开发机路径）；
   - 内置提供商（如 `deepseek-flash`）的看图能力按 `--list-models` 判断；
   - 「测试模型」列模型时带上 `PI_CODING_AGENT_DIR`；
   - 每个阶段写入 `run.trace.jsonl`；
   - 失败时给出中文处理建议；
   - D1 不依赖 `PYTHONUTF8`；
   - 任务成功后清理中间文件（见 15.4.1）。
2. **模型协议**：自定义提供商增加 `protocol`，取值 `openai`（写入 `api: openai-completions`）或 `anthropic`（写入 `api: anthropic-messages`，`baseUrl` 去掉末尾的 `/v1`）。
3. **后端架构**：
   - 导图 → `prometheus/mindmap/`；配图 → `prometheus/figures/`；一次性模型调用、模型能力查询、`models.json` 生成 → `prometheus/llm/`；
   - `tasks/stages.py` 只负责按阶段调用各功能模块，不再包含提示词拼装、重试等功能逻辑。
4. **知识库存储**：可读文件夹 + PDC 式 AI 索引（见 15.4.1）。分类阶段同时生成 3–5 个标签和一句话摘要。在软件里改名、移动条目、合并分类时，同步移动对应的文件夹。旧版数据目录自动迁移。
5. **思维导图改为 BiliSum 式知识树**（见 15.4.2）：分层 JSON，节点带摘要和时间锚点；前端用 React Flow 画布；同时导出 `思维导图.md`。
6. **转写实测**（见 15.4.3）：结果交用户拍板，再接入选定的本地引擎。
7. **云端转写 = 必剪**（见 15.4.4）：
   - 不需要任何配置，用户选了「云端」即可使用；
   - 失败时自动退回本地转写；
   - 删除 DashScope 相关的设置项和界面（vendor 的 paraformer 代码保持不动）。
8. **前端从零重写**（见 15.4.5），不在旧界面代码上修补，后端接口契约保持兼容。
9. **README**：写明技术栈、特色、使用与部署步骤，以及从 VRA 和 BiliSum 各取了什么。
10. **本地转写 = 中文 FunASR + 其他语言 faster-whisper**（用户 2026-09-27 看过 R5 实测后选定，D-35；FunASR 用 ONNX 版在 CPU 上运行，D-39，见 15.4.4）。
11. **平台人工字幕优先**（用户 2026-09-27 同意，借鉴 BiliSum）：YouTube 视频带有作者上传的原语言人工字幕时，直接使用，跳过转写（见 15.4.4）。B 站字幕需要登录 cookie，本阶段不做。
12. **字幕纠错**（用户 2026-09-27 同意，见 15.4.6）：精读完成后，用用户配置的同一个模型，按上下文并参考报告，改正字幕里的识别错字，同时补全标点；字幕页默认显示纠错版，可以切换回原始识别。
13. **阅读体验与模型设置**（用户 2026-09-27 看过 R7 后提出，见 15.4.7、15.4.8）：报告目录按钮、图片点击放大、侧栏收成图标窄条、正文缩放；模型设置改为可保存多份配置并一键切换，能获取模型列表。
14. **内容增强**（用户 2026-09-27 提出，见 15.4.9）：导图要点带 2–4 句详解并能跳到精读对应章节；非中文视频的字幕中外对照；英文字幕悬停查词；云端转写可接自定义的 OpenAI 兼容接口。
15. **界面修改第二轮**（用户 2026-09-27 提出，见 15.4.10）：分类可新建、改名、删除、拖拽归类，三个页签与知识库文件夹同步；设置页修复与常用供应商、思考强度六档、模型参数补齐；字幕合并成 10–15 秒一段；旧条目补标签；精读正文随窗口加宽；查词加英英释义。
16. **精读完整度**（用户 2026-09-27 提出，见 15.4.11）：「完整」模式用要点账本、分章写作、逐章检查与反馈、讲解审校，让精读覆盖来源里每一个有实质内容的点；用闭卷问答和忠实度抽检评测。

**明确不做：** 浅色/深色主题切换（全局只有 C 的墨夜外壳，报告保持浅色纸页）、问答 / RAG、阿里云与 Groq 云端、说话人区分、在资源管理器里手动挪动文件夹后的自动同步（软件只提示「文件缺失」，提供「删除记录」和「重新生成」两个操作）；引入 LangChain / LangGraph / LlamaIndex / DeepEval / RAGAS、向量检索、多份候选择优、DSPy 自动调提示词（理由见 15.4.11）；在软件里抓取剑桥、牛津的释义（它们没有免费接口，只提供在浏览器打开的按钮）；常用供应商里收录带返利链接的中转站。

### 15.3 Done When

命令默认在已执行 `env.ps1` 的 PowerShell 中、于仓库根目录运行，以退出码 0 为通过。

| # | 判据 | 判定 |
|---|---|---|
| **E1** | 后端全部测试通过；每个修复都有先失败的测试；**每个流水线阶段都有按 `StageContext` 调用的测试**（`test_stage_wiring.py` 一类） | `uv run pytest backend/tests -q -m "not live"`；`uv run ruff check backend` |
| **E2** | D1 在**没有**设置 `PYTHONUTF8` 的新终端中通过 | `uv run --package video-report-agent --extra enhancement --directory vendor/video-report-agent pytest -q` |
| **E3** | 真实跑完 `BV1yPb46xExH`（开启配图、本地转写，模型用用户提供的 API）：<br>① 知识库文件夹里有精读.html、精读.md（带 title/date/category/tags/description 的开头）、思维导图.md、字幕.srt、字幕.txt、来源.url；<br>② `index.json` 和 `llms.txt` 包含该条目；<br>③ `mindmap.json` 通过校验（3–6 个主题，叶子都有时间）；<br>④ `run.trace.jsonl` 覆盖全部阶段；<br>⑤ 清理后，该条目的知识库文件夹 + 缓存 ≤ 5MB | `scripts/acceptance/live.ps1 -Url https://www.bilibili.com/video/BV1yPb46xExH/`（会产生 API 费用，手动触发） |
| **E4** | 报告阶段进行中取消任务，5 秒内不再有该任务的 Pi / ffmpeg / 转写进程，状态为 `cancelled` | live 测试 `test_cancel_live.py` |
| **E5** | 转写实测表（4 个引擎 × 中英两段样本：字错率/词错率、速度、峰值显存、时间戳、标点） | `docs/asr-bench.md`；**由用户看表后决定默认引擎** |
| **E6** | 前端单测 + E2E 一条命令跑完，E2E 自动拉起假流水线后端和 Vite。断言：<br>① 侧栏五项顺序；<br>② 在某个页签里打开条目后，侧栏高亮**停留在该页签**；<br>③ 知识库、思维导图、字幕三个页签的分类和条目标题完全一致；<br>④ 导图画布渲染出节点，点节点出现摘要面板；<br>⑤ 字幕页按时间顺序列出**全部**分段，默认显示纠错版，可切换原始识别；<br>⑥ 外链交给 `openExternal`；<br>⑦ 设置里选「云端」无需填写任何 Key 即可保存；<br>⑧ 自定义提供商可选 OpenAI / Anthropic 协议 | `npm --prefix app run test`；`npm --prefix app run e2e`；`npm --prefix app run lint:design` |
| **E7** | 界面观感与动效：侧栏不遮挡内容，滚动条滚动时显现、静止时淡出，页面切换顺滑，报告阅读舒适 | **用户看截图并实际试用安装版后判定**，记入 `docs/acceptance.md` |
| **E8** | 安装包 ≤ 300MB；安装版在**禁止使用开发机工具路径**的条件下（设 `PROMETHEUS_FORBID_DEV_PATHS=1`，后端只要解析到安装目录以外的 node / pi / ffmpeg / python 就立即报错）完整处理一个短视频 | `scripts/acceptance/installed-live.ps1` |
| **E9** | README 按 15.2 第 9 条更新；远程 `main` 与本地一致；CI 为绿 | `git fetch origin; git rev-parse main origin/main`；CI 状态 |
| **E10** | 字幕纠错实测：对 R5 中文样本的 faster-whisper 结果和必剪结果分别纠错，以作者的人工字幕为参考：<br>① 纠错后的字错率**低于**纠错前；<br>② 分段数和每段的起止时间不变；<br>③ 必剪结果纠错后，标点 ≥ 每 100 字 5 个 | live 测试 `test_subtitle_fix_live.py`（会产生 API 费用，手动触发） |
| **E11** | R7b（阅读与设置）端到端：<br>① 阅读工具栏「目录」列出报告各章，点击后报告滚动到该章；<br>② 点击报告图片出现放大层，滚轮缩放，Esc 或点击图片外关闭；<br>③ 按钮或 Ctrl+B 把侧栏收成图标窄条，窄条图标仍能切换页签，重新打开后保持收起状态；<br>④ 正文缩放改变报告字号，重新打开后保持；<br>⑤ 设置里新增两份模型配置并切换当前配置；API Key 的眼睛图标切换明文；「获取模型列表」（假接口）后出现可选模型；思考强度默认「中」；<br>后端：两种协议的模型列表接口、旧设置迁移为一份配置，均有单测 | `npm --prefix app run e2e`；`uv run pytest backend/tests -q -m "not live"` |
| **E12** | R7c（内容增强）：<br>① 导图填充的检索、校验、重写与评测指标、字幕翻译的生成与校验、双语导出、查词（含词形还原）、自定义云端转写（假接口，含切块与失败退回本地）均有单测；<br>② 端到端：导图面板显示详解并能跳到精读对应章节；英文条目的字幕每段下方显示中文；悬停英文单词出现查词浮窗；<br>③ live：一段英文 YouTube 样本得到中文精读和中英对照字幕；<br>④ 导图实测（用户的 API，两篇真实报告）：leaf 的 detail 覆盖率 ≥ 90%，平均依据率 ≥ 0.4，各层平均字数由内向外递增，结果写进 `docs/mindmap-eval.md` | `uv run pytest backend/tests -q -m "not live"`；`npm --prefix app run e2e`；live 测试（会产生 API 费用，手动触发） |
| **E13** | R7d（界面修改第二轮，15.4.10）：<br>① 后端单测：新建分类（201 / 重名 409 / 空名 422）；删除非空分类带 `move_items=1` 时条目与文件夹移到「未分类」、不带时 409；重新生成保留分类、只更新标签和摘要；模型列表失败时返回状态码与原因、OpenAI 协议 404 时改试 `/v1/models`、请求带 User-Agent；Key 留空不修改；`reveal-key` 只返回所指配置的完整 Key（未知配置 404）；`models.json` 补齐模型参数（claude-opus-4-8 → 上下文 1000000、输出 128000、自适应思考、xhigh/max 两档；目录里没有的模型不写）；字幕合并规则（不丢字、不超过 15 秒、起止时间单调）与旧条目转换（重复执行结果不变）；补全标签不改分类；词库导入保留英英释义；失败原因的判定（每一类至少一段真实格式的报错样本）与失败时保留阶段；<br>② 端到端：假流水线模拟「下载」阶段的 412 风控，控制台那一行显示「在「下载」这一步失败」、原因、「怎么办」，「详情」里有原始报错；用「+」新建分类，在知识库把一个条目拖进去，切到思维导图和字幕页签，该条目都在新分类下；改名后三个页签和阅读页面包屑都显示新名；分类行有「✎」「🗑」按钮，删除非空分类后其条目出现在「未分类」；阅读页「⋯ → 移到…」可用，且原来的下拉框不存在；设置里的下拉框外框与按钮边界重合（只有一层边框）；点「Kimi」后接口地址和协议自动填好；DeepSeek 预设也有「获取 API Key ↗」；已保存 Key 的配置点眼睛后框里显示完整 Key；思考强度可选「超高」「最高」；字幕页没有超过 15 秒的段落；窗口 1600px 宽时报告纸面宽于 1000px、报告自带目录不显示；查词浮窗显示英英释义；<br>③ 截图放 `docs/screenshots/r7d/`，**停下来请用户看**，结论记入 `docs/acceptance.md` | `uv run pytest backend/tests -q -m "not live"`；`uv run ruff check backend scripts`；`npm --prefix app run test`；`npm --prefix app run e2e`；`npm --prefix app run lint:design`；在 `app/` 下 `npx tsc --noEmit`；用户判定 |
| **E14** | R7e（精读完整度，15.4.11）：<br>① 离线单测：转写切块；要点校验（锚点、单元归属、两级覆盖的第一级与重问）；规划校验（归属、跳过理由、「重复」指向、跳过过多时复核）；逐章检查（`data-points` 覆盖、依据率、照抄比例、每个要点的隐藏篇幅检查）与反馈生成；提示词和反馈里不出现字数；审校两步的清单校验；拼装（占位符全部填写、章节顺序、目录、补充说明样式、通过 finalize 的检查）；分章运行器的 Pi 命令参数与 vendor PiRunner 一致；各环节轮次上限；`coverage.json`；评测打分；「标准」模式不经过新流程；<br>② live（用户的模型，会产生费用，预算约 60–80 美元，2026-09-28 由 25–45 上调）：先测三篇旧报告的基线；卡巴拉（104 分钟）与英文学习视频（19 分钟）用「完整」模式重新生成，每篇都满足：要点覆盖率 ≥ 95%（只认 `data-points`，不算合法跳过）；时间覆盖 ≥ 90% 且最长漏写 ≤ 2 分钟（不算跳过段）；闭卷问答得分 ≥ 80%，且比旧报告至少高 20 个百分点或达到 95%；忠实度抽检「无依据」≤ 5%；补充说明与视频内容矛盾 0 条；图示、配图、表格、卡片等组件总数不少于旧报告。结果写进 `docs/report-eval.md`。**未达标时停下来向用户报告，不自行降低门槛**；<br>③ 用户并排阅读新旧报告并签字，记入 `docs/acceptance.md` | `uv run pytest backend/tests -q -m "not live"`；`uv run ruff check backend scripts`；live 测试与 `scripts/report-eval/`（手动触发）；用户判定 |

### 15.4 设计细节

#### 15.4.1 知识库存储（PDC 式）

```
<知识库文件夹>\                         首次启动时选择
├── llms.txt                           全库概览：简介、分类列表（名称、条目数、索引路径）、给 AI 的阅读说明
├── index.json                         {"generated_at", "items": [{"id","title","category","tags","description","date",
│                                        "source": {"platform","url","uploader","title","duration_s"},
│                                        "paths": {"html","md","mindmap","srt","txt"}}]}
├── <分类>\
│   ├── _index.md                      该分类全部条目：标题、日期、摘要、相对链接
│   └── <YYYY-MM-DD> <报告标题>\
│       ├── 精读.html                  给人看（配图已内联）
│       ├── 精读.md                    给 AI 读：YAML 开头（title/date/category/tags/description/source_url/platform/uploader/duration_s）
│       │                              + 由 HTML 转出的正文（标题层级、段落、列表、表格、图注；不含 base64 图片）
│       ├── 思维导图.md                由 mindmap.json 转出的大纲（节点摘要、时刻链接）
│       ├── 字幕.srt
│       ├── 字幕.txt
│       └── 来源.url                   [InternetShortcut] URL=<原视频>
└── .prometheus\                       设置 Windows「隐藏」属性
    ├── prometheus.db  config\  logs\  runtime\cuda\  models\
    └── cache\<条目ID>\                asr.json、transcript.md、canonical-transcript.jsonl、input.json、source.info.json、
                                       segments.json、mindmap.json、run.trace.jsonl（长期保留，用于重新生成）
```

- 文件夹命名：日期取任务完成当天（本地时区）；标题取报告 `<h1>`。`<>:"/\|?*` 替换为全角字符，去掉首尾空格和末尾的点，超过 60 个字符截断并加「…」；同名时追加「 (2)」「 (3)」。分类文件夹同样处理，默认分类名为「未分类」。
- 数据库保存每个条目的相对路径；只有 `done` 状态的条目才有知识库文件夹。
- **清理**：任务成功后删除缓存里的音视频、`audio.wav`、`frames\`、`sessions\`、`pi.events.jsonl` 和 Skill 副本；失败时保留，供排查，下次成功或删除条目时再清理。
- 每次条目完成、改名、移动或删除后，重写 `llms.txt`、`index.json` 和受影响分类的 `_index.md`。
- **旧版迁移**：检测到数据目录根部有 `prometheus.db` 和 `items\` 时，把内部数据移入 `.prometheus\`，把 `done` 条目转换成新的文件夹结构，把 `items\<ID>\work` 移到 `cache\<ID>`。迁移要可重入，中途失败后再次启动能够继续。

#### 15.4.2 思维导图（参考 BiliSum 的写作与呈现思路）

- **输入**：报告大纲（标题、导语、各章 `<h2>` 及 `section-time`、`<h3>`、段落正文）。
- **输出 JSON**（`cache\<ID>\mindmap.json`）：`{"title", "root": Node}`，`Node = {"label", "type": "root|theme|topic|leaf", "summary", "time", "children"}`：
  - `label` ≤ 20 字，`summary` ≤ 60 字，直接写信息本体；
  - 叶子节点必须有 `time`（秒，并落在某一章的时间范围内），其他层级可以没有；
  - 最深 4 层（root → theme → topic → leaf）。
- **写作规则**（改写自 BiliSum 的提示词）：
  - 先做语义归纳，不要把章节原样平移成节点；
  - theme 3–6 个，彼此区分明显，按「概念 / 方法 / 例子 / 条件 / 结论」这类知识结构组织，评论或资讯类则按观点和因果；
  - topic 只在某个 theme 下确实有不同子议题时才出现；
  - 叶子要具体、短、一眼能懂；
  - 覆盖所有章节，但合并重复内容；
  - 只输出 JSON。
- **校验**（确定性）：
  - 容忍模型在 JSON 前后附带说明文字，也容忍代码围栏，只取第一个完整的 JSON 对象；
  - 检查类型、层级、数量、字数、叶子时间；
  - 至少 80% 的章节被某个叶子时间覆盖。
- 校验失败时带上错误说明重试一次；仍然失败则记 `mindmap_status='failed'`，界面提供「重新生成导图」。
- **呈现**：
  - `@xyflow/react` 画布，自写的横向整齐树布局（参照 BiliSum `layoutMindMap` 的思路）；
  - 节点卡片按类型区分样式，主题节点可以折叠 / 展开；
  - 支持缩放、拖动、「适应画布」；
  - 点节点弹出摘要面板，面板里的时刻链接交给 `openExternal`；
  - 右上角「导出 .md」。

#### 15.4.3 转写实测

- 实测环境放在 `E:\tools\Prometheus-Desktop\asr-bench\`（独立虚拟环境 + 模型缓存），配使用说明，不进入安装包。
- **样本**：
  - 一段 5–15 分钟、带**人工中文字幕**（非自动生成）的普通话视频；
  - 一段 5–15 分钟、带人工英文字幕的英文视频（YouTube，cookies 路径由用户提供）；
  - 选定后写进 `docs/acceptance.md`。
- **参赛**：faster-whisper large-v3-turbo（现用）、Qwen3-ASR-1.7B（+ Qwen3-ForcedAligner 出时间戳）、FunASR paraformer-zh + fsmn-vad + ct-punc、必剪。时间允许时加测 Fun-ASR-Nano。
- **指标**：
  - 中文字错率：去掉标点和空白、繁转简后计算；阿拉伯数字与中文数字的写法差异单独统计，不计入错误；
  - 英文词错率：转小写、去标点后计算；
  - 另记：处理时间 / 音频时长、峰值显存（nvidia-smi 采样）、时间戳粒度、有无标点、安装体积。
- **产物**：`docs/asr-bench.md`（汇总表 + 典型错误摘录）；原始输出放 `acceptance-output/asr-bench/`（不提交）。

#### 15.4.4 转写：云端必剪、本地 FunASR / whisper、平台人工字幕

- `transcribe/bcut.py`：
  - 流程：上传授权 → 分片上传 → 提交 → 建任务 → 轮询；请求头参照 VideoCaptioner 的维护版实现（2026-09-26 实测：原版 bcut-asr 返回 412，改用维护版请求头后可用）；
  - 输入：由 ffmpeg 转成 16kHz 单声道 48kbps 的 mp3；
  - 输出：转成 vendor 的 `AsrRun` 结构（utterance 级时间戳）。
- 遇到 412 / 429、超时，或任务状态为错误时，**自动改用本地转写**，并在条目上记一条提示「必剪不可用，已改用本地转写」。
- 设置项 `asr.backend`：`local` | `cloud`；选 `cloud` 时不需要任何配置。
- 必剪的代码按接口流程自行编写，不复制 VideoCaptioner 的代码（它是 GPL，本仓库是 MIT）。

**本地转写（D-35、D-39，2026-09-27 补充）**

- **语言判断**：用 faster-whisper 的 `detect_language` 检测音频语言（有 CUDA 用 GPU，否则用 CPU int8）。`zh` 走 FunASR，其他语言走 faster-whisper（和现在一样：有 CUDA 用 GPU，否则用 CPU）。
- **FunASR**：fsmn-vad → paraformer-large（带逐字时间戳）→ ct-punc，全部用 onnxruntime 在 CPU 上运行（`funasr-onnx` 0.4.3，int8 模型），在单独的子进程里执行，取消时结束进程树。
  - 模型（ModelScope）：`iic/speech_fsmn_vad_zh-cn-16k-common-onnx`、`iic/speech_paraformer-large-vad-punc_asr_nat-zh-cn-16k-common-vocab8404-onnx`、`iic/punc_ct-transformer_cn-en-common-vocab471067-large-onnx`，共约 1.3GB，放在 `.prometheus\models\funasr\`，由「安装本地转写组件」一并下载（直接用 ModelScope 的文件接口，不引入 modelscope 包）。
  - **分段**：先按 。！？；… 断句；超过 30 个字或 8 秒的句子，再在 ，、 处拆开。每段的起止时间取首字和末字的时间戳。
- **组件安装位置**：CUDA 运行库装到 `paths.cuda_dir`（即 `.prometheus\runtime\cuda`）。修复 R3 遗留的问题：安装代码仍写到数据目录根部的 `runtime\cuda`，而转写代码从 `.prometheus` 下查找。

**平台人工字幕（2026-09-27 补充）**

- 仅限 YouTube：解析阶段读取 yt-dlp 的 `language`（视频原语言）和 `subtitles`（作者上传的人工字幕，不含 `automatic_captions`）。有与原语言匹配的人工字幕时（主语言代码相同，例如 `zh` 对 `zh-Hans` / `zh-CN`），只下载这份字幕，转成分段，跳过音频转写。没有 `language` 或没有匹配的字幕时，照常转写。
- 繁体字幕按现有规则转成简体。
- 使用了平台字幕的条目，在条目上记录来源「YouTube 人工字幕」。

#### 15.4.5 前端（C · 液态玻璃，用户于 2026-09-26 选定）

- **外壳**：墨夜底色（`#1b1e22` 系），报告保持浅色纸页（原因：Agent 生成的图表按白纸配色）。
- **侧栏**：独立的左列（胶囊宽 196px，外侧留白 14px），玻璃胶囊只悬浮在左列的环境光背景上，**不遮挡内容区**；内容区从左列右侧开始。玻璃效果只用在侧栏胶囊和阅读工具栏这类小面积上。
- **滚动条**：悬浮细滚动条，静止时几乎透明（约 20% 不透明），滚动或悬停时显现并变宽，停止 800ms 后淡出。报告 iframe 在注入的覆盖样式里做同样处理。
- **导航**：侧栏高亮始终等于当前页签；阅读页的「精读 / 导图 / 字幕」切换同时切换当前页签，保持同一条目。
- **三个内容页签**共用「分类 → 条目 → 内容」版式：分类列、条目列表，以及内容区的顶部玻璃工具栏（面包屑 + 三件套切换）。
- **字幕页**：按时间顺序完整列出全部分段（`[时:分:秒] 原文`），长列表用虚拟滚动；点时间戳在浏览器打开视频对应时刻；可以导出 SRT / TXT。默认显示纠错版（15.4.6），工具栏上有开关，可切换为原始识别；字幕来自 YouTube 人工字幕时显示来源。
- **报告页**：显示时临时注入覆盖样式（配色、字体、渐变条、滚动条），磁盘上的文件不改。
- **字体**：标题用思源宋体（Noto Serif SC，OFL）的按字切分 woff2，随安装包分发；界面文字用系统字体。
- **动效**：弹簧曲线（由阻尼振子采样生成 CSS `linear()`；空间类约 500ms、带轻微回弹，效果类约 320ms、无回弹），页面与内容切换用 React 19.3 的 `<ViewTransition>`；遵循 `prefers-reduced-motion`。
- **测试**：Vitest 覆盖布局与交互逻辑；Playwright 的 `webServer` 自动拉起假流水线后端和 Vite（`npm run e2e` 一条命令）。
- **设计检查**：颜色只在 `tokens.css` 定义；动效曲线只在 `motion.css` 定义。

#### 15.4.6 字幕纠错（用户 2026-09-27 同意）

- **位置**：新阶段 `subtitle_fix`，放在 `finalize` 之后、`mindmap` 之前。报告已经写好，可以当术语参考；报告的生成流程不变。
- **输入**：分段字幕（转写结果或平台人工字幕）；参考材料是报告转成的 Markdown（最多 12000 字）。
- **做法**：
  - 每次最多 120 段（约 2500 字），最多 3 个请求并发；
  - 提示词要求：只改语音识别造成的错字（同音字、近音词、专有名词），补全标点；不增删内容，不改说法，不合并或拆分分段，不改时间；平台人工字幕只补标点。输出为 `{"段号": "文本"}` 形式的 JSON。
- **逐段校验**（确定性）：
  - 每个段号都要有；
  - 去掉标点和空白后，与原文的编辑距离 ≤ max(2, ⌈原长 × 0.3⌉)；
  - 不满足的分段保留原文。一批的输出无法解析时重试一次，仍失败则整批保留原文。
- **存储**：原始识别存为缓存里的 `segments.raw.json`（长期保留）；纠错后的写入 `segments.json`，字幕页、`字幕.srt` 和 `字幕.txt` 都用它。条目记录 `subtitle_status`（`ok` / `failed`）。
- **失败处理**：纠错失败时只把 `subtitle_status` 记为 `failed`，字幕保持原样，条目照常完成。
- **接口**：`GET /items/{id}/subtitle?variant=raw` 返回原始识别。
- **费用**：输入和输出都约等于字幕字数的 token 数（13 分钟约 1 万 token，3 小时约 10 万 token）。

#### 15.4.7 阅读体验（R7b，用户 2026-09-27 提出）

- **报告目录**：阅读工具栏上加「目录」按钮，列出报告各章（`<h2>`），点击后报告平滑滚动到该章。报告自带的目录链接在报告内跳转（srcdoc 页面会把 `#s3` 解析到软件自己的地址，所以由注入脚本接管）。报告在沙箱里，章节列表和跳转指令通过 `postMessage` 传递。
- **图片放大**（参考 Discourse 的做法）：点击报告里的图片，图片从原位置平滑浮起并放大到窗口中央，背景变暗；滚轮以光标为中心缩放（0.5–4 倍）；放大后可以拖动；点击图片以外的地方或按 Esc，图片平滑缩回原位置。
- **侧栏收起**：侧栏底部的按钮或 Ctrl+B 把侧栏收成约 64px 的玻璃图标窄条（图标仍可直接切换页签，悬停显示名称），内容区随之变宽；再按一次展开。收起状态记住（localStorage）。
- **正文缩放**：精读和字幕支持放大缩小（阅读工具栏的 A− / A+，以及 Ctrl+= / Ctrl+- / Ctrl+0；80%–160%，每步 10%），记住比例。
- 以上动效都用 `motion.css` 的弹簧曲线，遵循 `prefers-reduced-motion`。

#### 15.4.8 设置 · 模型（R7b，用户 2026-09-27 提出；参考 CC Switch，规模远小于 ModelGate）

- **多份配置**：模型配置可以保存多份，以卡片列表显示，一键切换当前使用的一份。每份包含：名称、类型（DeepSeek / 智谱 / 自定义）、接口地址、协议（OpenAI / Anthropic）、API Key（眼睛图标切换显示）、模型、能否看图、思考强度。旧版的单一模型设置在读取时自动迁移成一份配置。
- **获取模型列表**：只在用户点击时，由后端向这份配置的接口请求一次模型列表（OpenAI 协议：`GET {base}/models`，`Authorization: Bearer`；Anthropic 协议：`GET {base 去掉 /v1}/v1/models`，`x-api-key` + `anthropic-version`），结果做成可搜索的下拉，也可以手填。开发和测试一律使用假接口，不向真实中转发送请求（用户要求：中转站测活会被封号）。
- **能否看图**：选中模型时先查随软件分发的 models.dev 目录快照（只保留模型 id 和是否接受图片输入，不联网），查不到时由用户勾选。
- **思考强度**：关 / 低 / 中 / 高，对应 Pi 的 `off / low / medium / high`，默认「中」。
- **下拉框**：改为自绘的圆角浮层，箭头内收，可用键盘操作。

#### 15.4.9 内容增强（R7c，用户 2026-09-27 提出）

- **导图：由简到繁**（用户 2026-09-27：越往外越丰富，末端要点比主题丰富是正常的；要求在调用模型的外层做加法，并用用户的 API 实测）：
  - **各层字数**：root ≤ 20 字；theme 的 label ≤ 20、summary ≤ 40；topic 的 summary ≤ 60；leaf 的 label ≤ 20、summary ≤ 60（卡片副标题），另加 `detail`（2–4 句，80–220 字）。
  - **两步生成**：第一步沿用 15.4.2 生成骨架。第二步按主题分批「填充」：每个主题一次模型调用，最多 3 个并发，为该主题下的每个 leaf 写 `detail`。
  - **检索**：每个 leaf 的资料 = 其时间所在章节的完整正文 + 在全篇报告段落上用 leaf 的 label 和 summary 做关键词检索（BM25，中文按字的二元组切分）得到的最相关的 2 段，去重后提供给模型。
  - **写作规范**：detail 只依据资料，至少包含资料里的一项具体信息（数字、名称、定义、例子或条件），不复述 label 和 summary；提示词附一条好的和一条差的示例。
  - **逐条校验**（确定性）：长度 80–220 字；与 summary 的字三元组重合度 < 0.6（不能只是复述）；依据率 ≥ 0.35（detail 的字三元组有多少出现在资料里）；含具体信息（数字、引号或书名号里的内容、西文词，或与资料相同的连续 6 个字以上）。不合格的 leaf 带着具体问题重写一次，仍不合格就不带 detail。
  - **评测**：`scripts/mindmap-eval/` 在真实报告上运行，输出各层平均字数、detail 覆盖率、平均依据率、具体信息覆盖率、调用次数与耗时，结果写进 `docs/mindmap-eval.md`。
  - **呈现**：leaf 卡片加宽，直接显示 detail 的前几行（完整内容在面板里）；主题卡片保持简洁。节点面板显示 label、summary、detail 全文、时间链接和「在精读中查看」（切到精读页签，并把报告滚动到该要点时间所在的章节）。旧导图没有 detail，照常显示，重新生成后补上。
- **中外对照字幕**：转写语言不是中文时，`subtitle_fix` 在同一次调用里给每段加中文翻译 `zh`（纠错规则不变）。字幕页每段原文下方显示中文，工具栏可以关掉译文；导出的 SRT / TXT 为双语（原文一行，译文一行）。精读仍然是中文。缺少译文的分段只显示原文。
- **查词**：英文字幕里光标停在单词上约 300ms，显示浮窗：音标、中文释义、词形还原（went → go）。释义来自离线词库 ECDICT（MIT），作为本地组件首次使用时下载。浮窗里有一排按钮：有道、剑桥、柯林斯、必应、韦氏，点击后在浏览器里打开该词典的这个词。
- **自定义云端转写**：设置「转写」增加第三个选项「自定义（OpenAI 兼容）」：接口地址、API Key、模型名。上传 16kHz 单声道 mp3，请求 `response_format=verbose_json` 获取带时间戳的分段；超过 20MB 的音频在静音处切块依次上传，再把时间拼接回原时间轴。没有返回时间戳、请求失败或超时，都与必剪一样改用本地转写，并在条目上记提示。

#### 15.4.10 界面修改第二轮（R7d，用户 2026-09-27 提出并确认）

**分类：人工管理，一处改动处处生效**
- 知识库、思维导图、字幕三个页签用同一份分类和条目数据：在任何一个页签里新建、改名、移动，另外两个页签立刻一致。知识库文件夹同步：分类文件夹改名；条目文件夹（精读.html、精读.md、思维导图.md、字幕.srt、字幕.txt、来源.url）整体移到新分类文件夹；重写 `llms.txt`、`index.json` 和受影响分类的 `_index.md`。
- **新建**：分类栏标题旁的「+」，原地输入名称，回车创建，Esc 取消；空名不创建；重名提示「已有这个分类」。接口 `POST /api/categories {name}` → 201 `{id, name}`，重名 409，空名 422。
- **分类行的按钮**：每个分类行带两个图标按钮「✎ 改名」「🗑 删除」，鼠标悬停时出现，当前选中的分类上一直显示；键盘聚焦时也显示。「未分类」没有这两个按钮。
- **改名**：点「✎」或双击分类名，原地编辑；回车保存，Esc 取消；重名提示同上。
- **删除**：点「🗑」后确认。空分类直接删除；非空分类的确认文字是「删除分类「×」？其中 N 篇会移到「未分类」」，确认后条目和文件夹移到「未分类」，再删除该分类。接口：`DELETE /api/categories/{id}?move_items=1`；不带参数时对非空分类仍返回 409（保持旧契约）。
- 合并功能不放到界面上（后端接口保留）。
- **拖拽**：拖拽和下拉框是两回事。在三个页签任意一个的条目列表里，把文章卡片拖到左侧的分类上，就归入该分类；拖动经过时目标分类高亮；拖回当前分类不做任何事。
- **阅读页**：去掉顶栏的分类下拉框（它看起来像筛选器，实际一选就移动条目，而且移空的分类会从列表消失、无法移回；2026-09-27 预览数据里三篇因此都进了「学习方法」）。改为「⋯」菜单：「移到…」（列出其他分类）、「删除」。
- 分类列表显示全部分类（包括 0 条的），按名称排序，「未分类」排最后。
- **模型自动归类**：用户新建或改名后的分类都是候选；只在条目第一次完成时归类。「重新生成」保留现有分类，只更新标签和摘要（现状是重新生成会重新归类，覆盖人工归类）。

**设置 · 模型（参考 CC Switch 与 ModelGate）**
- 下拉框只有一层边框（修复：自绘下拉框的外层误用了输入框样式 `.select`，造成「框套框」）。
- **API Key**（参考 ModelGate）：已保存时输入框为空，占位文字「已保存（末 4 位 ××××），留空则不修改」；输入了新内容才替换。平时页面拿不到完整 Key；**点眼睛图标时，才向本机后端要一次完整 Key 显示在框里**（用户 2026-09-28 选定，参考 CC Switch；接口 `POST /api/settings/reveal-key`，只返回该配置自己的 Key）。
- **获取模型列表**：失败时显示具体原因，即 HTTP 状态码加一句说明：401 或 403 为「Key 无效或无权限」；403 且响应来自 Cloudflare 为「请求被 Cloudflare 拦截」；404 为「这个地址没有模型列表接口」；超时为「连接超时」。请求带 `User-Agent: Prometheus/<版本>`（现在是 Python 默认的 `Python-urllib`，容易被拦）。OpenAI 协议先试 `{base}/models`，404 时再试 `{base}/v1/models`（CC Switch 的做法）。
- **常用供应商**（参考 CC Switch 的预设）：新增或编辑配置时，顶部一排按钮替代原来的「类型」下拉框：DeepSeek、智谱、Kimi、通义千问、MiniMax、豆包（火山方舟）、硅基流动、OpenRouter、Anthropic、OpenAI、自定义。
  - DeepSeek 和智谱仍是内置类型，也显示「获取 API Key ↗」（用户 2026-09-28 追加）。
  - 其余按钮填入接口地址、协议和推荐模型（填入后都可以再改），并在 Key 输入框旁显示「获取 API Key ↗」，点击在浏览器打开该平台的 Key 页面。
  - 只收官方平台，不收带返利链接的中转。地址和模型在实现时按各平台官方文档核对，核对日期记入 DECISIONS。
- **思考强度**：关 / 低 / 中 / 高 / 超高 / 最高，对应 Pi 的 `off / low / medium / high / xhigh / max`。随包 Pi 的模型目录里有这个模型时，只列出它支持的档位；没有时全部列出，并提示「超高、最高只有部分模型支持」。
- **模型参数**：生成 `models.json` 时，自定义模型按随包 Pi 的模型目录（同名模型）补齐 `contextWindow`、`maxTokens`、`thinkingLevelMap`、`compat`。目录里没有的，用随软件分发的 models.dev 快照中的上下文和输出上限；都没有就不写，按 Pi 默认的 128k / 16k。编辑页的「高级」里显示这两个数，可以手动改。
  - 原因（2026-09-27 查明）：用户的 claude-opus-4-8 一直按 Pi 的默认值运行（上下文 128k，每次回复 16k 且含思考），也没开自适应思考；该模型实际是 1M 上下文、128k 输出。

**字幕：合并成 10–15 秒一段**
- 纯函数 `group_segments`：
  - 按顺序累积分段。累计满 10 秒后，遇到句末标点（。！？!?.…）就结束一段。
  - 到 15 秒还没遇到句末，就在最后一个逗号类标点（，,、；;：:）处结束；也没有，就在 15 秒以内的最后一个分段边界结束。
  - 下一个分段会让本段超过 15 秒时，本段提前结束，可以短于 10 秒。
  - 单个分段超过 15 秒时按标点拆开，时间按字数比例估算；没有标点的按字数均分。
  - 英文拼接时加空格，中文直接拼接。不丢字、不改字，起止时间单调递增。
- **新条目**：转写之后、纠错之前合并；纠错和翻译都在合并后的段落上进行。
- **旧条目**：启动时一次性转换，不调用模型。
  - 纠错版和原始识别版用同一组边界合并；已有译文按顺序拼接。
  - 重写 `字幕.srt` 和 `字幕.txt`；原来的细分段另存为缓存里的 `segments.fine.json`。
  - 转换可以重复执行，结果不变。
- 字幕页、SRT、TXT 都使用合并后的段落。

**导入失败写明原因**（用户 2026-09-27 追加，2026-09-28 确认）
- 现状：失败的条目在控制台只显示「失败」和一句大类建议，括号里跟着原始报错（常是英文技术原文，例如 `Pi generation timed out; see RPC log`）；而且失败时队列把 `stage` 清空，看不出是哪一步失败的。
- 改为：失败时保留出错的阶段；控制台里失败的那一行写三件事：
  - 「在「下载」这一步失败：」加一句中文原因；
  - 「怎么办：」一句具体操作；
  - 「详情」折叠：原始报错全文，可以复制。
- 按报错内容判断原因（确定性规则，每类都用真实格式的报错样本做单测；报错格式从 yt-dlp 和 Pi 的源码里查，不向任何中转发请求）：
  - **视频本身**：视频不存在或已删除；需要登录、大会员或付费才能看；地区限制；直播或还没开播；不支持的链接。
  - **网络**：B 站暂时拒绝请求（HTTP 412 风控）；连不上网站（超时、DNS、代理地址错误）；YouTube 要求登录验证或 cookies 已过期。
  - **模型**：Key 无效或没有权限（401 / 403）；余额不足或额度用完（402、insufficient_quota 等）；请求太频繁或并发超限（429）；模型服务繁忙（overloaded、5xx）；模型没有回应（超时）；内容太长，超过模型的上下文；模型名不存在。
  - **本机**：转写组件没装；磁盘空间不足；转写进程出错（给出日志文件的位置）。
  - 都不匹配：「未归类的错误」，照样给出阶段和详情。

**旧条目补标签**
- 没有标签的条目，在阅读页「⋯」里显示「补全标签和摘要」。用户点了才调用一次模型（输入：标题、导语、各章标题），只写标签和摘要，不改分类；完成后更新 `精读.md` 开头和 `index.json`。

**精读正文加宽**
- 报告纸面随窗口变宽：宽度等于阅读区宽度减去两侧各 40px，最宽 1280px（原模板固定为 860px）。
- 隐藏报告自带的左侧目录（它在深色外壳下显示成灰块，还占宽度），由阅读工具栏的「目录」按钮承担。
- 图片和图表不超过自身宽度，居中；表格随纸面填满。
- 窗口本身可以拖边框改大小、可以最大化（Tauri 默认），不改。

**查词：英英释义**
- 浮窗在中文释义下方显示英英释义（最多 3 条），来自 ECDICT 的 `definition` 字段（主要取自 WordNet），离线，不调用模型。
- 旧词库没有这一列：浮窗底部提示「更新词库可显示英英释义（约 23MB）」并给出按钮；更新前照常显示中文释义。
- 词典按钮增加「牛津」（Oxford Learner's Dictionaries）和「欧路」（欧路网页词典）。

#### 15.4.11 精读完整度（R7e，用户 2026-09-27 提出，2026-09-28 确认）

> 用户 2026-09-28 的选择：每章单独运行 + 程序拼装（不改 vendor，不做附录 A 的 V4）；补充解释大力放开（讲深、讲长、讲易懂）；「讲清楚」审校在完整模式下默认开；live 预算约 25–45 美元（按官方价粗估，超出时停下来问用户）。方案参考了独立子 agent 的审视（评测先行、两级覆盖、照抄检查、两步审校）。
>
> 用户 2026-09-28 第二轮（看过第 1 层的结果和实测费用后；中转站没有提示缓存，英文 19 分钟重写一次约 5 美元）：走完整的分章流水线，不做省钱版；live 预算上调到约 60–80 美元；E14 的闭卷门槛改为「≥ 80%，且比旧报告高 20 个百分点或达到 95%」（英文样本旧报告已有 87.5%，原门槛不可能达到）；忠实度取证加上全文检索（见「评测」）。
>
> 用户 2026-09-28 第三轮（读了第 1 层的英文精读：分点清楚，但每点阐述不够，专有名词没解释，读完还是懵）：参考 ELI5 skill，读者设定为聪明但零基础的成年人，每个要点按「是什么 → 类比 → 展开 → 所以呢」四步写；术语第一次出现就在正文里一句话解释，需要时再加补充说明框；规则、规划和反馈里不写字数（写明下限会被当成终点），篇幅由结构、程序的隐藏检查和零基础读者的追问推动。

**目标**：精读是写给看不到视频的读者的完整讲解。**做加法**：保留 VRA 原有的图文结合（配图、图示、卡片、表格、强调框），在此基础上让来源里每一个有实质内容的点都写到、讲清楚；允许篇幅变长、解释重复；鼓励补充解释，但补充内容与视频原话区分开，不能写成讲者的说法。

**实测起点（2026-09-27）**：
- 卡巴拉（104 分钟）：转写 3.35 万字，报告 7572 字；48% 的转写单元不在任何出处标注的范围内。最长的一段（01:34:43–01:44:23）前半是正课、后半是课程推广和告别；最明显的漏写是 01:08:46–01:15:14（法老与十字架、六芒星的故事，几种护符的形状），报告里一句没有。
- 短视频（8 分钟、19 分钟）：大部分内容都有标注。
- **覆盖率只按 `data-points` 计算**：VRA 的出处标注只要求给「核心判断」标来源，标注写法也不统一（有的写首尾两个单元，有的逐个列出），不能当完整度指标。

原因：
1. **配置**：上下文按 128k 算（卡巴拉的转写约 8 万 token，加上 Skill 和模板就会触发 Pi 的自动压缩），每次回复最多 16k token。已由 15.4.10「模型参数」修复。
2. **VRA 的取舍方针**：standard.md 要求合并作用相同的例子、「不以篇幅证明完整性」、把长闲聊压缩成短报告，SKILL.md 的通读修订要求「优先删除重复层次」。
3. **篇幅习惯与长原文**：单次回复倾向于写几千字、越往后越省（LongWriter 的结论）；一次读 8 万 token 的原文，中段最容易被忽略（Lost in the Middle）。
4. **没有反馈**：流程里没有任何一步告诉模型漏了什么。

**设置**：「精读详细程度」分「完整」（默认）和「标准」（VRA 原样，不经过下面的流程）。完整模式下「讲清楚审校」默认开，设置里可以关。两者都使用 15.4.10 修好的模型参数。

**完整模式的流程**（VRA 的 Skill 文件不改；模型调用都经过 Pi）

0. **评测先行**：先写 `scripts/report-eval/`（见下文「评测」），测出三篇旧报告的基线。之后每加一层，先在英文样本（19 分钟）上量一次；最后在两篇上各跑一次完整流程。达到 E14 门槛就不再加层。
1. **附加规则 `report/depth.md`**（依据 standard.md「用户明确要求的深度优先」）：
   - 读者看不到视频；写明考法：「写完后会有人只拿这份报告回答视频每 5 分钟 4 道题，答不出算漏写」。
   - 逐条引用 VRA 里要求压缩的规则（standard.md 第 15–21、37、83 行，SKILL.md 第 90、133、137 行），写明完整模式下各改成什么；只可以删口头禅、逐字重复、广告、寒暄与课堂管理、技术故障。
   - 按要点类型给讲解清单：定义（是什么、例子、与相近概念的区别）；步骤（顺序、前提、每步做什么、常见错误）；论断（结论、理由、成立条件）；数字（数值、单位、口径、和谁比）；例子或故事（发生了什么、说明什么）。
   - **读者与讲法（用户 2026-09-28 第三轮，参考 ELI5 skill：github.com/DreambigOu/ELI5）**：读者设定为「聪明但零基础的成年人」，从没接触过这个领域，但不需要幼稚化。每个要点按四步写：一句话说清是什么 → 类比到读者熟悉的东西 → 分层展开（原理、理由、条件、步骤、例子，按上面的清单）→ 所以呢（对读者意味着什么、和前后要点的关系）。先讲目的，再讲机制。
   - **术语必须当场解释**：术语、专有名词、人名、书名、缩写、外语词第一次出现时，就在那句话里用一句白话解释；需要讲原理或背景的，再加「补充说明」框展开。后文再用到时再带一句。
   - **不给字数**（用户 2026-09-28 选定）：规则、规划和反馈里都不写任何字数。写明下限，模型会把它当终点；原来的「每条约 60–150 字」实际上还成了上限。篇幅靠四步结构、隐藏检查（第 5 步）和零基础读者的追问（第 6 步）推动。
   - **补充说明**（用户 2026-09-28：大力放开）：鼓励用模型自己的知识补充术语定义、背景、原理，以及帮助理解的通俗说法（类比、换个角度再讲一遍）；讲深、讲长、讲易懂都可以。补充内容放在 `<aside class="supplement">`（显示为「补充说明（非视频内容）」）里，不写成讲者的话，不替视频下结论，不与视频内容矛盾。
   - **图文结合照旧**：VRA 的组件、图示和画图规则全部适用；开了配图时，按 figures.md 使用本章时间范围内的候选帧。
   - 好坏对照示例用与评测样本无关的内容，避免把考题透露给模型。
2. **要点账本**（新阶段 `keypoints`，在写作之前；参考 FActScore、FineSurE）：
   - 把转写按单元边界切成约 5 分钟一块；每块一次模型调用（统一的一次性调用写法，最多 3 个并发），列出所有有实质内容的要点：编号 K001…、类型、一两句能独立看懂的表述、依据的单元范围、一句原话锚点。
   - 程序校验：单元属于这一块；锚点能在这些单元的原文里找到（去掉标点后相似度 ≥ 0.8）；类型合法。不合格的条目带着问题重问一次，仍不合格就丢弃并记录。
   - **两级覆盖的第一级**：这一块里每个转写单元都要归属某条要点，或者落在写明理由的「跳过片段」里；连续 30 秒以上没有归属，就带着这段原文重问一次。
   - 输出 `keypoints.json`、便于阅读的 `keypoints.md`，以及按块切好的转写 `transcript/part-NN.md`。
3. **规划**（一次 Pi 运行，带 VRA Skill；参考 LongWriter、STORM）：写 `plan.json`：主副标题、导语、Profile、各章（标题、依据的时间区间；要点按时间归属，需要时写 moves）、术语表（术语、在哪一章首次解释）、`skips`（不写的要点及理由：广告推广、寒暄与课堂管理、重复（须指向被重复的要点）、离题闲聊、技术故障）。程序校验：每条要点都有归属或合法的跳过理由；「重复」指向的要点存在且没有被跳过；跳过超过 25% 时要求逐条复核一次。不合格带着问题重做一次。
4. **分章写作**（每章一次独立的 Pi 运行，最多 3 个并发，可以用工具画图）：
   - 输入：depth.md、VRA 的 Skill / 模式文件 / 模板（写法和组件）、全篇规划、本章要点、本章转写分块、前面章节已解释过的术语、（开了配图时）本章的候选帧。
   - **图示和配图按内容触发，不设张数上限**（用户 2026-09-28）：图示按内容的形状画（步骤 → 步骤图，对比 → 对照表，因果和依赖 → 关系图，并列的类别 → 卡片，数量差别 → 柱图，抽象概念 → 类比示意图），不按要点数或章节数。截图在画面里有正文写不出来的信息时就配（幻灯片、图表、板书和公式、代码、软件界面、实物演示、地图），宁多勿少；不配口播人像、转场、片头片尾和广告，同一个画面只配一次。候选帧本身每小时最多 20 张。**图文不重复**：图负责结构，正文写图里画不出的道理和例子，图注只写画面的关键信息。「标准」模式照旧用 figures.md 的张数限制。
   - **多配图的三层**（用户 2026-09-28 选定）：① **候选帧账本**：开了配图且模型能看图时，写作前每章一次一次性调用，把本章的候选帧逐张附上（不拼成一张缩略图：模型会把单张图缩到长边约 1568 像素，拼图里幻灯片上的字就看不清了），逐帧给出类型（幻灯片、图表、板书公式、代码、软件界面、实物演示、地图、口播人像、转场片头、其他）和一句话内容，前七类算「有信息」；结果缓存，写作提示词里按时间列出本章候选帧（文件名、类型、一句话），写作者不用逐张打开就能挑。② **程序检查**：本章「有信息」的帧既没用上、也没写明不用的理由（片段里写 `<!-- 不用 f_000332：与 f_000310 同一画面 -->`），就和漏写的要点一起退回，同样最多 2 轮。③ **读者要图**：零基础读者审校时，同时列出「哪里配一张图或示意图会更好懂」，一起退回补图；补的图只画本章正文已经写到的内容。
   - **看大图时左右切换**（用户 2026-09-28，图多了以后）：放大层两侧各有「上一张」「下一张」按钮，键盘 ← → 也能切，底部显示「3 / 12」和图注；按报告里从上到下的顺序，到头不循环，到头的那一侧按钮变灰。切换时背后的正文跟着滚到当前这张，关闭时图片缩回它在正文里的位置。模型画的 SVG 图示也能点开放大，和截图排在同一个序列里（表格和卡片不算图）。
   - **面向未知的视频**（用户 2026-09-28）：规则、提示词和门槛不针对任何评测样本；示例用与样本无关的内容（有单测守着）；隐藏门槛用英文和卡巴拉两篇校准，罗素留作不参与校准的复核样本（这一条由执行 agent 提出，写进规格时没有先问，用户随后确认保留）：门槛调好以后在罗素上跑一次完整模式，确认对没见过的视频也成立。
   - 输出 `chapters/ch-NN.html`：一个章节片段（`<section>`，含 `<h2>`、`section-time` 和正文）；段落、列表项、表格行、图注都用 `data-points="K012 K013"` 标出讲了哪些要点。
   - 10 分钟以内的视频可以一次写完全部章节。
   - 分章运行由后端自己的运行器调用 Pi，命令参数与 vendor 的 PiRunner 一致（`--skill`、那组 `--no-*`、`--session-dir` 等），不修改 vendor。
5. **逐章检查与反馈**（程序；参考 Self-Refine、Chain of Density）：
   - 分到本章的要点是否都出现在 `data-points` 里（**两级覆盖的第二级**）；
   - 声称写到的要点，段落与要点原文的字符重合是否足够（沿用导图 `enrich` 的依据率算法，阈值用真实样本校准后记入 DECISIONS）；
   - **照抄检查**：与转写连续相同超过约 30 字的比例，防止直接贴口语原文；
   - **每个要点的隐藏篇幅检查**：统计标了这个要点的文字有多少（一段标了几个要点就平分），和这个要点在视频里讲了多少（它依据的转写单元）比较；门槛随来源内容放大，所以长短视频不用分开定。门槛只在程序里，用真实样本校准后记入 DECISIONS。不够时反馈不说数字，也不说「写多点」，只点名这个要点、要求按四步补全（缺类比、缺例子、缺「所以呢」等）。
   - 不合格就带着具体清单（要点编号、原话、时间）重跑这一章，每章最多 2 轮；仍缺的记入 `coverage.json`，不再追。
6. **讲清楚审校**（完整模式默认开；参考 G-Eval）：每章两步。
   - 第一步：只给这一章的正文，让模型扮演没看过视频、聪明但零基础的读者，列出看不懂或想追问的地方；第一次出现却没有解释的术语、人名、缩写，每一个都要列出来。
   - 第二步：再给本章转写，逐条判断原文里有没有答案。有答案的，交回去补写这一章一次；原文没有答案、但属于术语或背景的，可以用「补充说明」补；其余不补，防止编造。
7. **拼装**（程序）：按规划把各章依次填进 VRA 模板（`{{TITLE}}`、`{{SUBTITLE}}`、`{{LEAD}}`、`{{ATTRIBUTION}}`、`{{BODY}}`、`{{SOURCES}}`，保留 `{{VIDEO_DESCRIPTION}}` 一次），由章节标题生成模板的目录；注入「补充说明」框的样式（只用模板的 CSS 变量）；然后照常进入 `finalize`。拼好后程序复查全篇覆盖。
8. **记录**：覆盖结果写入缓存 `coverage.json`（要点总数、已写到、跳过及理由、未覆盖清单、各章每分钟字数、照抄比例）；精读页工具栏显示「要点 142/146」，点开是跳过和未覆盖的清单，带时间，点击跳到视频。

- 写作阶段的总时限是 2.1 节公式的 3 倍；控制台的阶段名增加「提取要点」「规划」，写作阶段显示「写作（第 3/10 章）」，审校显示「审校」。
- 并发、重试和费用：每篇的调用次数约为「要点块数 + 章数 × 2–4」；中转返回 429 时按现有规则退避重试。

**评测**（`scripts/report-eval/`，结果写进 `docs/report-eval.md`；同一样本对旧报告和新报告各测一次）
- **闭卷问答**（参考 QAGS、DeepEval 的摘要覆盖指标）：每 5 分钟转写出 4 道题及标准答案。只根据转写出题，与要点账本无关；一次生成后固定保存，新旧报告用同一套题。只给报告作答，找不到就答「未提及」；逐题判为正确、部分正确、未提及或错误。得分 = (正确 + 0.5 × 部分正确) / 题数。
- **忠实度抽检**（参考 FActScore）：随机抽 40 句正文（不含补充说明），连同它标注的来源单元（前后各多给 2 个单元）和整篇转写里与这句话最相关的两段原文（全文检索；用户 2026-09-28 确认，理由见 D-44），判为有依据、部分有依据或无依据。补充说明另外抽检，只判它与视频内容有没有矛盾。
- **图文结合不减少**：统计图示、配图、表格、卡片等组件的数量，新报告不少于旧报告。
- **程序指标**：要点覆盖率（只认 `data-points`）、跳过比例及理由分布、时间覆盖、最长漏写、各章每分钟字数、照抄比例；报告与转写的字数比只记录，不设门槛。

**参考文献**（2026-09-27 核对）：FineSurE（ACL 2024，arXiv 2407.00908）；FActScore（2023）；LongWriter（arXiv 2408.07055）；STORM（2024）；Chain of Density（arXiv 2309.04269）；Self-Refine（2023）；Lost in the Middle（2023）；BooookScore（arXiv 2310.00785）；QAGS（2020）；G-Eval（2023）。

**不采用**：
- 同一会话多轮往下写（附录 A 的 V4）：用户选定分章独立运行，它不受视频长短和模型上下文大小的限制，也不用改 vendor。
- LangChain / LangGraph / LlamaIndex：与现有的阶段编排重复，依赖重；而且模型调用必须经过 Pi，才能支持 Anthropic 协议的中转。
- DeepEval / RAGAS：原因同上，只借用它们的指标思路，自己实现。
- 向量检索：没有配置向量模型，中文锚点用字符匹配就够了。
- 「输出不少于原文 80%」：口语转写里口头禅和重复占三到五成，硬凑字数会逼模型注水或照抄转写。
- 调 temperature：Claude 开思考时不能调，也不是原因所在。
- 多份候选择优：费用成倍增加。
- DSPy 自动调提示词：要几十次付费运行；先用评测结果手工迭代。

#### 15.4.12 更新模型目录（R7e 期间，用户 2026-09-29 提出并确认）

> 起因：用户把模型换成本机 CPA 上的 gpt-6-luna、思考强度选「最高」。随包 Pi 的模型目录是 2026-09-04 的，不认识 gpt-6-luna；Pi 对不认识的模型只跑到「高」，设置里选了「最高」也默默降档，上下文还按 models.dev 快照填成了 1050000（pi.dev 目录里是 272000）。Pi 自己在联网时会自动刷新目录，但我们一直用离线模式运行它；`pi update --models` 只刷新配了凭证的内置供应商，自定义供应商用不上。

- **来源**：Pi 自己用的 `https://pi.dev/api/models/providers/<供应商>`，供应商列表就是随包目录里的那些文件。只读取公开目录，不调用模型、不发送 Key；走设置里的网络代理。
- **保存**：数据目录的 `config/pi/catalog/`（每个供应商一个文件，另存更新时间）。某个供应商拉取失败时保留它的旧文件；全部失败时照旧用随包目录。
- **使用**：填模型参数（上下文、最大输出、思考档位、兼容设置）时，新目录优先，其次随包目录，再次 models.dev 快照；更新完成后按当前配置重写 models.json。
- **触发**：设置页模型区的「更新模型目录」按钮，旁边显示目录日期；后端启动时，若超过一天没更新，就在后台自动更新一次，失败不影响使用。
- **说实话**（不改成原样传档位）：目录里仍然没有的模型，选了「超高」「最高」时，设置页写明「这个模型不在模型目录里，超高和最高会按高运行；可以先点「更新模型目录」」。
- **Done When**（并入 E14 ①）：后端单测（拉取与保存、单个供应商失败保留旧文件、新目录优先于随包目录、到期判断、接口返回日期与失败的供应商、更新后重写 models.json）；端到端（假后端下点「更新模型目录」后日期更新；目录里没有的模型选「最高」时出现上面那句提示）。

### 15.5 里程碑

每个里程碑在单独分支上开发，先写失败测试再实现，测试全绿后 `merge --no-ff` 到 `main` 并推送。

| 里程碑 | 分支 | 内容 | Done When |
|---|---|---|---|
| R1 | `r1-fixes` | 15.2 第 1、2 条（取消、运行时路径、看图能力、测试模型、trace、中文错误提示、D1、清理、模型协议） | E1、E2；取消与清理的单测 |
| R2 | `r2-architecture` | 15.2 第 3 条：模块搬迁，编排变薄；行为不变 | E1（搬迁前后测试集合不变且全绿） |
| R3 | `r3-library` | 15.4.1：可读文件夹、精读.md、标签与摘要、索引、改名与移动同步、旧版迁移 | E1；迁移、命名、索引的单测 |
| R4 | `r4-mindmap` | 15.4.2 后端：JSON 知识树生成、校验、导出 .md | E1；校验规则的单测 |
| R5 | `r5-asr-bench` | 15.4.3 实测 | E5，**停下来等用户选定** |
| R6 | `r6-asr` | 15.4.4 必剪 + 本地 FunASR / whisper 按语言切换 + YouTube 人工字幕 + 组件安装位置修复 | E1；live：必剪、FunASR、whisper 各转写一段样本；YouTube 人工字幕样本不经转写 |
| R6b | `r6b-subtitle-fix` | 15.4.6 字幕纠错 | E1；E10 |
| R7 | `r7-frontend` | 15.4.5 前端重写（含导图画布） | E6；**停下来请用户看截图**（E7） |
| R7b | `r7b-reading` | 15.4.7 阅读体验 + 15.4.8 模型设置 | E11 |
| R7c | `r7c-content` | 15.4.9 导图由简到繁（检索填充）、中外对照字幕、查词、自定义云端转写 | E12 |
| R7d | `r7d-ui-review` | 15.4.10 界面修改第二轮 | E13；**停下来请用户看截图** |
| R7e | `r7e-report-depth` | 15.4.11 精读完整度（评测先行、要点账本、分章写作与拼装、逐章检查、讲清楚审校） | E14；**用户签字** |
| R8 | `r8-release` | 打包、README、完整验收 | E3、E4、E8、E9 |

### 15.6 进度记录

| 里程碑 | 状态 | 完成日期 | 合并 commit | Done When 结果 |
|---|---|---|---|---|
| R1 修复与协议 | 完成 | 2026-09-26 | d644c71 | E1：`uv run pytest backend/tests -q -m "not live"` = 0（150 passed）、`ruff` = 0；E2：D1 在未设 PYTHONUTF8 的终端 = 0（249 passed）；红 72ade93 → 绿 19e683e、a6a810c；取消用真实子进程验证（5 秒内结束），清理与保留均有单测 |
| R2 架构 | 完成 | 2026-09-26 | eed62ec | E1：搬迁前后同为 150 passed、`ruff` = 0；live 测试 4 个可正常收集；`llm/`、`figures/`、`mindmap/`、`report/outline.py` 就位，`tasks/stages.py` 只做调度 |
| R3 知识库存储 | 完成 | 2026-09-26 | 63e74a8 | E1：`uv run pytest backend/tests -q -m "not live"` = 0（175 passed，连跑 3 遍稳定）、`ruff` = 0；红 32e1604、605e0cd → 绿 a944c07；真实数据验证：acceptance-output/live-data 的旧版布局副本迁移成功（两个条目分入「战争伦理」「神秘学」，6 个文件齐全，旧 items/ 与根目录 db 清除）；Tauri 外壳与安装冒烟脚本的端口文件改到 .prometheus/logs（cargo check = 0） |
| R4 思维导图 | 完成 | 2026-09-26 | b1d79fe | E1：`uv run pytest backend/tests -q -m "not live"` = 0（192 passed，连跑 5 遍稳定）、`ruff` = 0；红 9d565e4、542fc25、b146d2d → 绿 244b395、fd60091；校验规则单测覆盖主题数、字数、叶子时间、深度、章节覆盖率、容错解析；按 PLAN 8.8 补上「重新生成导图」（`regenerate` 带 `{"only": "mindmap"}`，D-34），顺带修复 `regenerate` 读取 dict 的 `.status_code` 导致 500 的问题；导图阶段的模型错误不再让条目失败（PLAN 8.3）；修复两处测试竞态（test_links、test_items_api）；live 测试改用 `generate_for_item`（4 个可正常收集，本里程碑未调用真实 API） |
| R5 转写实测 | 完成 | 2026-09-27 | 28da7c7 | 用户选定：中文 FunASR paraformer-zh + 其他语言 faster-whisper turbo（D-35），必剪原样使用（D-36）。E5：`docs/asr-bench.md` 已产出（4 个引擎 × 中英两段样本，另测 Qwen3 的两种加载方式；字错率/词错率、速度、显存、时间戳、标点、体积）；评分规则单测 `scripts/asr-bench/test_metrics.py` 8 passed（红 8b6a46d、b48c856 → 绿 a3b63af、f692324）；`ruff check scripts/asr-bench` = 0；Fun-ASR-Nano 未测 |
| R6 转写接入 | 完成 | 2026-09-27 | 0e06133 | E1：`uv run pytest backend/tests -q -m "not live"` = 0（229 passed，连跑 3 遍稳定）、`ruff` = 0；E2 复查 = 0（249 passed，依赖锁变更后）。live（无模型费用）：必剪转写 B 站样本、本地中文走 funasr-onnx、YouTube 英文走 faster-whisper、TED 人工字幕跳过下载音频和转写，4/4 通过。真实 worker 在 R5 样本上：中文 funasr-onnx 字错率 7.97%（306 段），英文 whisper 词错率 2.78%。组件安装实测：FunASR 模型 1.23GB 用时 5 分 51 秒。红 af72e6c、9d4082c、2424951、13caa04、ed92d73、a6e254b、0957b16、ee92a3f → 绿 d23d5cf、1d3ecad、d9ffbc1、dc7171a、9d28f79、312d069、0ed1c44、b5b0984 |
| R6b 字幕纠错 | 完成 | 2026-09-27 | 9a3a3db | E1：`uv run pytest backend/tests -q -m "not live"` = 0（250 passed，连跑 3 遍稳定）、`ruff` = 0；新阶段 `subtitle_fix` 有按 StageContext 调用的测试。E10（claude-opus-4-8，未给报告参考）：whisper 结果字错率 8.17% → 7.01%（改 64 段，0 段超限）；必剪结果 6.17% → 5.86%，标点每 100 字 0.9 → 6.3（改 243 段，1 段超限保留原文）；两者分段数与起止时间不变，2/2 通过（字错率按字母数字编辑距离计算，未做数字写法归一）。典型改正：打卷→问卷、不发→不乏、管中亏报→管中窥豹、三大剧头→巨头、B键→必剪、扣绿→抠绿、德意黑→得意黑。红 94b592c、6ab8702 → 绿 c05867e |
| R7 前端 | 完成 | 2026-09-27 | 2170ae9 | E7 第一轮：用户看过截图并在浏览器里试用，提出的意见进入 R7b / R7c（见 acceptance.md），最终判定在 R8 安装版试用后；目录白页缺陷已修复（1b31ea8）。E6：`npm --prefix app run test` = 0（22 passed）、`npm --prefix app run e2e` = 0（①–⑧ 加目录跳转共 9/9，Playwright 自动拉起假流水线后端和 Vite）、`npm --prefix app run lint:design` = 0；`tsc --noEmit` = 0。截图（真实数据：罗素 8 分钟、魔法卡巴拉 104 分钟，旧版数据迁移后用「重新生成导图」生成新版知识树）：`docs/screenshots/r7/`。顺带：`regenerate` 接受已完成条目（「文件缺失」的「重新生成」），红 37fc5a8 → 绿 4ea8fd1 |
| R7b 阅读与设置 | 完成 | 2026-09-27 | 62ed03e | E11：`npm --prefix app run e2e` = 0（14/14，含 E11 ①–⑤ 与 E6 ⑧ 的新设置页写法）、`npm --prefix app run test` = 0（25 passed）、`lint:design` = 0、`tsc` = 0；后端 `pytest` = 0（263 passed）、`ruff` = 0，模型配置迁移、两种协议的模型列表、假模型接口均有单测（开发中未向任何真实中转发送请求）。红 61eda96、ff84430、6829f65 → 绿 6bed985、d9a0fd8、64aac34、e6a9ccc |
| R7c 内容增强 | 完成 | 2026-09-27 | b4c029c | E12 ①：`uv run pytest backend/tests -q -m "not live"` = 0（318 passed：检索、校验、重写、评测指标、字幕翻译与校验、双语导出、查词含词形还原、自定义云端转写含切块与失败退回本地，均用假模型/假接口）、`ruff` = 0、`verify.ps1` = 0；② `npm --prefix app run e2e` = 0（18/18，新增导图详解与「在精读中查看」、英文字幕中外对照、查词浮窗、自定义转写设置）、`npm --prefix app run test` = 0（34 passed）、`lint:design` = 0、`tsc` = 0；③ live：样本按用户意见改为 B 站英文视频 BV11i8J65EDp，中文精读 + 中外对照字幕（译文 97.9%）+ 自动归类，见 acceptance.md；④ 导图实测（用户的模型，三篇真实报告）全部过线，见 `docs/mindmap-eval.md`。红 58aeedb、a982f8d、8da5d79、3e91ba4、df9ac48、5cace4c、23e1fff、8c928cf、b3ad833、6b83949、9b9a4dd、fe34fe0、ad6d3a5、78d0e87、eea96ae、29d35ca、8aa3edf、e9b60a7/b936694、0db411f、d9ec6cd → 绿 d6fa651、ea704c9、1390362、1cab7ad、aaada5a、c9ed926、5df528b、9505705、5387fd5、bac056b、29da0ea、99c1086、5520b90、533cf9b、95dc9a2、1c6d8f9、665546e、71e6c55、4f33e82、535bfb2/ceaad79、487a1d7 |
| R7d 界面修改第二轮 | 完成 | 2026-09-28 | 7d05d02 | E13 ①：`uv run pytest backend/tests -q -m "not live"` = 0（449 passed）、`ruff` = 0、`verify.ps1` = 0；② `npm --prefix app run e2e` = 0（42/42，连跑两遍稳定；新增 r7d-library / r7d-report / r7d-settings / r7d-subtitle / r7d-failure）、`npm --prefix app run test` = 0（46 passed）、`lint:design` = 0、`tsc` = 0；③ 用户看过 `docs/screenshots/r7d/` 后判定「看着没啥大问题」（acceptance.md），并追加失败原因、眼睛显示完整 Key、DeepSeek / 智谱 Key 链接三项，均已完成。真实预览数据上确认：models.json 启动时自动补上 claude-opus-4-8 的 1M 上下文 / 128k 输出 / 自适应思考；字幕 3895 段合并为 453 段（98% 在 10–15 秒）。设置页、字幕与查词、失败原因由三个子 agent 并行实现（D-43）。红 eb98160、e626a03、21021d8、af66b4a、a1d213c、59a991d、4352411、4fa05af、6bd1408、2822418、72becf2、d3145f2、798cf5b、c86d8ae、9b8d404、68dbd91 → 绿 5265d1e、2c45e61、ef9e81c、f18eecb、b487a65、bd0a9d7、da11458、e57c03b、2901925、9687377、6e6328a、8d9178f、6a4578c、4aa3c4c、51fa215、ba8485a、f3637f8 |
| R7e 精读完整度 | 未开始 | | | |
| R8 发布 | 未开始 | | | |

## 附录 A：对 vendor/video-report-agent 的修改（只允许以下各项）

| 编号 | 内容 | 状态 |
|---|---|---|
| V1 | Windows 兼容：所有文本读写显式使用 UTF-8；`execution.py` 在 Windows 上使用 `CREATE_NEW_PROCESS_GROUP`，并用 `taskkill /T /F` 结束进程树（taskkill 经模块导入时捕获的真实 `Popen` 调用，避免被测试对 `subprocess.Popen` 的拦截劫持）；`pyproject.toml` 增加 `tzdata` 依赖；测试替身改成跨平台写法（fake-pi 在 Windows 上改为 `.cmd` 启动器 + UTF-8 stdio 的 Python 脚本；`test_asr.py` 的 `os.kill(pid, 0)` 探活改为 `OpenProcess` + `WaitForSingleObject` 的跨平台实现） | 完成（2026-09-25，M1）；2026-09-26 补：`test_report_modes.py` 假 Pi 脚本读 `input.json` 和模板时显式用 UTF-8，D1 不再依赖 `PYTHONUTF8`（R1） |
| V2 | `PiRunner.__init__` 增加关键字参数：`tools`（默认 `"read,write,edit,bash"`，review 时追加 `inspect_report` 的逻辑不变）；`extra_prompt`（追加到用户提示末尾）；`extra_files`（复制进工作区）；`agent_dir`（覆盖模块导入时按当前工作目录算出的 `PI_AGENT_DIR`，包括 `auth.json` 的查找、`initialize_pi_config` 和传给子进程的 `PI_CODING_AGENT_DIR`）；`command_prefix`（例如 `[node.exe, cli.js]`，替代 `shutil.which("pi")`）。所有参数都取默认值时，行为与修改前完全一致 | 完成（2026-09-25，M4；基线夹具 tests/fixtures/pi-command-baseline.json 锁定默认命令） |
| V3 | `pipeline.py` 把 `from .report_image import render_report_image` 从文件顶部移到 `generate()` 函数内部使用它的地方。原因：`paraformer.py` 在运行途中会导入 `pipeline`，顶部导入会连带加载 playwright，而打包版不带 playwright | 完成（2026-09-25，M4） |
| V4 | （撤回）同一会话多轮写作所需的 `follow_up` 参数。用户 2026-09-28 选定分章独立运行，不需要修改 vendor | 不做 |

新增修改需要先征得用户同意并补进本表。V1、V2 可以整理成补丁提交给上游作者，但**向上游提 PR 之前要征得用户同意**。

## 附录 B：参考

- VRA：https://github.com/imexlovery/video-report-agent （commit `d060dfb`，2026-09-25）
- BiliSum（功能参考，不引入代码）：https://github.com/lycohana/BiliSum （v1.21.1）
- yt-dlp 的 JS 运行时要求：https://github.com/yt-dlp/yt-dlp/wiki/EJS
- Pi 的 Windows 说明：`E:\tools\Prometheus-Desktop\pi\node_modules\@earendil-works\pi-coding-agent\docs\windows.md`
- markmap：https://markmap.js.org/
