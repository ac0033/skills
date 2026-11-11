# skills 市场维护

本仓库只维护工具导航、Claude Code/Codex 两份市场清单和市场检查。Product Dev 源码、组件、产物、测试和发布位于 https://github.com/ac0033/product-dev，不在此重复维护。

- 保持市场名 ac0033-skills 和已登记插件身份；两份市场清单指向同一版本、同一实际插件目录。
- 工具先在独立仓库发布，市场 source 使用宿主已核实支持的格式并固定发行标签；同步 README 工具导航。
- PR 前运行 node --test tests/*.test.mjs。CI 对实际公开标签检查身份、清单版本、入口与内部资源，Linux/Windows 均通过后按风险做独立代码复审和增量一致性审。
- 合并入口为 GitHub PR merge API 或 gh pr merge，核对最终 SHA 与 CI，不绕过失败检查；工作树有并行会话时不移动、删除或修改其现场。
- 旧 Release、标签和下载资产永久保留。需要回退源码时从 Git 历史恢复，不保留第二份源码。

公开 README 面向使用者，只保留理解、安装、升级和使用所需内容；维护规则、执行过程和审查证据写在本文件或 PR。
