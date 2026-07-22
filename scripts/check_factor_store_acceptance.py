from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def run_acceptance() -> dict[str, Any]:
    from backend.app.main import app
    from fastapi.testclient import TestClient
    from scripts._authenticated_client import acceptance_admin_client
    from factors.offline.polars_factor_engine import FACTOR_NAMES, materialize_factor_store
    from feature_store.point_in_time_join.build_model_feature_matrix import build_model_feature_matrix
    from spark.jobs.factor_store_factor_materialization import run_job

    factor_report = materialize_factor_store(write_outputs=True)
    pit_report = build_model_feature_matrix()
    spark_report = run_job()
    client = acceptance_admin_client(app)

    failed: list[str] = []

    def check(name: str, condition: bool) -> None:
        if not condition:
            failed.append(name)

    factor_spec_path = ROOT / "configs" / "factor" / "factor_spec.yaml"
    feature_registry_path = ROOT / "feature_store" / "feature_registry.yaml"
    factor_long_dir = ROOT / "data" / "gold" / "factor_daily_panel_long"
    feature_matrix_dir = ROOT / "data" / "gold" / "model_feature_matrix_wide"
    risk_exposure_dir = ROOT / "data" / "gold" / "risk_factor_exposure"
    factor_page = ROOT / "frontend" / "src" / "app" / "factors" / "page.tsx"
    spark_panel_dir = ROOT / "data" / "gold" / "factor_daily_panel_spark_check"
    expected_factor_store_paths = [
        ROOT / "spark" / "jobs" / "materialize_factor_daily.py",
        ROOT / "spark" / "jobs" / "validate_spark_polars_factor_consistency.py",
        ROOT / "lakehouse" / "duckdb" / "factor_store_factor_queries.sql",
    ]

    factor_spec = yaml.safe_load(factor_spec_path.read_text(encoding="utf-8"))
    feature_registry = yaml.safe_load(feature_registry_path.read_text(encoding="utf-8"))
    risk_files = list(risk_exposure_dir.glob("**/*.parquet"))
    risk_df = pd.concat([pd.read_parquet(path) for path in risk_files], ignore_index=True) if risk_files else pd.DataFrame()

    check("factor_report_status_ok", factor_report.get("status") == "ok")
    check("factor_count_at_least_70", factor_report.get("factor_count", 0) >= 70 and len(FACTOR_NAMES) >= 70)
    check("factor_rows_materialized", factor_report.get("factor_rows", 0) > 100_000 and any(factor_long_dir.glob("**/*.parquet")))
    check("factor_spec_complete", factor_spec_path.is_file() and len(factor_spec.get("factors", {})) == factor_report.get("factor_count"))
    check("feature_registry_complete", feature_registry_path.is_file() and len(feature_registry.get("features", [])) == factor_report.get("factor_count"))
    check("point_in_time_join_passed", pit_report.get("status") == "ok" and pit_report.get("point_in_time_violations") == 0)
    check("feature_matrix_written", pit_report.get("output_rows") == factor_report.get("feature_matrix_rows") and any(feature_matrix_dir.glob("**/*.parquet")))
    check("risk_outputs_written", not risk_df.empty and risk_df["risk_factor_name"].nunique() >= 9)
    check("single_factor_reports_written", factor_report.get("single_factor_report_count", 0) >= 10 and (ROOT / "reports" / "factor_store" / "factor_store_factor_report.html").is_file())
    check("spark_consistency_passed", spark_report.get("status") == "ok" and spark_report.get("consistency_status") == "passed" and spark_report.get("failed_factors") == [])
    check("spark_outputs_factor_daily_panel", spark_report.get("factor_daily_panel_row_count", 0) > 10_000 and any(spark_panel_dir.glob("**/*.parquet")))
    check("spark_compares_many_factors", spark_report.get("compared_factor_count", 0) >= 10 and spark_report.get("row_count") == factor_report.get("feature_matrix_rows"))
    check("factor_store_expected_paths_exist", all(path.is_file() for path in expected_factor_store_paths))

    api_factors = client.get("/api/factors")
    api_features = client.get("/api/features")
    api_spark = client.get("/api/spark-jobs")
    check("backend_factors_api_ready", api_factors.status_code == 200 and api_factors.json().get("status") == "factor_store_factor_store_ready")
    check("backend_features_api_ready", api_features.status_code == 200 and api_features.json().get("status") == "factor_store_feature_registry_ready")
    check("backend_spark_api_ready", api_spark.status_code == 200 and api_spark.json().get("status") == "factor_store_spark_factor_materialization_ready")
    page_text = factor_page.read_text(encoding="utf-8")
    check("frontend_factor_page_factor_store_ready", "factor_store" in page_text and "74 个离线因子" in page_text and "/api/factors" in page_text)

    result = {
        "status": "ok" if not failed else "failed",
        "checks": 15,
        "failed": failed,
        "factor_count": factor_report.get("factor_count"),
        "factor_rows": factor_report.get("factor_rows"),
        "feature_matrix_rows": factor_report.get("feature_matrix_rows"),
        "spark_consistency_status": spark_report.get("consistency_status"),
        "point_in_time_violations": pit_report.get("point_in_time_violations"),
    }
    report_path = ROOT / "reports" / "factor_store" / "acceptance_report.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return result


if __name__ == "__main__":
    print(json.dumps(run_acceptance(), ensure_ascii=False, indent=2))
