from __future__ import annotations

import json
from pathlib import Path

from pyspark.sql import SparkSession, functions as F

ROOT = Path(__file__).resolve().parents[2]
REPORT = ROOT / "reports" / "lakehouse" / "spark_silver_to_gold_base_panels_report.json"


def main() -> None:
    spark = SparkSession.builder.master("local[*]").appName("stock-good-lakehouse-silver-to-gold-panels").getOrCreate()
    try:
        daily = spark.read.parquet(str(ROOT / "data" / "silver" / "dwd_stock_daily_bar"))
        factor = daily.select(
            "trade_date", "symbol", "available_time", "source", "data_version", "schema_version", "trace_id",
            F.lit("spark_close_return_proxy").alias("factor_name"),
            (F.col("close") / F.col("open") - F.lit(1.0)).alias("factor_value"),
            F.lit("alpha_mvp").alias("factor_set"),
            F.lit("v001").alias("factor_version"),
        )
        output = ROOT / "data" / "gold" / "factor_daily_panel_spark_check"
        factor.write.mode("overwrite").partitionBy("factor_set", "factor_version", "trade_date").parquet(str(output))
        report = {
            "status": "ok",
            "runtime": "pyspark-local",
            "job_name": "silver_to_gold_base_panels",
            "output": str(output),
            "output_format": "parquet",
            "row_count": factor.count(),
        }
    finally:
        spark.stop()
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False))


if __name__ == "__main__":
    main()
