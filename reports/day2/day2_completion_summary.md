# Day 2 完成摘要

## 结论

Day 2 已完成，并已通过本地验收、前端构建、PySpark local 验证、ClickHouse ADS 装载、Docker Compose 运行态与关键 HTTP/API 烟测。

## 已实现范围

- Source/license registry：`configs/data/source_license_registry.yaml`
  - 21 个数据源状态。
  - `authorized=12`，`restricted=6`，`adapter_pending=2`，`not_authorized=1`，`restricted_or_blocked=9`。
  - 明确 display/export policy，避免把未授权数据当作可展示数据。
- 本地批量数据接入：`scripts/run_day2_pipeline.py`
  - 生成 synthetic Day2 样例数据。
  - 落地 Bronze/ODS、Silver/DWD、Gold/DWS、ADS Parquet。
- ODS raw tables：11 张。
- DWD tables：5 张。
- Gold/DWS + ADS tables：14 张。
- Snapshot manifest：`data/snapshots/dataset_snapshot_manifest_day2.json`
  - 当前 30 个 snapshot。
  - 记录 `snapshot_id`、`dataset_layer`、`data_version`、`schema_version`、`source_version`、`content_hash`、`row_count`、`upstream_snapshot_ids`、`is_immutable`。
- DuckDB 研究查询：`lakehouse/duckdb/day2_research_queries.sql`。
- Spark local jobs：
  - `spark/jobs/bronze_to_silver_market_daily.py`
  - `spark/jobs/bronze_to_silver_reference.py`
  - `spark/jobs/silver_to_gold_base_panels.py`
- Iceberg 表格式 PoC：`spark/jobs/write_iceberg_table_poc.py`
  - 已接入 Spark Iceberg runtime connector：`org.apache.iceberg:iceberg-spark-runtime-3.5_2.12:1.11.0`。
  - `scripts/check_iceberg_acceptance.py` 单独验收真实 Iceberg 表写入、读回、schema evolution、metadata files 与 snapshots。
  - `spark/jobs/write_iceberg_or_delta_poc.py` 保留为兼容入口，实际调用 Iceberg PoC。
- ClickHouse ADS：
  - DDL：`deploy/clickhouse/day2_ads_tables.sql`
  - Loader：`scripts/load_day2_clickhouse.py`
  - 已装载：`ads_dashboard_summary=1`，`ads_score_latest=4`，`ads_backtest_summary=1`。
- Backend API：
  - `/api/licenses` -> `day2_license_registry_ready`
  - `/api/lakehouse` -> `day2_lakehouse_ready`
  - `/api/data-quality` -> `day2_ads_quality_summary_ready`
- Frontend pages：
  - `/dashboard`
  - `/lakehouse`
  - `/settings/licenses`

## 自动验收结果

执行：

```bash
.venv/Scripts/python.exe scripts/check_day2_acceptance.py
```

结果：

```text
status = ok
```

关键子项：

- `scripts/run_day2_pipeline.py`：通过。
- `spark/jobs/bronze_to_silver_market_daily.py`：通过，row_count=12。
- `spark/jobs/bronze_to_silver_reference.py`：通过，row_count=4。
- `spark/jobs/silver_to_gold_base_panels.py`：通过，row_count=12。
- `scripts/check_iceberg_acceptance.py`：通过，真实 Iceberg read-back row_count=12，snapshots=1，metadata_file_count=10。
- `spark/jobs/write_iceberg_or_delta_poc.py`：兼容入口通过，实际调用 Iceberg PoC。
- `pytest tests/test_day1_scaffold.py tests/test_day2_batch_lakehouse.py tests/test_iceberg_table_format.py -q`：15 passed。
- `npm run build`：Next.js production build 成功，23 个静态页面生成。
- `docker compose config --quiet`：通过。
- `scripts/load_day2_clickhouse.py`：通过。
- ClickHouse `SELECT count() FROM ads_dashboard_summary`：返回 1。

完整报告：`reports/day2/acceptance_report.json`。

## Docker Compose 与服务烟测

执行过：

```bash
docker compose -f deploy/docker/docker-compose.yml up -d --build backend worker frontend
docker compose -f deploy/docker/docker-compose.yml up -d --no-build
```

当前 Compose 栈 15 个服务均已启动：

- backend
- worker
- frontend
- postgres
- redis
- qdrant
- redpanda
- clickhouse
- spark-master
- spark-worker
- flink-jobmanager
- flink-taskmanager
- prometheus
- grafana
- backup

HTTP/API 烟测结果：

- Frontend `/`：HTTP 200。
- Frontend `/settings/licenses`：HTTP 200，页面包含 `Day 2`。
- Backend `/health`：HTTP 200。
- Backend `/api/licenses`：HTTP 200，`day2_license_registry_ready`。
- Backend `/api/lakehouse`：HTTP 200，`day2_lakehouse_ready`。
- Spark UI：HTTP 200。
- Flink UI：HTTP 200。
- Prometheus ready：HTTP 200。
- Grafana login：HTTP 200。
- Qdrant：HTTP 200。
- Redpanda ready：HTTP 200。
- Postgres：accepting connections。
- Redis：PONG。
- ClickHouse ADS score count：4。

## 访问地址

- Frontend: http://127.0.0.1:3000/
- Day2 licenses page: http://127.0.0.1:3000/settings/licenses
- Backend health: http://127.0.0.1:8000/health
- Day2 licenses API: http://127.0.0.1:8000/api/licenses
- Day2 lakehouse API: http://127.0.0.1:8000/api/lakehouse
- Spark UI: http://127.0.0.1:8080/
- Flink UI: http://127.0.0.1:8081/
- Prometheus: http://127.0.0.1:9090/
- Grafana: http://127.0.0.1:3001/login

## 边界说明

- Day2 使用 synthetic/local sample 数据，不伪造任何外部供应商授权。
- 受限/未授权源只进入 registry 和 schema/adapter contract，不进入可展示数据。
- Iceberg connector 已通过 `spark.jars.packages` 解析并缓存到本机 Ivy：`org.apache.iceberg:iceberg-spark-runtime-3.5_2.12:1.11.0`；单独验收报告为 `reports/day2/iceberg_table_format_acceptance.json`。
- 当前输出仍是研究平台数据、信号、排序和回测样例，不构成投资建议。
