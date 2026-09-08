# 安装与平台适配

## 无需安装服务的通用方式

保留整个 `skills/clear-reporting/` 目录，向 Agent 提供其中 SKILL.md 的实际路径，再提供本次问题与获准读取的材料。目录内含全部工作流、参考、脚本和示例，不依赖外层插件目录。

Agent 不支持读文件时，将 SKILL.md 和本次需要的参考内容粘贴到会话，再附任务材料。不能自动保存或检查来源时如实标明；输出可以复制的 bundle 用于下次恢复。

宿主支持 Skill 自动发现时，根据该宿主自己的文档放置**整个 Skill 目录**。不同平台的自动发现路径不保证相同；未验证的平台不提供猜测命令。其通用显式加载方式仍可使用。

## Python 检查

需要 Python 3.10+，没有第三方依赖。从工具包根执行 README 的命令。Windows 若没有 `python` 命令，使用已安装 Python 的绝对路径；PowerShell 在带空格的路径前加 `&`。其他系统使用自己的 Python 可执行文件。

无 Python 时不用为核心汇报强制安装。可以按 format.md 和 workflow.md 手工处理，注明没有程序验证。需要安装 Python 时参考 [Python 官方下载页](https://www.python.org/downloads/)，由用户选定环境后操作，本工具不会联网安装。

## Codex

本目录提供 `.codex-plugin/plugin.json`，指向 `./skills/`。包装清单与核心 Skill 分开，安装状态须通过宿主查询确认。

无需插件市场的使用路径仍是显式读取 SKILL.md。若要自动发现，可使用宿主支持的本地 Skill 安装方式，或通过 Codex 插件管理界面选择本工具包。本次使用个人市场登记安装，具体命令见下文。

如果宿主界面不提供本地目录安装，不假定存在该按钮；继续显式读取入口，另按该版本官方安装流程配置。分发本目录时要包含 skills，不能只分发清单。

## 项目首次接入

```text
python skills/clear-reporting/scripts/reporting.py init --project <项目绝对路径> --project-id <唯一标识>
```

该命令创建最小配置，拒绝覆盖已有配置，不扫描项目或生成事实。参考 software 示例，在新 request_id 下准备报告及 bundle，再运行 check。项目输入默认只在所指定项目根内，外部材料需用户明确提供为项目内获准副本或文本；工具不自动下载。

更新工具时保留项目 reporting 文件。卸载入口或包装不会删除项目报告。多 Agent 每个请求独立文件，由指定写入者发布，避免同时改一个全局文件。

## 可选能力

- 无 memory：使用项目内材料和真实反馈记录。
- 无其他 Skills：本工具自包含，不需补装。
- 无独立会话：导出 reader-pack 后用户手动开启新会话；未做就标 unavailable。
- 无绘图：用表格、算例、文字流程。
- 无联网：仅解释现有材料，不宣称外部事实已核实。

`reader-pack` 只给独立读者最终报告、阅读目标与问题。报告自身可能有源文件链接，读者只读正文，不访问链接；问题若含答案也会破坏独立性，发送前由复核者检查。导出文件与材料本身可能含项目数据，应留在原授权环境内。


## 本次已验证的 Codex CLI 安装路径

本工具通过个人市场 `personal` 登记，以 `codex plugin add clear-reporting@personal --json` 安装；可用 `codex plugin list --marketplace personal --json` 查看是否 enabled。新会话加载新增技能，原会话的技能清单不保证即时更新。

源目录是开发权威版本，个人市场安装源是发布副本，Codex另有安装缓存。更新时先同步发布副本、使用宿主plugin-creator更新缓存版本，再重新安装；不直接修改缓存中的代码。卸载使用 `codex plugin remove clear-reporting@personal` 前先以该CLI版本帮助确认参数。
