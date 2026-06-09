# Final Acceptance Report

本项目是智能选股研究平台/量化研究控制台，不是 AI 荐股网站、自动交易系统或买卖点工具；所有输出均为研究信号，必须经过样本外验证、模拟盘、风控、许可证 gate 和人工复核。

## 完成状态

Day 1 到 Day 14 已形成本地可运行、可测试、可演示的研究平台闭环。Day 14 的目标是全量联调、验收、演示、文档、风险复盘、覆盖矩阵复核，已通过 `scripts/check_day14_acceptance.py` 固化。

## 成熟度

- L2：批量数据、湖仓分层、数据质量、防泄漏、离线因子、标签、LightGBM baseline、回测、RAG、网站、许可证与导出治理。
- L1-L2：Spark、本地实时 replay、关系图、模拟盘、RBAC/audit、可观测性、部署 smoke。
- L1 / research_candidate_only：Flink 正式集群、高级模型生产集成、Feast adapter、完整 K8s 上线。

## 剩余风险

详见 `docs/risk_register.md`。主要剩余风险包括真实授权数据接入、Spark/Iceberg 生产化、Flink 集群稳定性、高级模型依赖、真实数据许可证、实盘边界和运维安全。

## blocked reason

1. 官方 Qlib 数据未下载，当前只验证 package 和 minimal recorder。
2. MASTER/StockMixer/HIST/TRSR 是 small-sample adapter，不是官方生产训练。
3. Kafka/Flink 是 replay/local PoC，不是正式实时选股链路。
4. Iceberg 是 local PoC，Hudi/Delta 是 adapter/backlog。
5. 真实券商实盘、自动下单、投资建议明确不在范围内。

## 覆盖矩阵

最终覆盖矩阵见 `docs/demo/coverage_matrix.md`，关键技术 Spark、Lakehouse、Flink、RAG、风险归因、导出合规均已进入每日计划并有 artifact 或 blocked reason。
