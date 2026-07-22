from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
from fastapi.testclient import TestClient

from tests.auth_helpers import authenticated_admin_client

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _read_json(path: str) -> object:
    return json.loads((PROJECT_ROOT / path).read_text(encoding="utf-8"))


def test_data_trust_data_trust_pipeline_generates_quality_lineage_leakage_reports():
    from quality.data_trust_data_trust import run_data_trust_data_trust

    report = run_data_trust_data_trust()
    assert report["status"] == "ok"
    assert report["day"] == 3
    assert report["maturity"] == "L2-data-trust-local-artifacts"
    assert report["leakage_check_status"] == "passed"

    required_paths = [
        "reports/data_quality_report.json",
        "reports/data_quality_report.html",
        "reports/lineage_report.json",
        "reports/lineage_report.html",
        "reports/data_trust/data_trust_data_trust_report.json",
        "reports/data_trust/synthetic_mini_market_report.json",
        "reports/data_trust/leakage_report.json",
    ]
    missing = [path for path in required_paths if not (PROJECT_ROOT / path).is_file()]
    assert missing == []

    quality = _read_json("reports/data_quality_report.json")
    assert quality["status"] == "passed"
    assert quality["data_version"] == "data_trust_v001"
    assert quality["thresholds"]["daily_coverage_min"] == 0.99
    assert quality["summary"]["future_time_leakage"] == 0
    assert quality["summary"]["illegal_price_rows_clean"] == 0
    assert quality["summary"]["duplicate_primary_keys_clean"] == 0
    assert quality["summary"]["quarantined_records"] >= 5

    checks = {item["check_name"]: item for item in quality["checks"]}
    required_checks = {
        "schema_match",
        "primary_key_duplicate",
        "missing_required_fields",
        "price_positive",
        "ohlc_relation",
        "volume_abnormal",
        "trading_day_gap",
        "adjustment_factor_present_and_stable",
        "industry_present",
        "index_member_history_present",
        "tradability_flags_present",
        "data_latency",
        "duplicate_rate",
        "correction_rate",
        "source_license_display_export_gate",
    }
    assert required_checks.issubset(checks)
    assert all(checks[name]["status"] == "passed" for name in required_checks)

    html = (PROJECT_ROOT / "reports" / "data_quality_report.html").read_text(encoding="utf-8")
    assert "data_trust" in html
    assert "quarantine" in html
    assert "leakage_check_status" in html


def test_data_trust_quarantine_contains_intentional_synthetic_anomalies_with_required_fields():
    from quality.data_trust_data_trust import run_data_trust_data_trust

    run_data_trust_data_trust()
    quarantine_root = PROJECT_ROOT / "data" / "quarantine" / "data_trust_synthetic_market"
    parquet_files = list(quarantine_root.glob("**/*.parquet"))
    assert parquet_files, "quarantine parquet files should exist"

    df = pd.concat([pd.read_parquet(path) for path in parquet_files], ignore_index=True)
    required_fields = {
        "reason",
        "severity",
        "source_row",
        "detected_at",
        "resolved_status",
        "owner",
        "resolution_note",
    }
    assert required_fields.issubset(df.columns)
    reasons = set(df["reason"].astype(str))
    expected_reasons = {
        "price_non_positive",
        "ohlc_relation_invalid",
        "duplicate_primary_key",
        "future_available_time",
        "full_sample_standardization_leak",
        "label_leakage_trap_feature",
    }
    assert expected_reasons.issubset(reasons)
    assert set(df["resolved_status"].astype(str)) == {"open"}


