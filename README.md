# stock_good — 智能选股研究平台

stock_good 是一个面向量化研究与智能选股的本地全栈工程样例。项目以“可追溯数据、可复现实验、可验证因子、可回测模型、可解释研究证据、可视化研究工作台”为核心目标，当前已完成 Day 1 至 Day 7 的本地闭环实现。

仓库地址：https://github.com/blankxxc/stock_good

## 项目定位

本项目不是自动荐股或实盘交易系统，而是研究型智能选股平台。系统输出的是：

- 横截面股票评分、排序和候选池；
- 离线因子、特征矩阵、标签和模型诊断；
- walk-forward 回测、风险归因、容量和交易成本分析；
- RAG/知识证据、研究假设和实验记录；
- 面向投研人员的 Web research console。

所有信号都必须经过样本外验证、模拟交易、风险约束和人工复核后，才可以作为进一步研究依据。项目不接券商实盘、不自动下单、不输出“必买/稳赚/目标价”等确定性投资建议。

## 当前完成度

| 阶段 | 主题 | 当前状态 |
| --- | --- | --- |
| Day 1 | 全栈工程骨架、数据契约、元数据治理、Spark/Flink/Kafka/Compose 基础 | 已完成 |
| Day 2 | 本地湖仓、批量接入、ODS/DWD/DWS/ADS、许可证治理、Iceberg PoC、ClickHouse ADS | 已完成 |
| Day 3 | 数据质量、quarantine、防泄漏、point-in-time、血缘、数据可信度页面/API | 已完成 |
| Day 4 | 74 个离线因子、Feature Store、点时间特征 join、Spark/Polars 一致性、因子页面/API | 已完成 |
| Day 5 | 5d/10d 标签、LightGBM baseline、walk-forward、回测/风险/容量、实验记录器、Qlib-compatible recorder | 已完成 |
| Day 6 | Redpanda/Kafka topic、replay simulated producer、Flink-style 实时因子、online feature snapshot、实时页面/API | 已完成 L1 PoC |
| Day 7 | 新闻/公告事件、FinBERT-compatible 情绪 baseline、事件因子、market regime、增强特征矩阵、ablation | 已完成 |

最近本地验收结果：

- Day4 acceptance: `status=ok`, `checks=15`, `failed=[]`, `factor_count=74`, `factor_rows=129796`, `feature_matrix_rows=1960`, `spark_consistency_status=passed`, `point_in_time_violations=0`。
- Day5 acceptance: `status=ok`, `checks=19`, `failed=[]`, `label_rows=3620`, `prediction_rows=413`, `holding_rows=105`, `split_count=3`, `feature_count=72`, `lightgbm_status=trained`, `qlib_status=minimal_qlib_recorder_available`, `leakage_check_status=passed`。
- Day6 acceptance: `status=ok`, `checks=24`, `failed=[]`, `feed_mode=replay_simulated_not_live_market_data`, `raw_events_written=137`, `flink_jobs_ready=5`, `realtime_factor_rows=162`, `online_feature_rows=36`, `diff_report.max_abs_diff=0.0`。
- Day7 acceptance: `status=ok`, `checks=18`, `failed=[]`, `text_model_status=lexicon_finbert_compatible_baseline_ready`, `event_factor_rows=29400`, `market_regime_rows=100`, `enhanced_feature_rows=1960`, `ablation_status=lightgbm_smoke_trained`。
- 完整测试：`39 passed, 24 warnings`。
- 前端路由：`route_count=21`。
- Next.js production build：23 个静态页面生成成功。

## 技术栈

后端与研究计算：

- Python 3.11
- FastAPI / Uvicorn
- Pandas / PyArrow / DuckDB
- Polars
- PySpark 3.5.3
- SQLAlchemy / Alembic
- pytest
- pyqlib 0.9.7

前端：

- Next.js App Router
- React
- TypeScript

数据与基础设施：

