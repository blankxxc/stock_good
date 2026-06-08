# stock_good — 智能选股研究平台 Day 1-3 本地工程实现

工作目录：`C:\Users\blankxxc\Desktop\work_space\stock_good`

本项目是“智能选股研究平台”，定位为可追溯数据、可复现实验、可回测模型、可解释 RAG 投研证据和风险解释工作台。它只输出横截面评分、排序、研究候选池、回测报告、风险解释和带引用的研究假设，不输出确定性交易指令。

## Day 1 已落地内容

- 后端：FastAPI `/health` 与 `/api/*` 模块路由占位。
- 前端：Next.js App Router 页面骨架，含 Dashboard、Scores、Candidates、Backtests、Factors、Experiments、RAG、Data Quality、Lineage、Lakehouse、Spark Jobs、Realtime、Flink Jobs、Graph、Models、Simulation、Reports、Settings。
- 数据契约：`data_contracts/*.schema.yaml` 共 17 个，带 source、license_id、data_version、schema_version、trace_id、time_semantic、backfill_allowed。
- 元数据 migration：`warehouse_schema/migrations/0001_day1_metadata.sql` 与 Alembic `backend/app/db/alembic/versions/0001_day1_metadata.py`，覆盖 dataset_snapshot_manifest、schema_registry、spark_job_run、flink_job_run、rag_claim、export_manifest、backfill_request、ADR、risk register 等。
- Spark：`spark/jobs/day1_spark_smoke.py`，优先使用 PySpark local；本项目 `.venv` 已安装 `pyspark==3.5.3`，并已安装 `C:\Users\blankxxc\hadoop\bin\winutils.exe` / `hadoop.dll`。当前 Windows 原生环境已验证 PySpark 可读取 sample CSV 并写出 Parquet。
- Flink：`streaming/flink/day1_flink_job_graph.py`，生成 Flink 5 类实时任务的 job graph 证据。
- Kafka/Redpanda：`streaming/kafka/topics.yaml`，覆盖 raw/clean/factor/feature/signal/alert topic。
- Docker Compose：`deploy/docker/docker-compose.yml`，声明 postgres、redis、qdrant、redpanda、flink、spark、clickhouse、backend、worker、frontend、prometheus、grafana、backup。
- 治理：ADR-001 至 ADR-004、`docs/risk_register.md`、Feature Store registry、许可证与审计边界。

## Day 2 已落地内容

- 数据源与许可证：`configs/data/source_license_registry.yaml`，覆盖 trading_calendar、stock_list、listing/ST/停牌/涨跌停、日频行情、复权因子、行业/指数/概念、基础财务、分钟/tick/盘口/逐笔、公告/新闻/宏观/资金流/北向资金等源；明确 `authorized`、`restricted`、`not_authorized`、`adapter_pending` 和展示/导出策略。
- 本地批量接入：`scripts/run_day2_pipeline.py` 生成可复现 synthetic Day2 样例，落地 Bronze/ODS、Silver/DWD、Gold/DWS、ADS Parquet。
- ODS：`data/bronze/synthetic_day2/*`，包含 11 张 raw 表：market_daily/minute/tick/trade/orderbook、financial_statement、announcement、news、macro、fund_flow、northbound。
- DWD：`data/silver/*`，包含 `dwd_stock_daily_bar`、`dwd_stock_minute_bar`、`dwd_financial_statement`、`dwd_news_event`、`dwd_announcement_event`。
- DWS/Gold：`data/gold/*`，包含日频因子、分钟因子、新闻情绪、市场环境、关系边、标签、训练样本、横截面信号、回测结果。
- ADS：`data/ads/*`，包含 `ads_dashboard_summary`、`ads_score_latest`、`ads_backtest_summary`、`ads_data_quality_summary`。
- 快照版本：`data/snapshots/dataset_snapshot_manifest_day2.json`，当前 30 个 snapshot，记录 row_count、content_hash、data_version、schema_version、source_version、upstream_snapshot_ids 和 immutable 标记。
- DuckDB 研究路径：`lakehouse/duckdb/day2_research_queries.sql` 可直接查询本地 Parquet。
- Spark 本地验证：`spark/jobs/bronze_to_silver_market_daily.py`、`bronze_to_silver_reference.py`、`silver_to_gold_base_panels.py` 均已跑通 PySpark local parquet 输出。
- 湖仓格式 PoC：`spark/jobs/write_iceberg_table_poc.py` 已通过 `org.apache.iceberg:iceberg-spark-runtime-3.5_2.12:1.11.0` 跑通真实 Iceberg Hadoop catalog 表；`scripts/check_iceberg_acceptance.py` 单独验收写入、读回、schema evolution、metadata files 与 snapshots，`write_iceberg_or_delta_poc.py` 保留为兼容入口。
- ClickHouse ADS：`deploy/clickhouse/day2_ads_tables.sql` 与 `scripts/load_day2_clickhouse.py`，已把 ADS 摘要、最新评分、回测摘要装载进正在运行的 ClickHouse 容器。
- 后端 API：`/api/licenses`、`/api/lakehouse`、`/api/data-quality` 返回 Day2 状态、数据版本、许可证计数、snapshot/table 摘要。
- 前端页面：Dashboard、Lakehouse、Settings/Licenses 已升级为 Day2 说明与许可证状态展示。

## Day 3 已落地内容

