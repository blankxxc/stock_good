# Architecture

本项目是智能选股研究平台/量化研究控制台，不是 AI 荐股网站、自动交易系统或买卖点工具；所有输出均为研究信号，必须经过样本外验证、模拟盘、风控、许可证 gate 和人工复核。

## 分层

1. 数据源与契约：日频、分钟、tick/盘口 replay、公告、新闻、宏观、行业/概念、资金流；所有表包含 event_time / publish_time / ingest_time / available_time / data_version。
2. 湖仓与批处理：Bronze/ODS -> Silver/DWD -> Gold/DWS -> ADS；Spark 本地任务与 Parquet/DuckDB/Polars 为 MVP 底座，Iceberg 为 local PoC。
3. 流式 PoC：Redpanda/Kafka topic manifest、replay simulated producer、Flink-style event-time jobs、online feature snapshot。
4. 研究计算：74 个离线因子、事件/market regime/关系传播因子、5d/10d 标签、LightGBM/Qlib-compatible recorder、MASTER/StockMixer/HIST/TRSR 小样本 adapter。
5. 证据与治理：claim-level RAG、paper simulation、RBAC、append-only audit、license gate、export_manifest。
6. 产品与运维：FastAPI、Next.js Research Console、Docker Compose、Prometheus/Grafana、backup/restore smoke、CI gates。

## 关键设计原则

- point-in-time 优先，禁止未来信息。
- 研究候选池和报告导出必须可追溯到 data/factor/model/label/RAG 版本。
- 实时链路和高级模型默认是研究候选/PoC，不进入正式交易信号。
