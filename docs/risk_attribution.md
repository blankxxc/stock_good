# Risk Attribution

本项目是智能选股研究平台/量化研究控制台，不是 AI 荐股网站、自动交易系统或买卖点工具；所有输出均为研究信号，必须经过样本外验证、模拟盘、风控、许可证 gate 和人工复核。

## 风险维度

行业、size、beta、value、momentum、volatility、liquidity、quality、growth、residual volatility、单票权重、行业集中度、turnover、tracking error、drawdown。

## Day12 风控 gate

组合必须通过单票权重、行业权重、ST/停牌/涨跌停、ADV participation、最大回撤、style exposure、tracking error、TopK concentration 等检查。

## 报告

风险归因报告用于解释研究组合暴露和失败模式，不用于自动交易。
