# Realtime Streaming

本项目是智能选股研究平台/量化研究控制台，不是 AI 荐股网站、自动交易系统或买卖点工具；所有输出均为研究信号，必须经过样本外验证、模拟盘、风控、许可证 gate 和人工复核。

## Kafka / Redpanda

Topic 覆盖 raw、clean、factor、feature、signal、alert；idempotent key 使用 symbol + event_time + factor_name + window。

## Flink-style PoC

实现 event_time、watermark、late data、window aggregation 和 deterministic local job status。当前是 replay_simulated_not_live_market_data，不是正式实时选股信号。

## Sinks

Redis/online_feature_snapshot、ClickHouse adapter、PostgreSQL metadata、topic health 与 realtime-vs-offline diff report 均可用于演示与诊断。
