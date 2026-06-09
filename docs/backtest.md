# Backtest

本项目是智能选股研究平台/量化研究控制台，不是 AI 荐股网站、自动交易系统或买卖点工具；所有输出均为研究信号，必须经过样本外验证、模拟盘、风控、许可证 gate 和人工复核。

## 规则

- 使用 purged walk-forward split。
- 处理交易成本、滑点、停牌、ST、涨跌停、退市、流动性、容量。
- 输出 IC、RankIC、ICIR、TopK return、quantile spread、long-short spread、turnover、drawdown、Sharpe、Calmar、hit rate、capacity。

## 解读边界

回测是研究证据，不是未来收益承诺。任何导出报告必须经过 license gate、RAG citation gate、forbidden wording gate 和人工审核。
