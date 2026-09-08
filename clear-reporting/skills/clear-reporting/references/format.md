# 材料格式 1.0

当前发行版使用一个 JSON bundle，避免强制大量小文件。完整可运行实例位于 `../examples/software/bundle.json`（以本文件目录为起点）；项目根为该实例所在目录。此处列出必填结构，实际检查规则以 scripts/reporting.py 和命令帮助为准。

顶层必填：schema_version=`1.0`、project_id、request_id、question、audience、evidence、knowledge、vocabulary、sections、report、checks、reader_questions。ID 是内部引用，正文用清楚名称。

| 对象 | 字段 |
|---|---|
| audience | goal；known_concepts 字符串列表。不把假定熟悉写成用户已确认 |
| evidence[] | id、claim、source、scope、verification、limitations 字符串列表 |
| source | path（项目内相对路径）、sha256（64位内容摘要）、locator（字段/筛选/位置及计算说明） |
| knowledge[] | id、question、claim、evidence_ids、kind、reasoning、limitations、status |
| vocabulary[] | id、name、aliases、meaning、example、prerequisite_ids、state、feedback_ref |
| sections[] | id、question、answer、knowledge_ids、concept_ids、context、example、limits |
| report | path（项目内相对路径）、sha256 |
| checks | fact_review、reader_review、reader_independent、user_understanding、feedback_ref |
| reader_questions | 针对本报告的问题字符串列表，不附标准答案 |

枚举：

- evidence.verification：verified / reported / unverified。
- knowledge.kind：observation / inference / recommendation / open。
- knowledge.status：supported / hypothesis / disputed / superseded / open。
- vocabulary.state：unexplained / explained / user_confirmed / questioned。
- checks.fact_review：passed / pending / failed。
- checks.reader_review：passed / pending / failed / unavailable。
- checks.user_understanding：unconfirmed / confirmed / questioned。

reader_independent 是布尔值。`reader_review=passed` 只允许与 `reader_independent=true` 同时使用。没有独立上下文时，即使同一 Agent 已根据 reader pack 完成分次表达自查，也应把自查另存为记录，并在 bundle 中使用 `reader_review=unavailable`、`reader_independent=false`；准备稍后补独立检查时使用 `pending`，不能把非独立自查写成 `passed`。feedback_ref 可以为空，但确认用户理解或词语认可必须有真实反馈引用。已解释不等于确认理解。前置概念必须存在且不能形成循环。

空列表表示不适用，不代表故意省略。例如不涉及新术语可用 vocabulary=[]；supported 结论不能没有证据。无来源时只能登记开放问题，不能声称已有支持。局限不存在与尚未检查是两回事。

数值的单位、分母、期间、基准和推导写入 claim、scope、locator、reasoning；当前程序验证这些字段存在及引用一致，不能证明它们在语义上充分。事实复核必须逐项看数值含义，不把非空字符串当作解释正确。

报告内容可以先在 sections 中准备，完成后保存正文，再计算 report.sha256。SHA256 只锁定内容，不是正确性认证。正式检查后任何改写均需重跑。

采用紧凑 JSON 也不能省略含义，推荐 UTF-8 和缩进便于人工复核。unsupported version、缺字段、未知引用、项目外来源、摘要变化必须报错，不能跳过。

## 配置与范围

project.json 的 schema_version 为1.0，source_roots 是非空项目内相对路径列表；check 会实际限制证据读取范围。init 生成的空数组文件仅作起草占位，实际校验以本次 bundle 为准，不把两处文件当作同步数据库。sections、reader_questions 和报告正文不能为空。


## 派生数字的计算

`calculate --input calculation.json` 接受 `{"operation":"mean","operands":["12","16"],"decimals":0}`，返回结果字符串 `14`、原操作数与方法。只使用十进制数字字符串，不接受表达式。

支持 sum、mean、difference（第一个减第二个）、ratio（第一个除第二个）、percent_change（操作数依次为旧值、新值，结果单位为百分比）。decimals 为 0—12，按 ROUND_HALF_UP 舍入。操作数最多 10000 个，每项最多 100 字符，指数和有效数量级在 -100 到 100；零分母和非有限值失败。

例如修改前 12、16 秒，修改后 7、9 秒：分别算均值 14 和 8，再以 difference 的 ["14","8"] 算减少 6 秒。不能据此自行声称每次减少 5—9 秒。保留原始精度到最后一步，避免用已舍入数值重复计算比例。输入和输出作为项目计算记录保存；check 不会自动重算报告中所有数字。