def test_data_trust_synthetic_mini_market_and_leakage_checker_block_known_traps():
    from quality.data_trust_data_trust import run_data_trust_data_trust

    run_data_trust_data_trust()
    synthetic = _read_json("reports/data_trust/synthetic_mini_market_report.json")
    assert synthetic["status"] == "passed"
    assert synthetic["stock_count"] == 20
    assert synthetic["trading_day_count"] == 100
    assert synthetic["row_count"] == 2000
    assert synthetic["scenario_flags"]["paused_rows"] > 0
    assert synthetic["scenario_flags"]["st_rows"] > 0
    assert synthetic["scenario_flags"]["limit_up_rows"] > 0
    assert synthetic["scenario_flags"]["limit_down_rows"] > 0
    assert synthetic["scenario_flags"]["delisted_rows"] > 0
    assert all(status == "passed" for status in synthetic["synthetic_tests"].values())

    leakage = _read_json("reports/data_trust/leakage_report.json")
    assert leakage["status"] == "passed"
    assert leakage["clean_dataset_status"] == "passed"
    assert leakage["intentional_trap_status"] == "blocked"
    assert leakage["trap_violation_count"] >= 5
    rules = {item["rule"]: item for item in leakage["rules"]}
    required_rules = {
        "feature.available_time <= prediction_time",
        "label_start_time > prediction_time",
        "announcement.publish_time <= prediction_time",
        "news.publish_time <= prediction_time",
        "financial_statement.announce_time <= prediction_time",
        "industry.as_of_date <= prediction_time",
        "index_member.as_of_date <= prediction_time",
        "scaler.fit_window <= train_window",
        "purged_split_with_embargo",
    }
    assert required_rules.issubset(rules)
    assert all(rules[rule]["clean_status"] == "passed" for rule in required_rules)


def test_data_trust_lineage_connects_sources_jobs_snapshots_and_quality_reports():
    from quality.data_trust_data_trust import run_data_trust_data_trust

    run_data_trust_data_trust()
    lineage = _read_json("reports/lineage_report.json")
    assert lineage["status"] == "passed"
    assert lineage["data_version"] == "data_trust_v001"
    assert lineage["node_count"] >= 30
    assert lineage["edge_count"] >= 30

    edges = lineage["edges"]
    assert any(edge["source_type"] == "source_table" and edge["target_type"] == "transform_job" for edge in edges)
    assert any(edge["source_type"] == "transform_job" and edge["target_type"] == "target_table" for edge in edges)
    assert any(edge["source_type"] == "spark_job_run" and edge["target_type"] == "snapshot" for edge in edges)
    assert any(edge["target_id"] == "reports/data_quality_report.json" for edge in edges)
    assert any(edge["target_id"] == "reports/data_trust/leakage_report.json" for edge in edges)


def test_backend_data_trust_data_quality_and_lineage_apis_are_ready():
    from backend.app.main import app

    from quality.data_trust_data_trust import run_data_trust_data_trust

    run_data_trust_data_trust()
    client = authenticated_admin_client(app)

    dq_response = client.get("/api/data-quality")
    assert dq_response.status_code == 200
    dq = dq_response.json()
    assert dq["status"] == "data_trust_data_trust_ready"
    assert dq["maturity"] == "L2-data-trust-quality-lineage-leakage"
    assert dq["leakage_check_status"] == "passed"
    assert dq["quarantine"]["record_count"] >= 5
    assert dq["reports"]["html"].endswith("reports/data_quality_report.html")

    lineage_response = client.get("/api/lineage")
    assert lineage_response.status_code == 200
    lineage = lineage_response.json()
    assert lineage["status"] == "data_trust_lineage_ready"
    assert lineage["edge_count"] >= 30
    assert lineage["reports"]["json"].endswith("reports/lineage_report.json")


def test_data_trust_frontend_pages_explain_real_quality_lineage_artifacts():
    dq_page = (PROJECT_ROOT / "frontend" / "src" / "app" / "data-quality" / "page.tsx").read_text(encoding="utf-8")
    lineage_page = (PROJECT_ROOT / "frontend" / "src" / "app" / "lineage" / "page.tsx").read_text(encoding="utf-8")
    assert "data_trust" in dq_page
    assert "reports/data_quality_report.json" in dq_page
    assert "quarantine" in dq_page
    assert "leakage_check_status" in dq_page
    assert "data_trust" in lineage_page
    assert "reports/lineage_report.json" in lineage_page
    assert "source_table" in lineage_page
    assert "Spark job run_id" in lineage_page


def test_data_trust_acceptance_script_reports_ok():
    from scripts.check_data_trust_acceptance import run_acceptance

    result = run_acceptance()
    assert result["status"] == "ok"
    assert result["checks"] >= 7
    assert result["failed"] == []
