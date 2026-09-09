# Agent Skills

自研与收录的 Agent 技能集合。每个技能以 `SKILL.md` 为入口，按任务需要提供写作、讲解或汇报规则；部分技能附有脚本与示例。

## 技能目录

| 入口 | 适用任务 | 配套内容 |
|---|---|---|
| [clear-reporting](clear-reporting/README.md) | 把已有结果写成有依据、易理解的汇报 | 自包含 Skill、材料格式、示例、Python 检查程序与测试，可选插件包装 |
| [human-writing](human-writing/SKILL.md) | 中文写作、修订与语言风格检查 | 场景参考、修订规范与 `check_prose.py` |
| [structured-writing](structured-writing/SKILL.md) | 文章结构、论证与量化表达 | 金字塔原则、模板和完整示例 |
| [white-box-explainer](https://github.com/ac0033/white-box-explainer) | 讲清代码、数据科学与机器学习项目 | 独立仓库，以 Git submodule 收录 |
| [Humanizer-zh](https://github.com/ac0033/Humanizer-zh) | 编辑中文文本中的常见 AI 写作痕迹 | 第三方技能的个人 fork，以 Git submodule 收录 |
| [语言风格 System Prompt](语言风格%20System%20Prompt.md) | 中文表达风格约定 | 单文件提示词 |

## 获取与使用

```bash
git clone --recurse-submodules https://github.com/ac0033/skills.git
cd skills
```

已有克隆需要补齐子模块时，运行：

```bash
git submodule update --init --recursive
```

让支持读取文件的 Agent 打开所选技能的 `SKILL.md`，并提供任务与材料。插件、技能安装目录和调用方式取决于宿主；clear-reporting 的适配说明见 [安装指南](clear-reporting/adapters/INSTALL.md)。

子模块固定在父仓库记录的提交。仅更新父仓库后，还需执行上述 `git submodule update`；它不会自动切换到子模块上游最新版本。

## 本地检查

clear-reporting 使用 Python 3.10+ 标准库：

```bash
cd clear-reporting
python -m unittest discover -s skills/clear-reporting/tests -v
python skills/clear-reporting/scripts/reporting.py --help
```

在仓库根目录查看中文文本检查器的参数：

```bash
python human-writing/scripts/check_prose.py --help
```

检查器能验证指定的结构或规则，不能替代对事实、原意和表达质量的人工判断。

## 来源与许可

Humanizer-zh 的上游为 [op7418/Humanizer-zh](https://github.com/op7418/Humanizer-zh)，其核心规则来自 [blader/humanizer](https://github.com/blader/humanizer)。各子目录保留各自的来源与许可文件，见对应 README、SKILL 和 LICENSE；本仓库不为所有收录内容统一声明新的许可。
