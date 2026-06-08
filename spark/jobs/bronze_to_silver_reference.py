from __future__ import annotations

import json
from pathlib import Path

from pyspark.sql import SparkSession

ROOT = Path(__file__).resolve().parents[2]
REPORT = ROOT / "reports" / "day2" / "spark_bronze_to_silver_reference_report.json"


def main() -> None:
    spark = SparkSession.builder.master("local[*]").appName("stock-good-day2-reference-smoke").getOrCreate()
    try:
        base = ROOT / "data" / "bronze" / "synthetic_day2"
        stock_like = spark.read.parquet(str(base / "ods_market_daily_raw")).select("symbol", "source", "data_version").distinct()
        output = ROOT / "data" / "silver" / "reference" / "stock_master_spark"
        stock_like.write.mode("overwrite").parquet(str(output))
        report = {
            "status": "ok",
            "runtime": "pyspark-local",
            "job_name": "bronze_to_silver_reference",
            "output": str(output),
            "output_format": "parquet",
            "row_count": stock_like.count(),
        }
    finally:
        spark.stop()
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False))


if __name__ == "__main__":
    main()