- Parquet 本地湖仓
- Iceberg Hadoop catalog PoC
- ClickHouse ADS
- PostgreSQL / Redis / Qdrant
- Redpanda/Kafka topic manifest
- Flink job graph manifest
- Spark local jobs
- Docker Compose
- Prometheus / Grafana

## 目录结构

```text
backend/                         FastAPI 后端、API 路由、Alembic migration
configs/                         数据源、因子、模型等配置
contracts/                       项目契约与治理约束
data/                            Bronze/Silver/Gold/ADS/样例数据/隔离数据
feature_store/                   Feature registry 与 point-in-time join
factors/                         离线因子计算引擎
frontend/                        Next.js research console
lakehouse/                       DuckDB 查询、Iceberg/Delta PoC 相关入口
models/                          Day5 研究闭环、Day7 事件/市场环境因子与 ablation
quality/                         Day3 数据质量、防泄漏、血缘与可信度逻辑
reports/                         验收报告、质量报告、回测报告、实验 artifacts
scripts/                         一键验收、pipeline、ClickHouse 装载等脚本
spark/                           Spark 本地批处理与因子物化任务
streaming/                       Kafka topic、replay producer 与 Flink-style 实时因子 PoC
warehouse_schema/                元数据仓库 SQL migration
```

## 核心功能

### 1. 数据契约与治理

- `data_contracts/*.schema.yaml` 覆盖行情、财务、公告、新闻、宏观、资金流、因子、标签、信号、回测、RAG claim 等数据契约。
- 元数据 migration 覆盖 dataset snapshot、schema registry、Spark/Flink job run、RAG claim、export manifest、backfill request、ADR、risk register 等。
- 数据源许可证 registry 明确 `authorized`、`restricted`、`not_authorized`、`adapter_pending` 等状态，并限制展示/导出边界。

### 2. 本地湖仓与批量接入

- Day2 pipeline 生成可复现 synthetic market 数据。
- Bronze/ODS：raw market、minute、tick、trade、orderbook、financial、announcement、news、macro、fund flow、northbound。
- Silver/DWD：清洗后的日频行情、分钟行情、财务、新闻事件、公告事件。
- Gold/DWS：因子面板、标签、训练样本、横截面信号、回测结果。
- ADS：dashboard summary、latest score、backtest summary、data quality summary。
- Iceberg PoC 已验证写入、读回、schema evolution、metadata files 与 snapshots。

### 3. 数据可信度、防泄漏与血缘

- synthetic mini market 覆盖停牌、ST、涨跌停、退市、新上市、公告晚于收盘、未来成分股、未来复权因子、全样本归一化泄漏、label 泄漏诱捕等场景。
- 数据质量报告覆盖 schema、主键重复、缺失、OHLC、成交量、交易日缺口、复权因子、行业、指数成分历史、延迟、重复率、修正率和 source license gate。
- 防泄漏检查验证 `feature.available_time <= prediction_time`、`label_start_time > prediction_time`、公告/新闻/财报发布时间、行业/指数 as-of、scaler fit window、purged split/embargo。
- 血缘报告连接 `source_table -> transform_job -> target_table -> snapshot/report`。

### 4. 因子库与 Feature Store

- 当前实现 74 个离线因子，覆盖价格收益、动量、反转、波动率、流动性、成交量、风险暴露等类别。
- 因子长表：`data/gold/factor_daily_panel_long`。
- 模型宽表：`data/gold/model_feature_matrix_wide`。
- 风险暴露：`data/gold/risk_factor_exposure`。
- 支持点时间 join，并验收 `point_in_time_violations=0`。
- Spark 与 Polars 因子物化结果已做一致性校验，`spark_consistency_status=passed`。

### 5. Day5 研究闭环

