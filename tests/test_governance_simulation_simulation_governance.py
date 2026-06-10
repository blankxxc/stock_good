from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from fastapi.testclient import TestClient

PROJECT_ROOT = Path(__file__).resolve().parents[1]


REQUIRED_LICENSE_FIELDS = {
    "source_id",
    "source_name",
    "source_type",
    "provider",
    "contract_owner",
    "license_document_path",
    "permitted_use",
    "raw_storage_allowed",
    "derived_signal_allowed",
    "redisplay_allowed",
    "snippet_allowed",
    "max_snippet_chars",
    "export_allowed",
    "external_share_allowed",
    "attribution_required",
    "retention_days",
    "expiry_date",
    "compliance_status",
}

REQUIRED_EXPORT_FIELDS = {
    "export_id",
    "report_id",
    "run_id",
    "export_type",
    "exported_by",
    "exported_at",
    "recipient_or_purpose",
    "data_versions",
    "factor_versions",
    "model_version",
    "label_version",
    "rag_sources",
    "license_check_result",
    "redaction_rules",
    "watermark",
    "disclaimer_version",
    "file_hash",
    "audit_id",
}

FORBIDDEN_WORDS = ["推荐买入", "建议卖出", "目标价", "稳赚", "确定上涨", "今日必买", "一键跟投"]


def test_governance_simulation_artifact_builder_creates_paper_simulation_risk_and_export_manifest() -> None:
    from simulation.governance_simulation_governance import build_governance_simulation_artifacts

    result = build_governance_simulation_artifacts(PROJECT_ROOT)

    assert result["status"] == "ok"
    assert result["research_boundary"] == "research_signals_only_not_investment_advice"
    assert result["broker_connection_status"] == "disabled_no_real_broker_integration"

    account = result["simulation_account"]
    orders = result["simulation_order"]
    positions = result["simulation_position"]
    nav = result["simulation_nav"]
    risk = result["simulation_risk"]

    assert account["account_type"] == "paper_trading_research_simulation_only"
    assert orders and all(order["simulated"] is True for order in orders)
    assert positions and nav and risk["status"] in {"passed_with_warnings", "passed"}
    assert result["risk_limits"]["single_stock_weight_max"] <= 0.1
    assert result["risk_limits"]["industry_weight_max"] <= 0.35
    assert risk["checks"]["restricted_security_filter"]["status"] == "passed"
    assert risk["checks"]["turnover_limit"]["status"] == "passed"
    assert "max_drawdown_alert" in risk["checks"]
    assert "tracking_error_alert" in risk["checks"]
    assert "topk_industry_concentration_alert" in risk["checks"]

    manifest = result["export_manifest"]
    assert REQUIRED_EXPORT_FIELDS <= set(manifest)
    assert manifest["license_check_result"] == "passed"
    assert manifest["watermark"] == "RESEARCH_SIMULATION_ONLY_NOT_INVESTMENT_ADVICE"
    assert manifest["file_hash"] and len(manifest["file_hash"]) == 64
    assert result["report_state_machine"]["final_status"] == "exported"

    audit_log = result["audit_log"]
    assert audit_log and all(entry["append_only"] is True for entry in audit_log)
    assert manifest["audit_id"] in {entry["audit_id"] for entry in audit_log}


