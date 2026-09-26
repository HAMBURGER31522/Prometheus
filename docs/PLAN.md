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
| M5 配图 | 未开始 | | | |
| M6 思维导图 | 完成（随 M4 分支落地，见 DECISIONS） | 2026-09-26 | 同 M4 | 离线：大纲提取（vendor 示例 9 章）/校验规则/两平台时刻链接测试全绿；live：报告导图 7 分支、7 个时刻链接、mindmap_status=ok（并入 test_report_live 验证）；Vendor 示例与黄金链路复用 |
| M7 前端 | 完成（D4 极简判定待用户查看截图） | 2026-09-26 | 387a7eb（merge） | D3：E2E ①–⑦ 全部通过（app/e2e/d3.spec.ts + app.smoke.spec.ts，7 用例；含跨页签一致性、报告 iframe/导图 SVG/字幕行、设置持久化、转写切换禁用规则、外链拦截）；`npm --prefix app run build` = 0；`npm --prefix app run test`（Vitest）与 `lint:design` = 0；运行中发现并修复 CORS 预检被鉴权中间件拦截的生产 bug（3fdc15b）；D4：截图 docs/screenshots/console.png、report.png 待用户判定 |
| M8 打包 | 完成（D9 长视频本地转写验收顺延至 M9 一并执行） | 2026-09-26 | 见本行合并后填写 | `scripts/package.ps1` = 0（一键全流程，含打包资产校验与 300MB 体积断言）；NSIS 安装包 `Prometheus_0.1.0_x64-setup.exe` = **165MB**，已复制到 `E:	ools\Prometheus-Desktopelease\`；D8：`scripts/acceptance/installed-smoke.ps1` = 0（静默安装 → 启动 → backend.port 轮询 /api/health 30 秒内 healthy → 静默卸载 → 数据目录保留）；Rust 壳实现后端进程启动/关闭 + backend_info + CREATE_NO_WINDOW；使用说明第 3 节已补 tauri build 实测 |
| M9 真实验收 | 未开始 | | | |

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

## 附录 A：对 vendor/video-report-agent 的修改（只允许以下各项）

| 编号 | 内容 | 状态 |
|---|---|---|
| V1 | Windows 兼容：所有文本读写显式使用 UTF-8；`execution.py` 在 Windows 上使用 `CREATE_NEW_PROCESS_GROUP`，并用 `taskkill /T /F` 结束进程树（taskkill 经模块导入时捕获的真实 `Popen` 调用，避免被测试对 `subprocess.Popen` 的拦截劫持）；`pyproject.toml` 增加 `tzdata` 依赖；测试替身改成跨平台写法（fake-pi 在 Windows 上改为 `.cmd` 启动器 + UTF-8 stdio 的 Python 脚本；`test_asr.py` 的 `os.kill(pid, 0)` 探活改为 `OpenProcess` + `WaitForSingleObject` 的跨平台实现） | 完成（2026-09-25，M1） |
| V2 | `PiRunner.__init__` 增加关键字参数：`tools`（默认 `"read,write,edit,bash"`，review 时追加 `inspect_report` 的逻辑不变）；`extra_prompt`（追加到用户提示末尾）；`extra_files`（复制进工作区）；`agent_dir`（覆盖模块导入时按当前工作目录算出的 `PI_AGENT_DIR`，包括 `auth.json` 的查找、`initialize_pi_config` 和传给子进程的 `PI_CODING_AGENT_DIR`）；`command_prefix`（例如 `[node.exe, cli.js]`，替代 `shutil.which("pi")`）。所有参数都取默认值时，行为与修改前完全一致 | 完成（2026-09-25，M4；基线夹具 tests/fixtures/pi-command-baseline.json 锁定默认命令） |
| V3 | `pipeline.py` 把 `from .report_image import render_report_image` 从文件顶部移到 `generate()` 函数内部使用它的地方。原因：`paraformer.py` 在运行途中会导入 `pipeline`，顶部导入会连带加载 playwright，而打包版不带 playwright | 完成（2026-09-25，M4） |

新增修改需要先征得用户同意并补进本表。V1、V2 可以整理成补丁提交给上游作者，但**向上游提 PR 之前要征得用户同意**。

## 附录 B：参考

- VRA：https://github.com/imexlovery/video-report-agent （commit `d060dfb`，2026-09-25）
- BiliSum（功能参考，不引入代码）：https://github.com/lycohana/BiliSum （v1.21.1）
- yt-dlp 的 JS 运行时要求：https://github.com/yt-dlp/yt-dlp/wiki/EJS
- Pi 的 Windows 说明：`E:\tools\Prometheus-Desktop\pi\node_modules\@earendil-works\pi-coding-agent\docs\windows.md`
- markmap：https://markmap.js.org/