- 生成 5d/10d 横截面收益标签。
- 标签包含 prediction time、label start/end、交易可行性、停牌/ST/涨跌停/退市等约束。
- LightGBM baseline 已训练完成。
- walk-forward split 数量为 3。
- 记录 IC、RankIC、ICIR、TopK return、quantile spread、long-short spread、turnover、cost-adjusted return、max drawdown、Sharpe、Calmar、hit rate、capacity 等指标。
- 输出预测、持仓、净值曲线、风险报告、回测 HTML 和 experiment recorder artifact。
- Qlib Python 包已安装，当前 recorder 状态为 `minimal_qlib_recorder_available`。注意：这表示 Qlib 包和最小 recorder 可用，不代表已下载官方 Qlib 股票数据集。

### 6. Day6 实时流 PoC

- `streaming/kafka/topics.yaml` 覆盖 raw、clean、factor、feature、signal、alert 等 Kafka/Redpanda topic。
- 本地 replay producer 生成契约合法 JSONL topic logs，feed mode 明确为 `replay_simulated_not_live_market_data`。
- Flink-style deterministic pipeline 生成实时价格量价、微观结构、新闻情绪、市场环境、relation placeholder 等因子。
- 输出 `realtime_factor_latest.parquet`、`factor_intraday_panel`、`online_feature_snapshot.json`、`flink_job_status.json`、`topic_health.json` 和 realtime-vs-offline diff report。
- `/api/realtime`、`/api/flink-jobs` 与 `/realtime`、`/flink-jobs` 页面展示 PoC 状态和 not formal signal 边界。

### 7. Day7 事件/市场环境因子

- 生成 news/announcement document、event extraction、entity-symbol mapping、DWD event 表。
- 使用诚实标注的 `lexicon_finbert_compatible_baseline` 作为本地金融文本情绪 baseline；未伪装成真实远程 FinBERT/FinGPT 推理。
- 事件因子覆盖 1d/3d/5d 情绪、公告情绪、事件数、负面事件、source weighted sentiment、novelty、authority、decay、policy/macro event score。
- 市场环境因子覆盖 breadth、return、volatility、drawdown、limit up/down、成交额分位、风格轮动、industry dispersion、northbound flow、liquidity regime、risk appetite。
- 严格区分 `ex_ante_regime_feature` 与 `ex_post_regime_label`，并保留 publish/available/prediction time 以避免新闻公告时间泄漏。
- 输出 Day7 增强特征矩阵和 `event_regime_ablation_report`，当前 ablation 状态为 `lightgbm_smoke_trained`。

## Web Research Console

前端位于 `frontend/`，当前包含 21 条业务路由，覆盖：

- `/dashboard`：研究总览与 Day5 dashboard summary
- `/scores`：横截面评分与候选池
- `/backtests`：回测与风险/容量结果
- `/experiments`：实验记录器与 artifact manifest
- `/factors`：Day4 因子库、Feature Store、Day7 事件/市场环境因子
- `/spark-jobs`：Spark 因子物化与一致性校验
- `/data-quality`：Day3 数据质量与防泄漏摘要
- `/lineage`：数据血缘
- `/lakehouse`：Day2 湖仓与 snapshot
- `/settings/licenses`：数据源许可证治理
- `/realtime`：Day6 replay simulated realtime factor PoC
- `/flink-jobs`：Day6 Flink-style job status
- `/rag`、`/graph`、`/models`、`/simulation`、`/reports` 等研究扩展页面

## 快速开始

以下命令适用于 Windows Git Bash / MSYS 环境。

```bash
cd /c/Users/blankxxc/Desktop/work_space/stock_good

# Python 依赖
uv venv --python 3.11 .venv
uv pip install --python ./.venv/Scripts/python.exe -e .

# 前端依赖
cd frontend
npm install
cd ..
```

如果只使用当前本机已有环境，可直接使用项目内 `.venv/Scripts/python.exe` 运行脚本。

## 常用运行命令

### 后端

```bash
cd /c/Users/blankxxc/Desktop/work_space/stock_good
./.venv/Scripts/python.exe -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
```

健康检查：

```bash
curl http://127.0.0.1:8000/health
```

核心 API：