def test_governance_simulation_rbac_license_and_forbidden_wording_gates_are_enforced() -> None:
    from simulation.governance_simulation_governance import (
        build_governance_simulation_artifacts,
        can_perform_action,
        evaluate_export_gate,
        evaluate_forbidden_wording,
        evaluate_license_policy,
        validate_report_transition,
    )

    result = build_governance_simulation_artifacts(PROJECT_ROOT)
    roles = {role["role"] for role in result["rbac_roles"]}
    assert {"admin", "researcher", "reviewer", "viewer", "compliance", "data_owner"} <= roles

    assert can_perform_action("viewer", "view_unpublished_candidate_pool") is False
    assert can_perform_action("viewer", "export_full_data") is False
    assert can_perform_action("viewer", "run_experiment") is False
    assert can_perform_action("researcher", "submit_report") is True

    same_author = validate_report_transition(
        actor_role="researcher",
        actor_user="alice",
        report_owner="alice",
        from_status="review",
        to_status="approved",
    )
    assert same_author["allowed"] is False
    assert same_author["reason"] == "submitter_cannot_approve_own_report"

    reviewer_approval = validate_report_transition(
        actor_role="reviewer",
        actor_user="bob",
        report_owner="alice",
        from_status="review",
        to_status="approved",
    )
    assert reviewer_approval["allowed"] is True

    licenses = result["license_registry"]
    assert licenses and all(REQUIRED_LICENSE_FIELDS <= set(item) for item in licenses)
    blocked = [item for item in licenses if item["source_id"] == "vendor_news_restricted"]
    assert blocked
    blocked_result = evaluate_license_policy(blocked[0], purpose="external_export")
    assert blocked_result["license_gate"] == "blocked"
    assert "redact_or_drop_source" in blocked_result["redaction_rules"]

    clean_text = "本报告仅展示研究模拟组合、风险约束和引用证据，不构成投资建议。"
    assert evaluate_forbidden_wording(clean_text)["contains_forbidden_words"] is False
    bad_text = "今日必买，目标价上涨，稳赚。"
    wording = evaluate_forbidden_wording(bad_text)
    assert wording["contains_forbidden_words"] is True
    assert set(wording["hits"]) >= {"今日必买", "目标价", "稳赚"}

    failed_export = evaluate_export_gate(
        data_quality_status="passed",
        leakage_check_status="passed",
        license_gate="passed",
        report_status="review",
        contains_forbidden_words=False,
        rag_citation_check="passed",
    )
    assert failed_export["allowed"] is False
    assert "report_status_not_exportable" in failed_export["failed_reasons"]

    forbidden_export = evaluate_export_gate(
        data_quality_status="passed",
        leakage_check_status="passed",
        license_gate="passed",
        report_status="approved",
        contains_forbidden_words=True,
        rag_citation_check="passed",
    )
    assert forbidden_export["allowed"] is False
    assert "forbidden_wording_detected" in forbidden_export["failed_reasons"]

    passed_export = evaluate_export_gate(
        data_quality_status="passed",
        leakage_check_status="passed",
        license_gate="passed",
        report_status="exportable",
        contains_forbidden_words=False,
        rag_citation_check="passed",
    )
    assert passed_export["allowed"] is True


def test_governance_simulation_api_frontend_and_acceptance_script_are_ready() -> None:
    from backend.app.main import app

    client = TestClient(app)
    health = client.get("/health").json()
    assert health["version"] in {"0.1.0-governance_simulation", "0.1.0-ops_deployment", "0.1.0-final_acceptance"}
    assert health["modules"]["simulation"] == "governance_simulation_paper_simulation_governance_ready"
    assert health["modules"]["rbac"] == "governance_simulation_rbac_duties_ready"
    assert health["modules"]["reports"] == "governance_simulation_report_export_manifest_ready"

    endpoints = {
        "/api/simulation": "governance_simulation_paper_simulation_ready",
        "/api/reports": "governance_simulation_report_export_ready",
        "/api/licenses": "lakehouse_license_registry_ready",
        "/api/admin": "governance_simulation_rbac_ready",
        "/api/audit": "governance_simulation_append_only_audit_ready",
    }
    for path, expected_status in endpoints.items():
        response = client.get(path)
        assert response.status_code == 200
        payload = response.json()
        assert payload["status"] == expected_status
        assert payload["research_boundary"] == "research_signals_only_not_investment_advice"

    simulation_page = (PROJECT_ROOT / "frontend" / "src" / "app" / "simulation" / "page.tsx").read_text(encoding="utf-8")
    reports_page = (PROJECT_ROOT / "frontend" / "src" / "app" / "reports" / "page.tsx").read_text(encoding="utf-8")
    users_page = (PROJECT_ROOT / "frontend" / "src" / "app" / "settings" / "users" / "page.tsx").read_text(encoding="utf-8")
    licenses_page = (PROJECT_ROOT / "frontend" / "src" / "app" / "settings" / "licenses" / "page.tsx").read_text(encoding="utf-8")
    audit_page = (PROJECT_ROOT / "frontend" / "src" / "app" / "settings" / "audit" / "page.tsx").read_text(encoding="utf-8")
    combined = "\n".join([simulation_page, reports_page, users_page, licenses_page, audit_page])

    for phrase in [
        "governance_simulation",
        "paper trading",
        "simulation_account",
        "simulation_order",
        "simulation_position",
        "simulation_nav",
        "simulation_risk",
        "RBAC",
        "职责分离",
        "license_gate",
        "export_manifest",
        "append_only",
        "forbidden_wording",
    ]:
        assert phrase in combined
    for word in FORBIDDEN_WORDS:
        assert word not in combined

    acceptance = subprocess.run(
        [sys.executable, "scripts/check_governance_simulation_acceptance.py"],
        cwd=PROJECT_ROOT,
        text=True,
        capture_output=True,
        check=True,
    )
    report = json.loads(acceptance.stdout)
    assert report["status"] == "ok"
    assert report["failed"] == []
    assert report["checks"] >= 18
    assert report["export_manifest_status"] == "generated"
    assert report["forbidden_wording_gate"] == "passed"
