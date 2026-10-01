---
name: 问题反馈
about: 软件出错、结果不对、用起来别扭
title: ""
labels: bug
---

**发生了什么**

（哪一步、看到了什么、本来应该是什么样）

**怎么重现**

1. 
2. 
3. 

**视频链接**（方便的话；私人视频可以不填）

**环境**

- 软件版本：（Windows「设置 → 应用 → 安装的应用」里 Prometheus 显示的版本，例如 1.0.0）
- Windows 版本：（例如 Windows 11 23H2）
- 用的 Agent 和模型：（例如 Pi + DeepSeek、Codex CLI 官方登录 gpt-6.1-sol「高」）
- 转写方式：（云端必剪 / 本地 / 自定义）

**日志**

请附上这两个文件（**先打开看一眼，删掉 API Key、私人内容**）：

- 后台日志：`%APPDATA%\com.hamburger31522.prometheus\backend.log`（每次启动会覆盖，出错后先别重启软件）
- 出错条目的步骤记录：`<知识库文件夹>\.prometheus\cache\<条目ID>\run.trace.jsonl`

控制台里失败条目的「详情」可以直接复制原始报错，也请贴上。