```text
/api/factors
/api/features
/api/spark-jobs
/api/dashboard
/api/scores
/api/backtests
/api/experiments
/api/data-quality
/api/lineage
/api/lakehouse
/api/licenses
/api/realtime
/api/flink-jobs
/api/event-regime
```

### 前端

```bash
cd /c/Users/blankxxc/Desktop/work_space/stock_good/frontend
npm run validate:routes
npm run build
npm run dev
```

默认本地访问地址：

```text
http://127.0.0.1:3000/
```

### Docker Compose

```bash
cd /c/Users/blankxxc/Desktop/work_space/stock_good
docker compose -f deploy/docker/docker-compose.yml up -d --build
docker compose -f deploy/docker/docker-compose.yml ps
```

Compose 栈声明了 postgres、redis、qdrant、redpanda、flink、spark、clickhouse、backend、worker、frontend、prometheus、grafana、backup 等服务。Windows 本地运行时需要 Docker Desktop / WSL2 Linux engine 正常可用。

## 一键验收命令

```bash
cd /c/Users/blankxxc/Desktop/work_space/stock_good

./.venv/Scripts/python.exe scripts/check_day1_acceptance.py
./.venv/Scripts/python.exe scripts/check_day2_acceptance.py
./.venv/Scripts/python.exe scripts/check_day3_acceptance.py
./.venv/Scripts/python.exe scripts/check_day4_acceptance.py
./.venv/Scripts/python.exe scripts/check_day5_acceptance.py
./.venv/Scripts/python.exe scripts/check_day6_acceptance.py
./.venv/Scripts/python.exe scripts/check_day7_acceptance.py
```

完整测试：

```bash
./.venv/Scripts/python.exe -m pytest tests -q
```

前端验证：

```bash
cd frontend
npm run validate:routes
npm run build
```

## Day2 常用命令

```bash
cd /c/Users/blankxxc/Desktop/work_space/stock_good
./.venv/Scripts/python.exe scripts/run_day2_pipeline.py
./.venv/Scripts/python.exe spark/jobs/bronze_to_silver_market_daily.py
./.venv/Scripts/python.exe spark/jobs/bronze_to_silver_reference.py
./.venv/Scripts/python.exe spark/jobs/silver_to_gold_base_panels.py
./.venv/Scripts/python.exe scripts/check_iceberg_acceptance.py
./.venv/Scripts/python.exe spark/jobs/write_iceberg_or_delta_poc.py
./.venv/Scripts/python.exe scripts/load_day2_clickhouse.py
```

## Day3 常用命令

```bash
cd /c/Users/blankxxc/Desktop/work_space/stock_good
./.venv/Scripts/python.exe scripts/run_day3_data_trust.py
./.venv/Scripts/python.exe scripts/check_day3_acceptance.py
```

## Day4 常用命令

```bash
cd /c/Users/blankxxc/Desktop/work_space/stock_good
./.venv/Scripts/python.exe scripts/check_day4_acceptance.py
```

Day4 验收会重新生成/检查因子 store、特征矩阵、Spark consistency artifact、后端 API 和前端页面文案。

## Day5 常用命令

```bash
cd /c/Users/blankxxc/Desktop/work_space/stock_good
./.venv/Scripts/python.exe scripts/check_day5_acceptance.py
```

Day5 验收会重新运行研究闭环并检查标签、模型、预测、持仓、回测、风险报告、实验记录器、API 和前端页面文案。

## Day6 常用命令

```bash
cd /c/Users/blankxxc/Desktop/work_space/stock_good
./.venv/Scripts/python.exe scripts/check_day6_acceptance.py
./.venv/Scripts/python.exe -m pytest tests/test_day6_realtime_streaming.py -q
docker compose -f deploy/docker/docker-compose.yml config --services
```

Day6 验收会重新生成 replay simulated topic logs、实时因子、online feature snapshot、Flink-style job status 和 realtime-vs-offline diff report。该阶段是本地 L1 PoC，不代表接入真实实盘行情。

## Day7 常用命令

