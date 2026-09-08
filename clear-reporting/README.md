# Clear Reporting

把已有工作成果组织为用户能理解、追问的汇报。适用于软件修改、数据分析、研究等项目。一个自包含 Skill、结构化材料约定、Python 检查程序和可选 Codex 包装。

## 从这里开始

让 Agent 读取 [Skill 入口](skills/clear-reporting/SKILL.md)，再提供本次问题、可读取的项目材料及报告输出位置。无需安装 memory 或其他 Skills；有文件和脚本能力时可持久化与核验，无则按文本流程使用。

推荐首次请求：

> 使用 clear-reporting，把这份已有结果讲清楚。先说明具体对象和背景，再解释数字、结论及限制；沿用我熟悉的词。只使用指定材料，不改变项目执行安排。

## 核心分工

`项目产物 → 证据 → 结论及依据 → 面向用户的解释 → 检查与反馈`

这就是参考对话中“认知编译器”的实际落点：模型写正文前先准备可核对的中间材料，避免每次从长日志即兴发挥。材料层次不是必须部署的服务，也不等于多个 Agent。

项目保存事实、专业词义、理解记录；工具包保存通用格式、规则、示例和脚本。Codex 清单仅作为包装，核心不调用任何特定平台 API。

## 文件导航

- [平台使用与安装](adapters/INSTALL.md)：通用文件/纯文本方式与 Codex 包装说明。
- [材料格式](skills/clear-reporting/references/format.md)：字段与状态。
- [流程](skills/clear-reporting/references/workflow.md)：项目如何接入及恢复。
- [正反例](skills/clear-reporting/references/examples.md)：软件、分析、研究三类。
- [可运行样例](skills/clear-reporting/examples/software/bundle.json)：教学用虚构数据。
- [实现与验证记录](VALIDATION.md)：已测内容和未测限制。
- plan.md：设计历史，实际实现范围以本 README 和 VALIDATION.md 为准。

## 本地运行

在本工具包目录，使用 Python 3.10+（只依赖标准库）：

```text
python skills/clear-reporting/scripts/reporting.py --help
python skills/clear-reporting/scripts/reporting.py check --bundle skills/clear-reporting/examples/software/bundle.json --project skills/clear-reporting/examples/software
python -m unittest discover -s skills/clear-reporting/tests -v
```

程序只验证可机械判断的部分，不能证明结论真实、语言充分或用户掌握。独立阅读与用户反馈单独记录；跨模型效果需要实际对照，不能由单元测试推断。

派生数字用 `python skills/clear-reporting/scripts/reporting.py calculate --input calculation.json` 核对；请求格式见材料格式。纯文本模式仍可能出现错误，不能承诺跨模型相同质量。
