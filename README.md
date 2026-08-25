# skills

自研与收录的 Agent skills 集合。skill 是 Agent 的能力插件：一个目录一份 `SKILL.md`，Agent 在匹配的任务场景下加载并按其指引工作。

## 目录结构

- `语言风格 System Prompt.md` — 自研的中文表达风格规范（平实、清楚、结构化，反机器腔）
- `white-box-explainer/` — 自研 skill：把代码/数据科学/ML 项目讲成可复算、可复现、可转述的白盒（git submodule，独立仓库 [ac0033/white-box-explainer](https://github.com/ac0033/white-box-explainer)）
- `Humanizer-zh/` — 收录的第三方 skill：中文 AI 写作去痕（git submodule，fork 自 [op7418/Humanizer-zh](https://github.com/op7418/Humanizer-zh)，上游为 [blader/humanizer](https://github.com/blader/humanizer)，MIT 协议，LICENSE 保留在子目录内）

## 克隆

```bash
git clone --recursive https://github.com/ac0033/skills.git
```
