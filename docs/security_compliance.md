# Security and Compliance

本项目是智能选股研究平台/量化研究控制台，不是 AI 荐股网站、自动交易系统或买卖点工具；所有输出均为研究信号，必须经过样本外验证、模拟盘、风控、许可证 gate 和人工复核。

## 门禁

- no broker integration：不接券商实盘，不自动下单。
- RBAC：viewer 不能看未发布候选池、不能导出完整数据、不能运行实验。
- Separation of duties：报告提交者不能自审。
- Audit：submit/approve/export 等治理事件 append-only。
- License gate：display/export/share/snippet/redaction policy 必须在导出前检查。
- Forbidden wording：不得输出确定性收益或交易承诺。

## 密钥

`.env.example` 只允许占位符；真实 credentials 不进 Git。
