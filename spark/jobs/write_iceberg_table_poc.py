from __future__ import annotations

import json
import os
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pyspark.sql import SparkSession

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

ICEBERG_VERSION = os.getenv("ICEBERG_VERSION", "1.11.0")
ICEBERG_PACKAGE = f"org.apache.iceberg:iceberg-spark-runtime-3.5_2.12:{ICEBERG_VERSION}"
CATALOG_NAME = "local"
NAMESPACE = "lakehouse"
TABLE_NAME = "dwd_stock_daily_bar_iceberg"
TABLE_IDENTIFIER = f"{CATALOG_NAME}.{NAMESPACE}.{TABLE_NAME}"
WAREHOUSE = ROOT / "lakehouse" / "iceberg" / "warehouse"
REPORT = ROOT / "reports" / "lakehouse" / "iceberg_table_format_acceptance.json"
LEGACY_MANIFEST = ROOT / "lakehouse" / "delta" / "lakehouse_delta_poc_manifest.json"


def _spark_uri(path: Path) -> str:
    return path.resolve().as_uri()


def _ensure_lakehouse_source() -> Path:
    source = ROOT / "data" / "silver" / "dwd_stock_daily_bar"
    if not any(source.glob("**/*.parquet")):
        from lakehouse.lakehouse_pipeline import run_pipeline

        result = run_pipeline()
        if result.get("status") != "ok":
            raise RuntimeError(f"lakehouse pipeline did not prepare source parquet data: {result}")
    if not any(source.glob("**/*.parquet")):
        raise FileNotFoundError(f"Missing source parquet files under {source}")
    return source


def _build_spark() -> SparkSession:
    return (
        SparkSession.builder.master("local[*]")
        .appName("stock-good-lakehouse-real-iceberg-poc")
        .config("spark.ui.enabled", "false")
        .config("spark.sql.shuffle.partitions", "2")
        .config("spark.jars.packages", ICEBERG_PACKAGE)
        .config(
            "spark.sql.extensions",
            "org.apache.iceberg.spark.extensions.IcebergSparkSessionExtensions",
        )
        .config(
            f"spark.sql.catalog.{CATALOG_NAME}",
            "org.apache.iceberg.spark.SparkCatalog",
        )
        .config(f"spark.sql.catalog.{CATALOG_NAME}.type", "hadoop")
        .config(f"spark.sql.catalog.{CATALOG_NAME}.warehouse", _spark_uri(WAREHOUSE))
        .getOrCreate()
    )


def run_iceberg_poc() -> dict[str, Any]:
    source = _ensure_lakehouse_source()
    table_path = WAREHOUSE / NAMESPACE / TABLE_NAME
    shutil.rmtree(table_path, ignore_errors=True)
    WAREHOUSE.mkdir(parents=True, exist_ok=True)

    spark = _build_spark()
    try:
        source_df = spark.read.parquet(str(source))
        row_count = int(source_df.count())
        if row_count <= 0:
            raise RuntimeError(f"Source parquet table is empty: {source}")

        source_df.createOrReplaceTempView("lakehouse_dwd_stock_daily_bar_source")
        spark.sql(f"CREATE NAMESPACE IF NOT EXISTS {CATALOG_NAME}.{NAMESPACE}")
        spark.sql(f"DROP TABLE IF EXISTS {TABLE_IDENTIFIER}")
        spark.sql(
            f"""
            CREATE TABLE {TABLE_IDENTIFIER}
            USING iceberg
            PARTITIONED BY (trade_date)
            TBLPROPERTIES ('format-version'='2')
            AS
            SELECT
                trade_date,
                symbol,
                open,
                high,
                low,
                close,
                volume,
                amount,
                adj_factor,
                paused,
                limit_up,
                limit_down,
                st_flag,
                event_time,
                publish_time,
                ingest_time,
                available_time,
                source,
                data_version,
                schema_version,
                trace_id,
                adj_close,
                'iceberg_v1_initial_write' AS iceberg_write_note
            FROM lakehouse_dwd_stock_daily_bar_source
            """
        )
        spark.sql(
            f"ALTER TABLE {TABLE_IDENTIFIER} "
            "ADD COLUMN iceberg_schema_evolution_note STRING COMMENT 'Added during real Iceberg acceptance'"
        )

        read_back = spark.table(TABLE_IDENTIFIER)
        read_back_row_count = int(read_back.count())
        schema_evolution_checked = "iceberg_schema_evolution_note" in read_back.columns
        files_count = int(spark.sql(f"SELECT count(*) AS c FROM {TABLE_IDENTIFIER}.files").collect()[0]["c"])
        snapshots_count = int(spark.sql(f"SELECT count(*) AS c FROM {TABLE_IDENTIFIER}.snapshots").collect()[0]["c"])
        metadata_dir = table_path / "metadata"
        metadata_file_count = len(list(metadata_dir.glob("*"))) if metadata_dir.exists() else 0
        report = {
            "status": "ok",
            "table_format": "iceberg",
            "runtime": "pyspark-local",
            "spark_version": spark.version,
            "connector_package": ICEBERG_PACKAGE,
            "connector_install_mode": "spark.jars.packages_maven_resolved",
            "catalog": CATALOG_NAME,
            "catalog_type": "hadoop",
            "namespace": NAMESPACE,
            "table_name": TABLE_NAME,
            "table_identifier": TABLE_IDENTIFIER,
            "warehouse": str(WAREHOUSE),
            "warehouse_uri": _spark_uri(WAREHOUSE),
            "source": str(source),
            "row_count": row_count,
            "read_back_row_count": read_back_row_count,
            "partition_columns": ["trade_date"],
            "format_version": "2",
            "schema_evolution_checked": schema_evolution_checked,
            "files_count": files_count,
            "snapshots_count": snapshots_count,
            "metadata_file_count": metadata_file_count,
            "iceberg_metadata_dir_exists": metadata_dir.exists(),
            "fallback_used": False,
            "research_boundary": "research_signals_only_not_investment_advice",
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }
        required = [
            report["read_back_row_count"] == report["row_count"],
            report["row_count"] > 0,
            report["schema_evolution_checked"] is True,
            report["files_count"] > 0,
            report["snapshots_count"] > 0,
            report["metadata_file_count"] > 0,
            report["iceberg_metadata_dir_exists"] is True,
        ]
        if not all(required):
            raise RuntimeError(f"Iceberg acceptance invariants failed: {report}")
        return report
    finally:
        spark.stop()


def write_reports(report: dict[str, Any]) -> None:
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    # Compatibility for the original lakehouse table-format manifest path.  The content now
    # states the actual successful table format instead of pretending Delta succeeded.
    LEGACY_MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    legacy = {
        **report,
        "legacy_manifest_note": "Original lakehouse manifest path retained; table_format is now real Iceberg.",
        "iceberg_acceptance_report": str(REPORT),
    }
    LEGACY_MANIFEST.write_text(json.dumps(legacy, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> None:
    try:
        report = run_iceberg_poc()
    except Exception as exc:
        report = {
            "status": "failed",
            "table_format": "iceberg",
            "runtime": "pyspark-local",
            "connector_package": ICEBERG_PACKAGE,
            "fallback_used": False,
            "error": repr(exc),
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }
        write_reports(report)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        raise
    write_reports(report)
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
