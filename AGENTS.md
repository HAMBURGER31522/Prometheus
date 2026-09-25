# Prometheus — 执行 Agent 须知

本文件约束所有在本仓库工作的 AI Agent（Claude Code、Codex、Cursor 等）。与本文件冲突的临时想法，一律以本文件和 `docs/PLAN.md` 为准。

## 开工前必读

1. `docs/PLAN.md` 全文：它就是规格。Goal / Boundaries / Done When 已经由用户确认。
2. `docs/DECISIONS.md`：每个已定选择背后的理由。
3. `E:\tools\Prometheus-Desktop\使用说明.md`，以及各工具目录里的 `使用说明.md`。

## 两条底线

1. **规格先行**：只实现 `docs/PLAN.md` 里写明的内容。发现规格有缺口、矛盾，或者 Done When 做不到时，**停下来问用户**，不要自己改 Goal / Boundaries / Done When，也不要实现「明确不做」清单里的任何东西。
2. **红绿最小实现**：每个行为先写测试，运行它，**亲眼看到它以正确的理由失败**（是断言失败，不是导入错误或拼写错误），把失败的测试单独提交一次（提交信息带 `(red)`），然后写刚好让它通过的最少代码，再提交。没有红过的绿是假绿。重构只在全绿时做，而且不增加行为。

## 环境

- 每个新终端先执行 `. E:\tools\Prometheus-Desktop\env.ps1`，然后运行 `verify.ps1`，退出码必须为 0。
- 不要往 C 盘安装任何工具，不要 `npm install -g`，不要修改用户级或系统级环境变量。Python 依赖只用 uv 管理。
- 所有文件读写一律显式指定 `encoding="utf-8"`：本机控制台编码是 cp936（GBK）。
- `.ps1` 脚本只写 ASCII 字符（Windows PowerShell 5.1 会按 GBK 读取没有 BOM 的脚本）。
- 需要新工具或新版本时，按 `E:\tools\Prometheus-Desktop\使用说明.md` 的升级原则操作，并同步更新文档和 `verify.ps1`。

## 代码结构

- 前后端都**按功能分文件夹**：`console`、`report`（精读）、`mindmap`、`subtitle`、`settings`，后端另有 `ingest`、`transcribe`、`figures`、`library`、`tasks`、`api`。让人一眼就能看出哪个文件夹管字幕、哪个管精读、哪个管思维导图。不要建 `utils/`、`helpers/`、`common/` 这类杂物文件夹；确实共用的代码放 `shared/`，并且说明原因。
- `vendor/video-report-agent` 是上游 VRA 的 subtree。**只允许**做 `docs/PLAN.md` 附录 A 列出的修改；每次修改都在附录 A 登记，并配测试。
- 不做投机性抽象，不顺手重构与当前里程碑无关的代码。

## Git 与推送

- 远程仓库：`origin` = https://github.com/HAMBURGER31522/Prometheus.git（公开仓库）。
- 每个里程碑一个分支，命名写在 `docs/PLAN.md`，例如 `m1-windows-portability`。
- 提交信息格式：`type(scope): 描述`。type 取 test / feat / fix / refactor / docs / build / chore；scope 取功能文件夹名。红阶段的提交在末尾加 `(red)`。
- 里程碑的 Done When 命令全部通过后：`git checkout main`，`git merge --no-ff <分支>`，然后 `git push origin main <分支>`。
- **禁止** `push --force`、禁止改写 `main` 的历史、禁止跳过 hooks。
- **绝不提交**：API Key、`.env`、cookies 文件、数据目录、`tmp/`、打包用的运行时二进制、视频音频文件。提交前运行 `git status` 检查。

## 声明完成之前

- 逐条运行当前里程碑的 Done When 命令，读取退出码，把结果（日期、commit、每条命令的退出码）写进 `docs/PLAN.md` 的「进度记录」表。
- 需要真实 API 调用的验收（pytest 的 `live` 标记、`scripts/acceptance/*.ps1`）会产生费用，只在里程碑要求时运行。所需的 Key 和 cookies 文件路径由用户在运行时通过环境变量提供，**缺少时停下来向用户要**，不要编造，也不要跳过。
- D4（极简设计）和 D6（配图后的报告质量）需要用户本人判定：准备好截图或 A/B 报告后，停下来请用户查看，并把用户的结论记录到 `docs/acceptance.md`。
- 如实报告：测试失败就贴出失败输出；某一步没做就明确说没做。不要把「静态检查通过」说成「实际验证过」。

## 文档维护

- `docs/PLAN.md`：更新进度记录、附录 A；**规格部分只在用户同意后修改**。
- `docs/DECISIONS.md`：记录新的、会影响后续开发的重要选择（日期、问题、决定、原因、代价）。
- 工具链文档：首次在项目里跑通 `uv sync`、`npm ci`、`tauri build` 等命令后，到 `E:\tools\Prometheus-Desktop\使用说明.md` 第 3 节补上实测结果。
