# Feature Store

本项目是智能选股研究平台/量化研究控制台，不是 AI 荐股网站、自动交易系统或买卖点工具；所有输出均为研究信号，必须经过样本外验证、模拟盘、风控、许可证 gate 和人工复核。

## Offline store

`data/gold/factor_daily_panel_long` 与 `data/gold/model_feature_matrix_wide` 是离线训练与回测主入口。

## Point-in-time join

Feature join 必须使用 available_time 和 prediction_time，禁止使用未来成分股、未来复权因子或全样本 scaler。

## Online store PoC

realtime streaming/ops deployment 输出 online_feature_snapshot，Redis/Feast adapter 保留为后续生产化路线。
