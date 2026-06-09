from __future__ import annotations

from pathlib import Path
from typing import Any

from backend.app.services.day2_catalog import license_payload
from simulation.day12_governance import build_day12_artifacts

PROJECT_ROOT = Path(__file__).resolve().parents[3]


def _payload() -> dict[str, Any]:
    return build_day12_artifacts(PROJECT_ROOT)


def simulation_payload(research_boundary: str) -> dict[str, Any]:
    data = _payload()
    return {
        "module": "simulation",
        "status": "day12_paper_simulation_ready",
        "version": "0.1.0-day12",
        "research_boundary": research_boundary,
        "broker_connection_status": data["broker_connection_status"],
        "simulation_account": data["simulation_account"],
        "simulation_order_count": len(data["simulation_order"]),
        "simulation_position_count": len(data["simulation_position"]),
        "simulation_nav": data["simulation_nav"],
        "simulation_risk": data["simulation_risk"],
        "risk_limits": data["risk_limits"],
        "artifacts": {
            "simulation_report": "reports/day12/day12_simulation_governance_report.json",
            "simulation_account": "data/gold/simulation_account/simulation_account.json",
            "simulation_order": "data/gold/simulation_order/simulation_order.json",
            "simulation_position": "data/gold/simulation_position/simulation_position.json",
            "simulation_nav": "data/gold/simulation_nav/simulation_nav.json",
        },
    }


def reports_payload(research_boundary: str) -> dict[str, Any]:
    data = _payload()
    return {
        "module": "reports",
        "status": "day12_report_export_ready",
        "version": "0.1.0-day12",
        "research_boundary": research_boundary,
        "report_state_machine": data["report_state_machine"],
        "export_gate": data["export_gate"],
        "export_manifest": data["export_manifest"],
        "forbidden_wording_check": data["forbidden_wording_check"],
        "artifacts": {
            "export_manifest": "reports/day12/export_manifest.json",
            "simulation_governance_report": "reports/day12/day12_simulation_governance_report.json",
        },
    }


def licenses_day12_payload(research_boundary: str) -> dict[str, Any]:
    data = _payload()
    payload = license_payload(research_boundary)
    # Preserve the Day2 contract for regression tests and existing UI callers:
    # status/sources/summary remain day2-compatible while Day12 governance fields
    # are added under explicit policy keys.
    payload.update({
        "day12_policy_status": "day12_license_policy_ready",
        "version": "0.1.0-day12",
        "license_registry": data["license_registry"],
        "license_gate_results": data["license_gate_results"],
        "source_count": len(data["license_registry"]),
        "artifacts": {"license_gate_report": "reports/day12/license_gate_report.json"},
    })
    return payload


def admin_payload(research_boundary: str) -> dict[str, Any]:
    data = _payload()
    return {
        "module": "admin",
        "status": "day12_rbac_ready",
        "version": "0.1.0-day12",
        "research_boundary": research_boundary,
        "rbac_roles": data["rbac_roles"],
        "duties_separation": {
            "researcher_cannot_approve_own_report": True,
            "viewer_cannot_view_unpublished_or_export_or_run_experiment": True,
            "append_only_audit_log": True,
        },
    }


def audit_payload(research_boundary: str) -> dict[str, Any]:
    data = _payload()
    return {
        "module": "audit",
        "status": "day12_append_only_audit_ready",
        "version": "0.1.0-day12",
        "research_boundary": research_boundary,
        "audit_log": data["audit_log"],
        "append_only": all(entry.get("append_only") for entry in data["audit_log"]),
        "artifacts": {"audit_log": "reports/day12/audit_log.json"},
    }
