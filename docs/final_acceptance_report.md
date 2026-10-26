# Final Acceptance Report

本项目是智能选股研究平台/量化研究控制台，不是 AI 荐股网站、自动交易系统或买卖点工具；所有输出均为研究信号，必须经过样本外验证、模拟盘、风控、许可证 gate 和人工复核。

## 完成状态

foundation 到 final acceptance 已形成本地可运行、可测试、可演示的研究平台闭环。final acceptance 的目标是全量联调、验收、演示、文档、风险复盘、覆盖矩阵复核，已通过 `scripts/check_final_acceptance_acceptance.py` 固化。

## 成熟度

- L2：批量数据、湖仓分层、数据质量、防泄漏、离线因子、标签、LightGBM baseline、回测、RAG、网站、许可证与导出治理。
- L1-L2：Spark、关系图、模拟盘、RBAC/audit、可观测性、部署 smoke。
- L2：COGRASP 和情绪融合 LightGBM 日频预测，仍需持续评估样本外表现。

## 剩余风险

详见 `docs/risk_register.md`。主要剩余风险包括真实授权数据接入、Spark/Iceberg 生产化、日频模型样本外表现、真实数据许可证、实盘边界和运维安全。

## blocked reason

1. 模型入口仅保留 COGRASP 和情绪融合 LightGBM，实验记录使用本地文件。
2. 模型表现页读取当前两个模型的最新推理报告，指标对应各自的样本外测试区间。
3. Iceberg 是 local PoC，Hudi/Delta 是 adapter/backlog。
4. 真实券商实盘、自动下单、投资建议明确不在范围内。

## 覆盖矩阵

最终覆盖矩阵见 `docs/demo/coverage_matrix.md`，关键技术 Spark、Lakehouse、RAG、风险归因、导出合规均已进入每日计划并有 artifact 或 blocked reason。
