from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import yaml
from fastapi.testclient import TestClient

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _read_json(path: str):
    return json.loads((PROJECT_ROOT / path).read_text(encoding="utf-8"))


def _ensure_factor_store_without_spark() -> tuple[dict, dict]:
    from factors.offline.polars_factor_engine import materialize_factor_store
    from feature_store.point_in_time_join.build_model_feature_matrix import build_model_feature_matrix

    factor_report = materialize_factor_store(write_outputs=True)
    pit_report = build_model_feature_matrix()
    return factor_report, pit_report


def test_factor_store_factor_engine_writes_factor_spec_registry_and_gold_artifacts():
    factor_report, _ = _ensure_factor_store_without_spark()
    assert factor_report["status"] == "ok"
    assert factor_report["maturity"] == "L2-offline-factor-store-local-artifacts"
    assert factor_report["engine"] == "polars"
    assert factor_report["factor_count"] >= 70
    assert factor_report["factor_rows"] > 100_000
    assert factor_report["feature_matrix_rows"] == 1960

    factor_spec = yaml.safe_load((PROJECT_ROOT / "configs" / "factor" / "factor_spec.yaml").read_text(encoding="utf-8"))
    registry = yaml.safe_load((PROJECT_ROOT / "feature_store" / "feature_registry.yaml").read_text(encoding="utf-8"))
    assert len(factor_spec["factors"]) == factor_report["factor_count"]
    assert len(registry["features"]) == factor_report["factor_count"]
    for required in ["return_5d", "momentum_20d", "volatility_20d", "amihud_20d", "beta_20d", "industry_neutral_return_20d"]:
        assert required in factor_spec["factors"]
        spec = factor_spec["factors"][required]
        assert spec["economic_hypothesis"]
        assert spec["time_semantics"]["available_time"]
        assert spec["version"] == "factor_v004"

    assert any((PROJECT_ROOT / "data" / "gold" / "factor_daily_panel_long").glob("**/*.parquet"))
    assert any((PROJECT_ROOT / "data" / "gold" / "model_feature_matrix_wide").glob("**/*.parquet"))


def test_factor_store_point_in_time_join_and_risk_model_outputs_are_ready():
    factor_report, pit_report = _ensure_factor_store_without_spark()
    assert pit_report["status"] == "ok"
    assert pit_report["feature_count"] == factor_report["factor_count"]
    assert pit_report["point_in_time_violations"] == 0

    exposure_files = list((PROJECT_ROOT / "data" / "gold" / "risk_factor_exposure").glob("**/*.parquet"))
    covariance_files = list((PROJECT_ROOT / "data" / "gold" / "risk_factor_covariance").glob("**/*.parquet"))
    specific_files = list((PROJECT_ROOT / "data" / "gold" / "specific_risk").glob("**/*.parquet"))
    assert exposure_files and covariance_files and specific_files

    exposures = pd.concat([pd.read_parquet(path) for path in exposure_files], ignore_index=True)
    assert {"trade_date", "symbol", "risk_factor_name", "exposure_value", "version"}.issubset(exposures.columns)
    risk_names = set(exposures["risk_factor_name"].astype(str))
    for required in ["size", "beta", "value", "momentum", "volatility", "liquidity", "quality", "growth", "residual_volatility"]:
        assert required in risk_names
    assert any(name.startswith("industry_exposure::") for name in risk_names)


def test_factor_store_spark_materialization_report_matches_polars_outputs():
    _ensure_factor_store_without_spark()
    report_path = PROJECT_ROOT / "reports" / "factor_store" / "spark_factor_materialization_report.json"
    if not report_path.exists() or _read_json("reports/factor_store/spark_factor_materialization_report.json").get("status") != "ok":
        from spark.jobs.factor_store_factor_materialization import run_job

        spark_report = run_job()
    else:
        spark_report = _read_json("reports/factor_store/spark_factor_materialization_report.json")

    assert spark_report["status"] == "ok"
    assert spark_report["runtime"] == "pyspark-local"
    assert spark_report["consistency_status"] == "passed"
    assert spark_report["row_count"] == 1960
    assert spark_report["joined_row_count"] == 1960
    assert spark_report["compared_factor_count"] >= 10
    assert spark_report["failed_factors"] == []
    assert all(item["compared_rows"] > 0 for item in spark_report["max_abs_diff_by_factor"].values())
    assert all((item["max_abs_diff"] or 0) <= 1e-8 for item in spark_report["max_abs_diff_by_factor"].values())


