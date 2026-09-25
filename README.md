# Prometheus

把 B 站和 YouTube 视频整理成可以长期查阅的个人知识库的 Windows 桌面软件。

粘贴一个视频链接，Prometheus 会产出三样东西，并按同一套「分类 → 标题」归档：

- **精读报告**：沿用 [video-report-agent](https://github.com/imexlovery/video-report-agent) 的精读写作规则，在正文需要的位置插入视频截图；
- **思维导图**：由报告提炼，节点可以跳回视频对应时刻；
- **原样字幕**：语音识别的原始结果，可以导出 SRT / TXT。

## 状态

规划阶段。完整规格、技术栈和里程碑见 [docs/PLAN.md](docs/PLAN.md)，设计决策见 [docs/DECISIONS.md](docs/DECISIONS.md)。

开发工具链位于 `E:\tools\Prometheus-Desktop`，说明见其中的 `使用说明.md`。

## 致谢与授权

报告写作能力来自 [imexlovery/video-report-agent](https://github.com/imexlovery/video-report-agent)（以下简称 VRA）。VRA 以 git subtree 形式保存在 `vendor/video-report-agent`，保留原始提交历史。
VRA 作者已同意本项目对其代码进行二次开发，并按 MIT 许可发布。

本项目以 [MIT License](LICENSE) 发布。
