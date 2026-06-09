# Lakehouse and Spark

本项目是智能选股研究平台/量化研究控制台，不是 AI 荐股网站、自动交易系统或买卖点工具；所有输出均为研究信号，必须经过样本外验证、模拟盘、风控、许可证 gate 和人工复核。

## 分层

- Bronze/ODS：原始入湖，保留 source、license_id、ingest metadata。
- Silver/DWD：清洗和点时间修正后的事实表。
- Gold/DWS：因子、标签、训练样本、信号、回测、风险。
- ADS：dashboard/latest score/backtest/data quality summary。

## Spark

Spark 负责 bronze_to_silver、silver_to_gold、factor_materialization、label_build、training_matrix_build 的可迁移批处理语义；本地验收以 Spark local smoke 和 Spark/Polars consistency 为准。

## Lakehouse 格式

Iceberg local PoC 已验证。Hudi/Delta 保留 adapter/blocked reason，不阻塞两周 MVP。