- 数据可信度框架：`quality/day3_data_trust.py` 与 `scripts/run_day3_data_trust.py`（入口兼容见下方命令）生成 Day3 quality、quarantine、leakage、lineage artifact。
- synthetic mini market：`data/samples/synthetic_mini_market/day3_market_daily.parquet`，20 只股票 × 100 个交易日 = 2000 行，覆盖停牌、ST、涨停、跌停、退市、新上市、公告晚于收盘、未来成分股、未来复权因子、全样本标准化泄漏和 label 泄漏诱捕。
- 数据质量报告：`reports/data_quality_report.json` 与 `reports/data_quality_report.html`，覆盖 schema、主键重复、缺失、价格、OHLC、成交量、交易日缺口、复权因子、行业、指数成分历史、ST/停牌/涨跌停、延迟、重复率、修正率、source license display/export gate。
- quarantine：`data/quarantine/day3_synthetic_market`，异常样本记录 `reason`、`severity`、`source_row`、`detected_at`、`resolved_status`、`owner`、`resolution_note`。
- 防泄漏检查：`reports/day3/leakage_report.json`，验证 `feature.available_time <= prediction_time`、`label_start_time > prediction_time`、公告/新闻/财报发布时间、行业/指数 as_of、scaler fit window、purged split/embargo；故意构造的泄漏样本已被拦截，`leakage_check_status=passed`。
- 轻量血缘：`reports/lineage_report.json` 与 `reports/lineage_report.html`，连接 `source_table -> transform_job -> target_table -> snapshot/report`，并把 Spark job run_id 连接到输出 snapshot_id。
- 后端 API：`/api/data-quality` 升级为 `day3_data_trust_ready`，`/api/lineage` 升级为 `day3_lineage_ready`。
- 前端页面：`/data-quality`、`/lineage` 已升级为 Day3 artifact 展示说明。


## 本地验证命令

```bash
cd /c/Users/blankxxc/Desktop/work_space/stock_good
pytest tests/test_day1_scaffold.py -q
python backend/app/db/run_day1_migration.py
python -m alembic -c alembic.ini upgrade head
# 无 PySpark 时会生成 fallback 证据；使用 .venv 可尝试真实 PySpark local 读取
python spark/jobs/day1_spark_smoke.py
.venv/Scripts/python.exe spark/jobs/day1_spark_smoke.py
python streaming/flink/day1_flink_job_graph.py
cd frontend && npm run validate:routes && npm run build
```

一键验收：

```bash
python scripts/check_day1_acceptance.py
.venv/Scripts/python.exe scripts/check_day2_acceptance.py
.venv/Scripts/python.exe scripts/check_day3_acceptance.py
```


Day 2 常用命令：

```bash
cd /c/Users/blankxxc/Desktop/work_space/stock_good
.venv/Scripts/python.exe scripts/run_day2_pipeline.py
.venv/Scripts/python.exe spark/jobs/bronze_to_silver_market_daily.py
.venv/Scripts/python.exe spark/jobs/bronze_to_silver_reference.py
.venv/Scripts/python.exe spark/jobs/silver_to_gold_base_panels.py
.venv/Scripts/python.exe scripts/check_iceberg_acceptance.py
.venv/Scripts/python.exe spark/jobs/write_iceberg_or_delta_poc.py  # 兼容入口，实际调用 Iceberg PoC
.venv/Scripts/python.exe scripts/load_day2_clickhouse.py
```

Day 3 常用命令：

```bash
cd /c/Users/blankxxc/Desktop/work_space/stock_good
.venv/Scripts/python.exe scripts/run_day3_data_trust.py
.venv/Scripts/python.exe scripts/check_day3_acceptance.py
```

启动后端：

```bash
uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
curl http://127.0.0.1:8000/health
```

Docker Compose（当前已验证 Docker Desktop / WSL2 / Linux engine 可用）：

```bash
cd /c/Users/blankxxc/Desktop/work_space/stock_good
docker compose -f deploy/docker/docker-compose.yml up -d --build
docker compose -f deploy/docker/docker-compose.yml ps
```

当前实测状态：`docker desktop status` 为 `running`，`docker info` 可连接 Linux engine；Compose 栈已成功启动 postgres、redis、qdrant、redpanda、flink、spark、clickhouse、backend、worker、frontend、prometheus、grafana、backup。核心访问地址：前端 `http://127.0.0.1:3000/`，许可证页 `http://127.0.0.1:3000/settings/licenses`，后端健康检查 `http://127.0.0.1:8000/health`，Day2 许可证 API `http://127.0.0.1:8000/api/licenses`，Lakehouse API `http://127.0.0.1:8000/api/lakehouse`，Spark UI `http://127.0.0.1:8080/`，Flink UI `http://127.0.0.1:8081/`，Prometheus `http://127.0.0.1:9090/`，Grafana `http://127.0.0.1:3001/login`。

## 关键边界

- Spark 用于离线批处理、湖仓 ETL、批量因子、标签和训练样本。
- Flink 用于事件时间实时流、watermark、window、late data、实时因子和质量告警。
- 所有正式输出必须绑定 run_id、data_version、factor_version、label_version、model_version、config_hash。
- RAG 必须 claim 级引用；没有 citation 的输出必须标记为证据不足。
- 不接券商实盘，不自动下单，不生成“稳赚/必买/目标价”等话术。
