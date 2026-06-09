# Factor System

本项目是智能选股研究平台/量化研究控制台，不是 AI 荐股网站、自动交易系统或买卖点工具；所有输出均为研究信号，必须经过样本外验证、模拟盘、风控、许可证 gate 和人工复核。

## 覆盖

- 离线因子：价格收益、动量、反转、波动率、流动性、成交量、风险暴露，共 74 个。
- 事件因子：新闻/公告情绪、事件数量、负面事件、novelty、authority、decay。
- Market regime：breadth、return、volatility、drawdown、风格轮动、industry dispersion、liquidity regime。
- 关系传播：industry/concept/supply-chain/news co-mention/price correlation/lead-lag neighbor spillover。

## 因子准入

coverage、point-in-time、RankIC 稳定性、分层单调性、中性化后有效性、成本后收益、与已有因子相关性、样本外增量贡献均需记录。
