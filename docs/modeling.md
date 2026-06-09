# Modeling

本项目是智能选股研究平台/量化研究控制台，不是 AI 荐股网站、自动交易系统或买卖点工具；所有输出均为研究信号，必须经过样本外验证、模拟盘、风控、许可证 gate 和人工复核。

## Baseline

LightGBM baseline 采用 5d/10d 横截面标签、walk-forward split、Qlib-compatible recorder、IC/RankIC/TopK 等指标。

## Advanced adapters

MASTER、StockMixer、HIST、TRSR 均为 small-sample research candidate。它们用于比较输入语义和候选模型形态，不代表官方生产训练或收益承诺。

## 禁止事项

禁止只报告最佳 seed、最佳年份、单次回测；模型输出不得直接变成交易指令。
