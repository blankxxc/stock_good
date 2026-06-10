from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from fastapi.testclient import TestClient

PROJECT_ROOT = Path(__file__).resolve().parents[1]

REQUIRED_DOCS = [
    "docs/architecture.md",
    "docs/data_contracts.md",
    "docs/lakehouse_spark.md",
    "docs/realtime_streaming.md",
    "docs/factor_system.md",
    "docs/feature_store.md",
    "docs/modeling.md",
    "docs/backtest.md",
    "docs/risk_attribution.md",
    "docs/rag_evidence.md",
    "docs/security_compliance.md",
    "docs/deployment.md",
    "docs/demo_script.md",
    "docs/final_acceptance_report.md",
    "docs/risk_register.md",
    "docs/adr/ADR-005-final-release-gates.md",
]

REQUIRED_DEMO_ASSETS = [
    "docs/diagrams/system_architecture.mmd",
    "docs/diagrams/data_lineage.mmd",
    "docs/diagrams/spark_lakehouse_etl.mmd",
    "docs/diagrams/realtime_streaming.mmd",
    "docs/demo/model_experiment_comparison.md",
    "docs/demo/backtest_report.md",
    "docs/demo/risk_attribution_report.md",
    "docs/demo/rag_evidence_example.md",
    "docs/demo/relation_graph_example.md",
    "docs/demo/simulation_example.md",
    "docs/demo/rbac_audit_example.md",
    "docs/demo/deployment_runbook.md",
    "docs/demo/coverage_matrix.md",
]

REQUIRED_FINAL_AREAS = [
    "data_ingestion",
    "spark_batch",
    "lakehouse_format",
    "lakehouse_layers",
    "clickhouse_olap",
    "kafka_redpanda",
    "flink_realtime",
    "online_feature_store",
    "offline_factors",
    "realtime_factors",
    "event_factors",
    "market_regime",
    "relation_graph",
    "propagation_factors",
    "labels",
    "leakage_check",
    "baseline_model",
    "advanced_models",
    "backtest",
    "risk_attribution",
    "rag_evidence",
    "website",
    "simulation",
    "rbac",
    "audit",
    "license_gate",
    "report_export",
    "observability",
    "deployment",
    "documentation",
]


def _run_acceptance() -> dict:
    result = subprocess.run(
        [sys.executable, "scripts/check_final_acceptance_acceptance.py"],
        cwd=PROJECT_ROOT,
        text=True,
        capture_output=True,
        timeout=480,
    )
    assert result.returncode == 0, result.stderr + result.stdout
    return json.loads(result.stdout)


def test_final_acceptance_acceptance_script_covers_full_two_week_scope() -> None:
    report = _run_acceptance()
    assert report["status"] == "ok"
    assert report["checks"] >= 34
    assert report["failed"] == []
    assert report["final_status"] == "final_acceptance_final_acceptance_ready"
    assert report["completed_modules"] == 14
    assert report["coverage_area_count"] >= len(REQUIRED_FINAL_AREAS)
    assert report["document_count"] >= len(REQUIRED_DOCS)
    assert report["demo_asset_count"] >= len(REQUIRED_DEMO_ASSETS)
    assert report["release_gate_status"] == "passed"
    assert report["blocked_reason_count"] >= 1

    payload_path = PROJECT_ROOT / "reports" / "final_acceptance" / "final_acceptance_final_acceptance.json"
    assert payload_path.is_file()
    payload = json.loads(payload_path.read_text(encoding="utf-8"))
    area_names = {item["area"] for item in payload["coverage_matrix"]}
    assert set(REQUIRED_FINAL_AREAS).issubset(area_names)
    assert all(item["status"] in {"passed", "partial", "research_candidate_only"} for item in payload["coverage_matrix"])
    assert payload["research_boundary"] == "research_signals_only_not_investment_advice"
    assert payload["release_gates"]["no_broker_integration"] == "passed"
    assert payload["release_gates"]["no_trading_advice_wording"] == "passed"
    assert payload["release_gates"]["manual_review_required_before_real_use"] == "passed"


def test_final_acceptance_docs_demo_assets_and_api_are_ready() -> None:
    report = _run_acceptance()
    missing_docs = [rel for rel in REQUIRED_DOCS if not (PROJECT_ROOT / rel).is_file()]
    missing_assets = [rel for rel in REQUIRED_DEMO_ASSETS if not (PROJECT_ROOT / rel).is_file()]
    assert missing_docs == []
    assert missing_assets == []

    final_report = (PROJECT_ROOT / "docs" / "final_acceptance_report.md").read_text(encoding="utf-8")
    assert "foundation" in final_report and "final_acceptance" in final_report
    assert "完成状态" in final_report
    assert "成熟度" in final_report
    assert "剩余风险" in final_report
    assert "blocked reason" in final_report
    assert "不是 AI 荐股网站" in final_report

    coverage = (PROJECT_ROOT / "docs" / "demo" / "coverage_matrix.md").read_text(encoding="utf-8")
    for required in ["Spark", "Lakehouse", "Flink", "RAG", "风险归因", "导出合规"]:
        assert required in coverage

    risk_register = (PROJECT_ROOT / "docs" / "risk_register.md").read_text(encoding="utf-8")
    for risk in ["Spark", "Flink", "高级模型", "许可证", "实盘"]:
        assert risk in risk_register

    from backend.app.main import app

    client = TestClient(app)
    response = client.get("/api/final-acceptance")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "final_acceptance_final_acceptance_ready"
    assert payload["completed_modules"] == 14
    assert payload["coverage_area_count"] == report["coverage_area_count"]


def test_final_acceptance_readme_and_generated_reports_are_git_hygienic() -> None:
    _run_acceptance()
    readme = (PROJECT_ROOT / "README.md").read_text(encoding="utf-8")
    assert "沪深300近三年日频" in readme
    assert "configs/universe/csi300.yaml" in readme
    assert "/api/final-acceptance" in readme
    assert "## 当前完成度" not in readme
    assert "| foundation |" not in readme

    gitignore = (PROJECT_ROOT / ".gitignore").read_text(encoding="utf-8")
    assert "reports/**/*.json" in gitignore
    assert "reports/**/*.yaml" in gitignore

    tracked_reports = subprocess.run(
        ["git", "ls-files", "reports/final_acceptance"],
        cwd=PROJECT_ROOT,
        text=True,
        capture_output=True,
        timeout=60,
    )
    assert tracked_reports.returncode == 0
    assert tracked_reports.stdout.strip() == ""
