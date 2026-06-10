from __future__ import annotations

import json
from pathlib import Path

import yaml
from fastapi.testclient import TestClient

PROJECT_ROOT = Path(__file__).resolve().parents[1]

PRIORITY_SOURCES = {
    "trading_calendar",
    "stock_list",
    "listing_status",
    "st_status",
    "suspension_status",
    "limit_rules",
    "market_daily_ohlcv",
    "adjustment_factor",
    "industry_classification_history",
    "index_constituent_history",
    "concept_classification",
    "financial_statement_basic",
}

ODS_TABLES = {
    "ods_market_daily_raw",
    "ods_market_minute_raw",
    "ods_market_tick_raw",
    "ods_trade_raw",
    "ods_orderbook_raw",
    "ods_financial_statement_raw",
    "ods_announcement_raw",
    "ods_news_raw",
    "ods_macro_raw",
    "ods_fund_flow_raw",
    "ods_northbound_raw",
}

CORE_QUERYABLE_TABLES = {
    "dwd_stock_daily_bar",
    "factor_daily_panel",
    "label_cross_sectional_return",
    "model_training_sample",
    "ads_dashboard_summary",
    "ads_score_latest",
    "ads_backtest_summary",
    "ads_data_quality_summary",
}

SNAPSHOT_FIELDS = {
    "snapshot_id",
    "dataset_name",
    "dataset_layer",
    "partition_start",
    "partition_end",
    "schema_version",
    "source_version",
    "content_hash",
    "row_count",
    "upstream_snapshot_ids",
    "created_at",
    "created_by",
    "is_immutable",
    "data_version",
}


def _read_json(path: str) -> object:
    return json.loads((PROJECT_ROOT / path).read_text(encoding="utf-8"))


def _parquet_glob(table: str) -> str:
    roots = ["bronze", "silver", "gold", "ads"]
    for root in roots:
        base = PROJECT_ROOT / "data" / root / table
        if base.exists():
            return str(base / "**" / "*.parquet")
    raise AssertionError(f"Missing parquet table directory for {table}")


def test_lakehouse_source_registry_tracks_priority_sources_and_license_gates():
    registry_path = PROJECT_ROOT / "configs" / "data" / "source_license_registry.yaml"
    adapter_path = PROJECT_ROOT / "data" / "adapters" / "lakehouse_sources.py"
    assert registry_path.is_file()
    assert adapter_path.is_file()

    registry = yaml.safe_load(registry_path.read_text(encoding="utf-8"))
    sources = {item["dataset_name"]: item for item in registry["sources"]}
    assert PRIORITY_SOURCES.issubset(sources)

    statuses = {item["license_status"] for item in sources.values()}
    assert "authorized" in statuses
    assert {"not_authorized", "restricted", "adapter_pending"}.issubset(statuses)
    assert all(item.get("adapter_status") for item in sources.values())
    assert all(item.get("display_policy") for item in sources.values())


def test_lakehouse_output_layers_and_snapshot_manifest_are_materialized():
    report = _read_json("reports/lakehouse/lakehouse_pipeline_report.json")
    assert report["status"] == "ok"
    assert report["data_version"].startswith("lakehouse_")

    manifest = _read_json("data/snapshots/dataset_snapshot_manifest_lakehouse.json")
    assert isinstance(manifest, list) and manifest
    by_name = {row["dataset_name"]: row for row in manifest}

    required_tables = ODS_TABLES | CORE_QUERYABLE_TABLES
    missing = sorted(required_tables - set(by_name))
    assert missing == []

    for dataset_name in required_tables:
        row = by_name[dataset_name]
        assert SNAPSHOT_FIELDS.issubset(row), dataset_name
        assert row["row_count"] > 0, dataset_name
        assert len(row["content_hash"]) >= 16, dataset_name
        assert row["is_immutable"] is True, dataset_name

    assert by_name["dwd_stock_daily_bar"]["upstream_snapshot_ids"]
    assert by_name["factor_daily_panel"]["upstream_snapshot_ids"]
    assert by_name["model_training_sample"]["upstream_snapshot_ids"]


