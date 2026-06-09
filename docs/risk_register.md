# Risk Register

本项目是智能选股研究平台/量化研究控制台，不是 AI 荐股网站、自动交易系统或买卖点工具；所有输出均为研究信号，必须经过样本外验证、模拟盘、风控、许可证 gate 和人工复核。

| 风险 | 当前状态 | 处理方式 | Owner |
| --- | --- | --- | --- |
| Spark / Iceberg / Hudi / Delta Lake 依赖复杂 | 部分关闭 | Spark local + Parquet 可运行，Iceberg local PoC，Hudi/Delta 保留 adapter/blocked reason | data-platform |
| Flink 实时链路复杂 | 部分关闭 | replay simulated feed + Flink-style deterministic jobs；正式集群后续推进 | streaming |
| 高级模型依赖冲突 | 部分关闭 | MASTER/StockMixer/HIST/TRSR 先 small-sample adapter，禁止生产化宣传 | modeling |
| 数据许可证/外部数据接入 | 未关闭 | license_id、display/export policy、redaction、manual review | compliance |
| 实盘/券商/自动交易边界 | 已门禁 | no broker integration、simulated=true、broker_route=none_disabled | governance |
| RAG 幻觉或无证据回答 | 部分关闭 | claim-level citation、无引用拒答、eval gate | rag |
| 回测过拟合 | 部分关闭 | walk-forward、成本、滑点、capacity、blocked reason、严禁收益承诺 | quant |
| 部署密钥泄漏 | 部分关闭 | .env.example 只放占位符，CI secret scan，真实 credentials 不进 Git | ops |
