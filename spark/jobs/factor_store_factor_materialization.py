from __future__ import annotations

import json
from pathlib import Path

from pyspark.sql import SparkSession, Window, functions as F

ROOT = Path(__file__).resolve().parents[2]
REPORT = ROOT / "reports" / "factor_store" / "spark_factor_materialization_report.json"
SOURCE = ROOT / "data" / "samples" / "synthetic_mini_market" / "data_trust_market_daily.parquet"
POLARS_FEATURE_MATRIX = ROOT / "data" / "gold" / "model_feature_matrix_wide"
OUTPUT = ROOT / "data" / "gold" / "model_feature_matrix_spark_check"
SPARK_FACTOR_PANEL_OUTPUT = ROOT / "data" / "gold" / "factor_daily_panel_spark_check"
RESEARCH_BOUNDARY = "research_signals_only_not_investment_advice"
FEATURE_SET_VERSION = "feature_set_factor_store_v001"
FACTOR_VERSION = "factor_v004"

COMPARE_FACTORS = [
    "return_5d",
    "momentum_20d",
    "volatility_20d",
    "ma20_gap",
    "volume_mean_20d",
    "amount_mean_20d",
    "volume_shock_20d",
    "intraday_return",
    "high_low_range",
    "close_position_in_range",
    "turnover_proxy_20d",
    "size_log_amount",
    "vwap_deviation",
]


def _safe_divide(left: F.Column, right: F.Column) -> F.Column:
    return F.when(F.abs(right) > F.lit(1e-12), left / right).otherwise(F.lit(None).cast("double"))


def build_spark_factor_matrix(spark: SparkSession):
    symbol_order = Window.partitionBy("symbol").orderBy("trade_date")
    rolling20 = symbol_order.rowsBetween(-19, 0)

    daily = (
        spark.read.parquet(str(SOURCE))
        .withColumn("trade_date", F.to_date("trade_date"))
        .filter(F.col("close") > 0)
        .filter(F.col("open") > 0)
        .filter(F.col("high") >= F.greatest(F.col("open"), F.col("close")))
        .filter(F.col("low") <= F.least(F.col("open"), F.col("close")))
        .filter(F.col("volume") >= 0)
        .filter(F.col("amount") >= 0)
        .filter(F.coalesce(F.col("eligible_universe"), F.lit(True)))
        .filter(~F.coalesce(F.col("delist_flag"), F.lit(False)))
        .dropDuplicates(["symbol", "trade_date"])
        .withColumn("prev_close", F.lag("close", 1).over(symbol_order))
        .withColumn("lag5_close", F.lag("close", 5).over(symbol_order))
        .withColumn("lag20_close", F.lag("close", 20).over(symbol_order))
        .withColumn("daily_return", _safe_divide(F.col("close"), F.col("prev_close")) - F.lit(1.0))
        .withColumn("return_5d", _safe_divide(F.col("close"), F.col("lag5_close")) - F.lit(1.0))
        .withColumn("momentum_20d", _safe_divide(F.col("close"), F.col("lag20_close")) - F.lit(1.0))
        .withColumn("rolling20_close_count", F.count("close").over(rolling20))
        .withColumn("rolling20_return_count", F.count("daily_return").over(rolling20))
        .withColumn("volume_mean_20d_raw", F.avg("volume").over(rolling20))
        .withColumn("amount_mean_20d_raw", F.avg("amount").over(rolling20))
        .withColumn("ma20_raw", F.avg("close").over(rolling20))
        .withColumn("volatility_20d_raw", F.stddev_samp("daily_return").over(rolling20))
        .withColumn("volume_mean_20d", F.when(F.col("rolling20_close_count") >= 5, F.col("volume_mean_20d_raw")))
        .withColumn("amount_mean_20d", F.when(F.col("rolling20_close_count") >= 5, F.col("amount_mean_20d_raw")))
        .withColumn("ma20", F.when(F.col("rolling20_close_count") >= 5, F.col("ma20_raw")))
        .withColumn("volatility_20d", F.when(F.col("rolling20_return_count") >= 5, F.col("volatility_20d_raw")))
        .withColumn("ma20_gap", _safe_divide(F.col("close"), F.col("ma20")) - F.lit(1.0))
        .withColumn("volume_shock_20d", _safe_divide(F.col("volume"), F.col("volume_mean_20d")) - F.lit(1.0))
        .withColumn("turnover_proxy_20d", _safe_divide(F.col("volume"), F.col("volume_mean_20d")))
        .withColumn("intraday_return", _safe_divide(F.col("close"), F.col("open")) - F.lit(1.0))
        .withColumn("high_low_range", _safe_divide(F.col("high") - F.col("low"), F.col("close")))
        .withColumn("close_position_in_range", _safe_divide(F.col("close") - F.col("low"), F.col("high") - F.col("low")))
        .withColumn("vwap", _safe_divide(F.col("amount"), F.col("volume")))
        .withColumn("vwap_deviation", _safe_divide(F.col("close"), F.col("vwap")) - F.lit(1.0))
        .withColumn("size_log_amount", F.log1p("amount_mean_20d"))
        .withColumn("trade_date", F.date_format("trade_date", "yyyy-MM-dd"))
        .withColumn("feature_set_version", F.lit(FEATURE_SET_VERSION))
        .withColumn("factor_version", F.lit(FACTOR_VERSION))
        .withColumn("research_boundary", F.lit(RESEARCH_BOUNDARY))
    )
    return daily.select(
        "trade_date",
        "symbol",
        "prediction_time",
        "available_time",
        "feature_set_version",
        "factor_version",
        "research_boundary",
        *COMPARE_FACTORS,
    )