```bash
cd /c/Users/blankxxc/Desktop/work_space/stock_good
./.venv/Scripts/python.exe scripts/check_day7_acceptance.py
./.venv/Scripts/python.exe -m pytest tests/test_day7_event_regime.py -q
```

Day7 验收会重新生成新闻/公告事件、事件因子、市场环境因子、增强特征矩阵和 ablation 报告。当前金融文本模型状态是本地 `lexicon_finbert_compatible_baseline_ready`。

## 关键产物

| 产物 | 路径 |
| --- | --- |
| Day4 因子长表 | `data/gold/factor_daily_panel_long` |
| Day4 模型特征矩阵 | `data/gold/model_feature_matrix_wide` |
| Day4 风险暴露 | `data/gold/risk_factor_exposure` |
| Day4 因子报告 | `reports/day4/day4_factor_report.html` |
| Day5 标签 | `data/gold/label_cross_sectional_return` |
| Day5 模型信号 | `data/gold/model_signal_cross_sectional` |
| Day5 回测 Gold 表 | `data/gold/portfolio_backtest_result` |
| Day5 风险 Gold 表 | `data/gold/portfolio_risk_report` |
| Day5 预测 | `reports/day5/predictions.parquet` |
| Day5 持仓 | `reports/day5/holdings.parquet` |
| Day5 净值曲线 | `reports/day5/equity_curve.csv` |
| Day5 风险报告 | `reports/day5/risk_report.parquet` |
| Day5 回测 HTML | `reports/day5/backtest_report.html` |
| Day5 实验记录器 | `reports/day5/experiment_recorder/day5_lightgbm_walk_forward_v001` |
| Day6 Kafka topic logs | `data/realtime/kafka_topics` |
| Day6 实时因子 latest | `reports/day6/realtime_factor_latest.parquet` |
| Day6 intraday factor panel | `data/gold/factor_intraday_panel` |
| Day6 online feature snapshot | `reports/day6/online_feature_snapshot.json` |
| Day6 Flink-style job status | `reports/day6/flink_job_status.json` |
| Day6 realtime/offline diff | `reports/day6/realtime_vs_offline_diff_report.json` |
| Day7 新闻文档 | `data/silver/news_document` |
| Day7 公告文档 | `data/silver/announcement_document` |
| Day7 事件抽取 | `data/silver/event_extraction_result` |
| Day7 事件因子 | `data/gold/factor_news_sentiment_panel` |
| Day7 市场环境因子 | `data/gold/factor_market_regime_panel` |
| Day7 增强特征矩阵 | `data/gold/model_feature_matrix_wide_day7` |
| Day7 ablation 报告 | `reports/day7/event_regime_ablation_report.json` |

## 研究与合规边界

- 系统只生成研究信号，不生成投资建议。
- 所有特征必须满足 point-in-time 约束，不能使用未来信息。
- 历史回测必须考虑停牌、ST、涨跌停、退市、流动性、交易成本、滑点、容量和行业/风格暴露。
- RAG 输出必须有 claim 级引用；没有证据的内容必须标记为假设或证据不足。
- 数据源必须绑定 license_id 和 display/export policy。
- 禁止把单次回测、单一年份、单个随机种子或明星模型结果当成收益承诺。

## 后续建议

1. 接入真实授权数据源，并把 Day2 synthetic pipeline 替换为正式 adapter。
2. 准备官方 Qlib 数据目录，跑完整 Qlib workflow，而不只使用 minimal recorder。
3. 扩展模型路线：XGBoost/CatBoost/LambdaRank、MASTER、StockMixer、HIST、Temporal Relational Stock Ranking。
4. 增强 RAG claim-level evidence、factor card、experiment card 和 failure case 记忆库。
5. 把 Web research console 从静态说明页升级为可筛选、可钻取、可下载的交互式研究工作台。
6. Day8 可继续补 relation graph、行业/概念/供应链/新闻共现/价格相关/lead-lag 邻居溢出因子，并把 Day7 relation placeholder 替换为真实图特征。
