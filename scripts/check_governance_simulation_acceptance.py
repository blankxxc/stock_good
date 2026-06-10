from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from fastapi.testclient import TestClient

from backend.app.main import app
from simulation.governance_simulation_governance import (
    build_governance_simulation_artifacts,
    can_perform_action,
    evaluate_export_gate,
    evaluate_forbidden_wording,
    evaluate_license_policy,
    validate_report_transition,
)

REQUIRED_LICENSE_FIELDS = {
    "source_id", "source_name", "source_type", "provider", "contract_owner", "license_document_path", "permitted_use",
    "raw_storage_allowed", "derived_signal_allowed", "redisplay_allowed", "snippet_allowed", "max_snippet_chars", "export_allowed",
    "external_share_allowed", "attribution_required", "retention_days", "expiry_date", "compliance_status",
}
REQUIRED_EXPORT_FIELDS = {
    "export_id", "report_id", "run_id", "export_type", "exported_by", "exported_at", "recipient_or_purpose", "data_versions",
    "factor_versions", "model_version", "label_version", "rag_sources", "license_check_result", "redaction_rules", "watermark",
    "disclaimer_version", "file_hash", "audit_id",
}


def main() -> None:
    data = build_governance_simulation_artifacts(PROJECT_ROOT)
    failed: list[str] = []
    checks: list[tuple[str, bool]] = []
    client = TestClient(app)
    health = client.get("/health").json()
    endpoints = {
        "/api/simulation": "governance_simulation_paper_simulation_ready",
        "/api/reports": "governance_simulation_report_export_ready",
        "/api/licenses": "lakehouse_license_registry_ready",
        "/api/admin": "governance_simulation_rbac_ready",
        "/api/audit": "governance_simulation_append_only_audit_ready",
    }

    checks.extend([
        ("status_ok", data["status"] == "ok"),
        ("paper_trading_only", data["broker_connection_status"] == "disabled_no_real_broker_integration"),
        ("simulation_account_ready", bool(data["simulation_account"])),
        ("simulation_orders_simulated", bool(data["simulation_order"]) and all(o["simulated"] for o in data["simulation_order"])),
        ("simulation_positions_ready", bool(data["simulation_position"])),
        ("simulation_nav_ready", bool(data["simulation_nav"])),
        ("risk_checks_present", data["simulation_risk"]["status"] in {"passed", "passed_with_warnings"} and len(data["simulation_risk"]["checks"]) >= 9),
        ("risk_limits_effective", data["simulation_risk"]["checks"]["single_stock_weight_limit"]["status"] == "passed" and data["simulation_risk"]["checks"]["industry_weight_limit"]["status"] == "passed"),
        ("roles_present", {"admin", "researcher", "reviewer", "viewer", "compliance", "data_owner"} <= {r["role"] for r in data["rbac_roles"]}),
        ("viewer_restrictions", not can_perform_action("viewer", "view_unpublished_candidate_pool") and not can_perform_action("viewer", "export_full_data") and not can_perform_action("viewer", "run_experiment")),
        ("duties_separation", not validate_report_transition("researcher", "alice", "alice", "review", "approved")["allowed"]),
        ("license_schema", all(REQUIRED_LICENSE_FIELDS <= set(item) for item in data["license_registry"])),
        ("license_gate_blocks_restricted", evaluate_license_policy(next(item for item in data["license_registry"] if item["source_id"] == "vendor_news_restricted"), purpose="external_export")["license_gate"] == "blocked"),
        ("report_state_machine_exported", data["report_state_machine"]["final_status"] == "exported"),
        ("export_manifest_generated", REQUIRED_EXPORT_FIELDS <= set(data["export_manifest"])),
        ("append_only_audit", all(entry["append_only"] for entry in data["audit_log"])),
        ("forbidden_wording_gate", evaluate_forbidden_wording("今日必买，目标价上涨，稳赚")["contains_forbidden_words"] is True),
        ("clean_export_gate_passes", evaluate_export_gate(data_quality_status="passed", leakage_check_status="passed", license_gate="passed", report_status="exportable", contains_forbidden_words=False, rag_citation_check="passed")["allowed"] is True),
        ("health_governance_simulation", health["version"] in {"0.1.0-governance_simulation", "0.1.0-ops_deployment", "0.1.0-final_acceptance"} and health["modules"].get("simulation") == "governance_simulation_paper_simulation_governance_ready"),
    ])
    for path, expected in endpoints.items():
        resp = client.get(path)
        checks.append((f"api_{path}", resp.status_code == 200 and resp.json().get("status") == expected))
    page_paths = [
        PROJECT_ROOT / "frontend" / "src" / "app" / "simulation" / "page.tsx",
        PROJECT_ROOT / "frontend" / "src" / "app" / "reports" / "page.tsx",
        PROJECT_ROOT / "frontend" / "src" / "app" / "settings" / "users" / "page.tsx",
        PROJECT_ROOT / "frontend" / "src" / "app" / "settings" / "licenses" / "page.tsx",
        PROJECT_ROOT / "frontend" / "src" / "app" / "settings" / "audit" / "page.tsx",
    ]
    combined = "\n".join(path.read_text(encoding="utf-8") for path in page_paths)
    checks.append(("frontend_governance_simulation_copy", all(word in combined for word in ["governance_simulation", "simulation_account", "export_manifest", "license_gate", "RBAC", "append_only"])))
    for name, passed in checks:
        if not passed:
            failed.append(name)
    report: dict[str, Any] = {
        "status": "ok" if not failed else "failed",
        "checks": len(checks),
        "failed": failed,
        "simulation_order_count": len(data["simulation_order"]),
        "simulation_position_count": len(data["simulation_position"]),
        "risk_status": data["simulation_risk"]["status"],
        "role_count": len(data["rbac_roles"]),
        "license_source_count": len(data["license_registry"]),
        "export_manifest_status": "generated" if REQUIRED_EXPORT_FIELDS <= set(data["export_manifest"]) else "missing_fields",
        "forbidden_wording_gate": "passed" if evaluate_forbidden_wording("今日必买，目标价上涨，稳赚")["contains_forbidden_words"] else "failed",
        "append_only_audit": all(entry["append_only"] for entry in data["audit_log"]),
        "artifacts": {
            "simulation_governance_report": "reports/governance_simulation/governance_simulation_simulation_governance_report.json",
            "export_manifest": "reports/governance_simulation/export_manifest.json",
            "audit_log": "reports/governance_simulation/audit_log.json",
            "license_gate_report": "reports/governance_simulation/license_gate_report.json",
        },
    }
    out_path = PROJECT_ROOT / "reports" / "governance_simulation" / "acceptance_report.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
