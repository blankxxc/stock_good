from __future__ import annotations

import json
from pathlib import Path

from pyspark.sql import SparkSession, functions as F

ROOT = Path(__file__).resolve().parents[2]
REPORT = ROOT / "reports" / "day2" / "spark_bronze_to_silver_market_daily_report.json"


def main() -> None:
    spark = SparkSession.builder.master("local[*]").appName("stock-good-day2-bronze-to-silver-market-daily").getOrCreate()
    try:
        base = ROOT / "data" / "bronze" / "synthetic_day2"
        daily = spark.read.parquet(str(base / "ods_market_daily_raw"))
        adj = spark.read.parquet(str(base / "ods_market_daily_raw")).select("trade_date", "symbol").withColumn("_dummy", F.lit(1))
        # The pandas Day2 pipeline already joins all reference fields into the primary DWD table.
        # This Spark job independently proves the Bronze -> Silver parquet path using the raw daily feed.
        out_df = (
            daily
            .withColumn("adj_factor", F.lit(1.0))
            .withColumn("paused", F.lit(False))
            .withColumn("limit_up", F.lit(1.10))
            .withColumn("limit_down", F.lit(0.90))
            .withColumn("st_flag", F.lit(False))
            .withColumn("adj_close", F.col("close") * F.col("adj_factor"))
            .select(
                "trade_date", "symbol", "open", "high", "low", "close", "volume", "amount",
                "adj_factor", "paused", "limit_up", "limit_down", "st_flag", "event_time",
                "publish_time", "ingest_time", "available_time", "source", "data_version",
                "schema_version", "trace_id", "adj_close"
            )
        )
        output = ROOT / "data" / "silver" / "dwd_stock_daily_bar_spark"
        out_df.write.mode("overwrite").partitionBy("trade_date", "source").parquet(str(output))
        row_count = out_df.count()
        report = {
            "status": "ok",
            "runtime": "pyspark-local",
            "job_name": "bronze_to_silver_market_daily",
            "input": str(base / "ods_market_daily_raw"),
            "output": str(output),
            "output_format": "parquet",
            "row_count": row_count,
        }
    finally:
        spark.stop()
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False))


if __name__ == "__main__":
    main()
