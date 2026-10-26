# 日频模型

当前网站和日频更新流水线仅使用以下两个模型：

| 模型 | 输入 | 训练入口 | 预测报告 |
| --- | --- | --- | --- |
| COGRASP | 当前沪深300量价序列、收益相关性图 | `scripts/train_cograsp_current.py` | `reports/research_loop/live_predictions_report.json` |
| 情绪融合 LightGBM | 股票时序、市场情绪代理、可选新闻事件 | `scripts/train_sentiment_event_fusion.py` | `reports/research_loop/sentiment_event_predictions_report.json` |

`/api/models` 和模型表现页直接读取上述报告，展示模型版本、最新输入日、股票覆盖和样本外指标。两个模型使用各自的时间顺序训练、验证和测试区间，比较指标时须同时查看测试日期。

日频更新依次刷新行情、指数、因子、时间可用性校验、标签和两个模型的结果。没有数据变化时使用指纹跳过已完成步骤。当前流程只生成研究输出，不执行交易。

`models/research_loop_research_loop.py` 中的标签、历史回测、基准评估与本地文件记录仍为研究和论文实验共用代码，不作为额外的当前选股模型入口。

论文实验的绘图与基线比较依赖单独放在 `research` 可选依赖组，需要运行这些脚本时使用 `uv sync --extra cograsp --extra research` 安装。
