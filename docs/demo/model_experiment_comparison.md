# 日频模型表现

| 模型 | 页面 | 结果来源 |
| --- | --- | --- |
| COGRASP | `/scores?model=cograsp` | `reports/research_loop/live_predictions_report.json` |
| 情绪融合 LightGBM | `/scores?model=sentiment_event` | `reports/research_loop/sentiment_event_predictions_report.json` |

`/models` 展示最新输入日期、预测覆盖、模型版本和各自的样本外 MAE、MSE、IC、RankIC；不使用旧样例模型数据。