def test_lakehouse_core_parquet_tables_are_queryable_with_duckdb():
    import duckdb

    con = duckdb.connect(database=":memory:")
    daily_rows = con.execute(
        "select count(*) from read_parquet(?)",
        [_parquet_glob("dwd_stock_daily_bar")],
    ).fetchone()[0]
    assert daily_rows >= 6

    factor_rows = con.execute(
        "select count(*), count(distinct factor_name) from read_parquet(?)",
        [_parquet_glob("factor_daily_panel")],
    ).fetchone()
    assert factor_rows[0] >= 6
    assert factor_rows[1] >= 3

    label_rows = con.execute(
        "select min(label_horizon), count(*) from read_parquet(?)",
        [_parquet_glob("label_cross_sectional_return")],
    ).fetchone()
    assert label_rows[0] == "5d"
    assert label_rows[1] >= 3

    ads_rows = con.execute(
        "select max(total_rows) from read_parquet(?)",
        [_parquet_glob("ads_dashboard_summary")],
    ).fetchone()[0]
    assert ads_rows >= daily_rows


def test_lakehouse_spark_and_lakehouse_poc_artifacts_exist():
    required_jobs = [
        "spark/jobs/bronze_to_silver_market_daily.py",
        "spark/jobs/bronze_to_silver_reference.py",
        "spark/jobs/silver_to_gold_base_panels.py",
        "spark/jobs/write_iceberg_table_poc.py",
        "spark/jobs/write_iceberg_or_delta_poc.py",
        "scripts/check_iceberg_acceptance.py",
    ]
    missing_jobs = [path for path in required_jobs if not (PROJECT_ROOT / path).is_file()]
    assert missing_jobs == []

    spark_report = _read_json("reports/lakehouse/spark_bronze_to_silver_market_daily_report.json")
    assert spark_report["status"] == "ok"
    assert spark_report["runtime"] == "pyspark-local"
    assert spark_report["output_format"] == "parquet"
    assert spark_report["row_count"] >= 6

    lakehouse_report = _read_json("reports/lakehouse/iceberg_table_format_acceptance.json")
    assert lakehouse_report["status"] == "ok"
    assert lakehouse_report["table_format"] == "iceberg"
    assert lakehouse_report["runtime"] == "pyspark-local"
    assert "org.apache.iceberg:iceberg-spark-runtime-3.5_2.12" in lakehouse_report["connector_package"]
    assert lakehouse_report["fallback_used"] is False
    assert lakehouse_report["read_back_row_count"] == lakehouse_report["row_count"]
    assert lakehouse_report["schema_evolution_checked"] is True
    assert lakehouse_report["snapshots_count"] >= 1
    assert lakehouse_report["metadata_file_count"] >= 1


def test_backend_license_api_exposes_lakehouse_source_statuses():
    from backend.app.main import app

    client = TestClient(app)
    response = client.get("/api/licenses")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "lakehouse_license_registry_ready"
    sources = {item["dataset_name"]: item for item in payload["sources"]}
    assert PRIORITY_SOURCES.issubset(sources)
    assert sources["market_daily_ohlcv"]["license_status"] == "authorized"
    assert sources["market_minute_rt"]["license_status"] == "restricted"
    assert sources["northbound_flow"]["license_status"] == "not_authorized"
    assert payload["summary"]["restricted_or_blocked"] >= 1


def test_clickhouse_loader_and_frontend_license_page_are_lakehouse_ready():
    assert (PROJECT_ROOT / "scripts" / "load_lakehouse_clickhouse.py").is_file()
    sql_path = PROJECT_ROOT / "deploy" / "clickhouse" / "lakehouse_ads_tables.sql"
    assert sql_path.is_file()
    sql = sql_path.read_text(encoding="utf-8")
    assert "ads_dashboard_summary" in sql
    assert "ads_score_latest" in sql
    assert "ads_backtest_summary" in sql

    page = (PROJECT_ROOT / "frontend" / "src" / "app" / "settings" / "licenses" / "page.tsx").read_text(encoding="utf-8")
    assert "lakehouse" in page
    assert "not_authorized" in page
    assert "restricted" in page
    assert "adapter_pending" in page