def test_factor_store_backend_apis_and_frontend_factor_page_are_ready():
    _ensure_factor_store_without_spark()
    from backend.app.main import app

    client = TestClient(app)
    factors = client.get("/api/factors")
    features = client.get("/api/features")
    spark_jobs = client.get("/api/spark-jobs")
    assert factors.status_code == 200
    assert features.status_code == 200
    assert spark_jobs.status_code == 200
    assert factors.json()["status"] == "factor_store_factor_store_ready"
    assert factors.json()["factor_count"] >= 70
    assert features.json()["status"] == "factor_store_feature_registry_ready"
    assert features.json()["point_in_time_violations"] == 0
    assert spark_jobs.json()["status"] == "factor_store_spark_factor_materialization_ready"

    page = (PROJECT_ROOT / "frontend" / "src" / "app" / "factors" / "page.tsx").read_text(encoding="utf-8")
    assert "factor_store" in page
    assert "74 个离线因子" in page
    assert "point_in_time_violations=0" in page
    assert "/api/factors" in page


def test_factor_library_api_and_frontend_have_interactive_catalog_contract():
    from backend.app.main import app

    client = TestClient(app)
    factors = client.get("/api/factors")
    assert factors.status_code == 200
    payload = factors.json()
    assert payload["factor_count"] >= 70
    assert payload["factor_catalog_summary"]["total_factors"] == payload["factor_count"]
    assert payload["factor_catalog_summary"]["point_in_time_violations"] == 0
    assert payload["factor_catalog_summary"]["admission_ready_count"] >= 1
    assert len(payload["category_summary"]) >= 6
    assert {"price_return", "momentum", "volatility", "liquidity"}.issubset({row["category"] for row in payload["category_summary"]})
    assert len(payload["factor_catalog"]) == payload["factor_count"]
    first = payload["factor_catalog"][0]
    required_fields = {
        "factor_name",
        "category",
        "formula",
        "economic_hypothesis",
        "coverage",
        "missing_rate",
        "ic_mean",
        "rank_ic_mean",
        "icir",
        "turnover",
        "capacity_estimate",
        "admission_status",
        "risk_notes",
        "detail_anchor",
    }
    assert required_fields.issubset(first)
    assert {row["admission_status"] for row in payload["factor_catalog"]} & {"research_ready", "needs_review", "proxy_only"}
    assert len(payload["top_factors_by_icir"]) >= 5
    assert payload["factor_ui_hints"]["default_sort"] == "ICIR_desc"

    page = (PROJECT_ROOT / "frontend" / "src" / "app" / "factors" / "page.tsx").read_text(encoding="utf-8")
    component = (PROJECT_ROOT / "frontend" / "src" / "components" / "FactorLibraryDashboard.tsx").read_text(encoding="utf-8")
    factor_ui = page + component
    assert "因子搜索" in factor_ui
    assert "分类筛选" in factor_ui
    assert "准入状态" in factor_ui
    assert "ICIR 排序" in factor_ui
    assert "覆盖率" in factor_ui
    assert "因子详情" in factor_ui
    assert "因子库研究控制台" not in component
    assert "factor-help-panel" not in component
    assert "factor-education-card" not in component
    assert "因子是什么" not in component
    assert "干什么用" not in component
    assert "IC / RankIC 怎么看" not in component
    assert "factor-description" not in component
    assert "factor-usage" not in component
    assert "factor-compatibility-note" not in page
    assert "terminal-strip" not in component
    assert "data-api-path" not in component
    assert "point_in_time_violations=0" not in factor_ui
    assert "market regime publish_time / available_time" not in factor_ui
    assert "long panel" not in component
    assert "wide matrix" not in component


def test_factor_store_acceptance_script_reports_ok():
    from scripts.check_factor_store_acceptance import run_acceptance

    result = run_acceptance()
    assert result["status"] == "ok"
    assert result["checks"] == 15
    assert result["failed"] == []
    assert result["factor_count"] >= 70
    assert result["spark_consistency_status"] == "passed"
    assert result["point_in_time_violations"] == 0
