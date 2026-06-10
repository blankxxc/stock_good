from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="session", autouse=True)
def prepare_clean_checkout_artifacts() -> None:
    """Materialize deterministic local artifacts that are intentionally git-ignored.

    The repository keeps generated lakehouse/data/report outputs out of git. A fresh
    GitHub Actions checkout therefore needs a small bootstrap before tests that read
    those artifacts directly.
    """
    if str(PROJECT_ROOT) not in sys.path:
        sys.path.insert(0, str(PROJECT_ROOT))

    for rel in ["lakehouse/iceberg", "lakehouse/hudi", "lakehouse/delta", "configs/env"]:
        (PROJECT_ROOT / rel).mkdir(parents=True, exist_ok=True)

    lakehouse_report = PROJECT_ROOT / "reports" / "lakehouse" / "lakehouse_pipeline_report.json"
    market_daily = PROJECT_ROOT / "data" / "bronze" / "synthetic_lakehouse" / "ods_market_daily_raw"
    if not lakehouse_report.is_file() or not list(market_daily.glob("**/*.parquet")):
        from lakehouse.lakehouse_pipeline import run_pipeline

        run_pipeline()

    spark_report = PROJECT_ROOT / "reports" / "lakehouse" / "spark_bronze_to_silver_market_daily_report.json"
    if not spark_report.is_file():
        subprocess.run(
            [sys.executable, "spark/jobs/bronze_to_silver_market_daily.py"],
            cwd=PROJECT_ROOT,
            check=True,
            timeout=600,
        )

    iceberg_report = PROJECT_ROOT / "reports" / "lakehouse" / "iceberg_table_format_acceptance.json"
    if not iceberg_report.is_file():
        subprocess.run(
            [sys.executable, "scripts/check_iceberg_acceptance.py"],
            cwd=PROJECT_ROOT,
            check=True,
            timeout=900,
        )

    factor_long_dir = PROJECT_ROOT / "data" / "gold" / "factor_daily_panel_long"
    if not list(factor_long_dir.glob("**/*.parquet")):
        from factors.offline.polars_factor_engine import materialize_factor_store

        materialize_factor_store(write_outputs=True)
