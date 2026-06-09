# Data Contracts

本项目是智能选股研究平台/量化研究控制台，不是 AI 荐股网站、自动交易系统或买卖点工具；所有输出均为研究信号，必须经过样本外验证、模拟盘、风控、许可证 gate 和人工复核。

## 时间语义

- event_time：事件实际发生时间。
- publish_time：公告/新闻/财报公开时间。
- ingest_time：平台接收时间。
- available_time：研究系统可使用时间。
- prediction_time：模型形成横截面评分的时间。

规则：`available_time <= prediction_time`，`label_start_time > prediction_time`。

## 核心契约

覆盖 market_daily、minute、tick、orderbook、financial、announcement、news、macro、fund_flow、factor、label、signal、backtest、RAG claim、simulation、export_manifest。

## 质量门禁

schema、主键、缺失率、重复率、OHLC、成交量、交易日缺口、复权因子、行业/指数 as-of、许可证状态、quarantine 和 lineage 均需可查。