def run_job() -> dict[str, object]:
    spark = (
        SparkSession.builder.master("local[*]")
        .appName("stock-good-factor_store-spark-factor-materialization")
        .config("spark.sql.session.timeZone", "UTC")
        .getOrCreate()
    )
    try:
        spark_matrix = build_spark_factor_matrix(spark)
        spark_matrix.write.mode("overwrite").parquet(str(OUTPUT))
        stack_expr = "stack({0}, {1}) as (factor_name, factor_value)".format(
            len(COMPARE_FACTORS),
            ", ".join(f"'{name}', {name}" for name in COMPARE_FACTORS),
        )
        spark_factor_panel = (
            spark_matrix.select(
                "trade_date",
                "symbol",
                "prediction_time",
                "available_time",
                "feature_set_version",
                "factor_version",
                "research_boundary",
                F.expr(stack_expr),
            )
            .where(F.col("factor_value").isNotNull())
        )
        spark_factor_panel.write.mode("overwrite").partitionBy("factor_version", "trade_date").parquet(str(SPARK_FACTOR_PANEL_OUTPUT))

        polars_matrix = spark.read.parquet(str(POLARS_FEATURE_MATRIX)).select(
            "trade_date", "symbol", *[F.col(name).cast("double").alias(f"polars_{name}") for name in COMPARE_FACTORS]
        )
        joined = spark_matrix.alias("spark").join(polars_matrix.alias("polars"), ["trade_date", "symbol"], "inner")
        metrics: dict[str, dict[str, float | int | None]] = {}
        failed_factors: list[str] = []
        for factor_name in COMPARE_FACTORS:
            metric = joined.select(
                F.count(F.when(F.col(factor_name).isNotNull() & F.col(f"polars_{factor_name}").isNotNull(), 1)).alias("compared_rows"),
                F.max(F.abs(F.col(factor_name) - F.col(f"polars_{factor_name}"))).alias("max_abs_diff"),
                F.avg(F.abs(F.col(factor_name) - F.col(f"polars_{factor_name}"))).alias("mean_abs_diff"),
            ).collect()[0].asDict()
            compared_rows = int(metric["compared_rows"] or 0)
            max_abs_diff = metric["max_abs_diff"]
            mean_abs_diff = metric["mean_abs_diff"]
            metrics[factor_name] = {
                "compared_rows": compared_rows,
                "max_abs_diff": None if max_abs_diff is None else float(max_abs_diff),
                "mean_abs_diff": None if mean_abs_diff is None else float(mean_abs_diff),
            }
            if compared_rows <= 0 or (max_abs_diff is not None and float(max_abs_diff) > 1e-8):
                failed_factors.append(factor_name)

        row_count = spark_matrix.count()
        spark_factor_panel_row_count = spark_factor_panel.count()
        joined_row_count = joined.count()
        report = {
            "status": "ok" if not failed_factors and row_count == joined_row_count else "failed",
            "runtime": "pyspark-local",
            "job_name": "factor_store_spark_factor_materialization",
            "feature_set_version": FEATURE_SET_VERSION,
            "factor_version": FACTOR_VERSION,
            "input": str(SOURCE.relative_to(ROOT)),
            "output": str(OUTPUT.relative_to(ROOT)),
            "factor_daily_panel_output": str(SPARK_FACTOR_PANEL_OUTPUT.relative_to(ROOT)),
            "output_format": "parquet",
            "row_count": row_count,
            "factor_daily_panel_row_count": spark_factor_panel_row_count,
            "joined_row_count": joined_row_count,
            "compared_factor_count": len(COMPARE_FACTORS),
            "compare_factors": COMPARE_FACTORS,
            "consistency_status": "passed" if not failed_factors else "failed",
            "failed_factors": failed_factors,
            "max_abs_diff_by_factor": metrics,
            "research_boundary": RESEARCH_BOUNDARY,
        }
    finally:
        spark.stop()
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def main() -> None:
    print(json.dumps(run_job(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
