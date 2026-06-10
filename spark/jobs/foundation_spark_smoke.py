from __future__ import annotations

import csv
import json
import os
from pathlib import Path

# Native Windows PySpark needs HADOOP_HOME/bin/winutils.exe for local file writes.
# Prefer an explicit environment variable, but fall back to the user-level install
# used by this project setup: C:\Users\blankxxc\hadoop.
def _bootstrap_windows_hadoop_home() -> None:
    default_home = Path.home() / "hadoop"
    winutils = default_home / "bin" / "winutils.exe"
    if not os.environ.get("HADOOP_HOME") and winutils.exists():
        os.environ["HADOOP_HOME"] = str(default_home)
    if winutils.exists():
        os.environ["PATH"] = str(winutils.parent) + os.pathsep + os.environ.get("PATH", "")


_bootstrap_windows_hadoop_home()

ROOT = Path(__file__).resolve().parents[2]
INPUT = ROOT / "data" / "samples" / "market_daily_sample.csv"
OUTPUT_DIR = ROOT / "data" / "bronze" / "spark_smoke_market_daily"
REPORT = ROOT / "reports" / "foundation" / "spark_smoke_report.json"


def write_fallback_placeholder() -> dict:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    rows = list(csv.DictReader(INPUT.open("r", encoding="utf-8")))
    (OUTPUT_DIR / "part-00000.parquet.placeholder.json").write_text(
        json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return {"fallback_runtime": "python-stdlib", "fallback_rows": len(rows), "fallback_output": str(OUTPUT_DIR)}


def run_with_pyspark() -> dict:
    from pyspark.sql import SparkSession  # type: ignore

    spark = SparkSession.builder.master("local[*]").appName("stock-good-foundation-smoke").getOrCreate()
    try:
        df = spark.read.option("header", True).option("inferSchema", True).csv(str(INPUT))
        count = df.count()
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        try:
            df.write.mode("overwrite").parquet(str(OUTPUT_DIR))
            return {
                "status": "ok",
                "runtime": "pyspark-local",
                "read_status": "ok",
                "write_status": "parquet_ok",
                "rows": count,
                "output": str(OUTPUT_DIR),
            }
        except Exception as write_exc:
            message = str(write_exc).splitlines()[0] if str(write_exc) else repr(write_exc)
            result = {
                "status": "partial_pyspark_read_ok_parquet_blocked",
                "runtime": "pyspark-local",
                "read_status": "ok",
                "write_status": "parquet_blocked",
                "rows": count,
                "output": str(OUTPUT_DIR),
                "blocked_reason": (
                    f"PySpark read succeeded, but Parquet write failed: "
                    f"{write_exc.__class__.__name__}: {message}"
                ),
                "next_fix": "Install/configure winutils.exe and HADOOP_HOME on Windows, or run Spark through Docker/WSL/Linux.",
            }
            result.update(write_fallback_placeholder())
            return result
    finally:
        spark.stop()


def run_no_pyspark_fallback(exc: Exception) -> dict:
    result = {
        "status": "fallback_no_pyspark",
        "runtime": "python-stdlib",
        "blocked_reason": f"real PySpark smoke unavailable: {exc.__class__.__name__}: {exc}",
    }
    result.update(write_fallback_placeholder())
    return result


def main() -> None:
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    try:
        result = run_with_pyspark()
    except Exception as exc:
        result = run_no_pyspark_fallback(exc)
    REPORT.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
