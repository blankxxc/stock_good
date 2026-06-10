from __future__ import annotations

import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_iceberg_acceptance_report_proves_real_spark_iceberg_table() -> None:
    report_path = PROJECT_ROOT / "reports" / "lakehouse" / "iceberg_table_format_acceptance.json"
    assert report_path.is_file(), "Run scripts/check_iceberg_acceptance.py to generate the Iceberg acceptance report"

    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["status"] == "ok"
    assert report["table_format"] == "iceberg"
    assert report["runtime"] == "pyspark-local"
    assert report["fallback_used"] is False
    assert "org.apache.iceberg:iceberg-spark-runtime-3.5_2.12" in report["connector_package"]
    assert report["catalog"] == "local"
    assert report["table_identifier"] == "local.lakehouse.dwd_stock_daily_bar_iceberg"
    assert report["row_count"] >= 6
    assert report["read_back_row_count"] == report["row_count"]
    assert report["schema_evolution_checked"] is True
    assert report["snapshots_count"] >= 1
    assert report["metadata_file_count"] >= 1
    assert report["iceberg_metadata_dir_exists"] is True
