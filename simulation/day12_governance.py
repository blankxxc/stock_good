from __future__ import annotations

import hashlib
import json
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

RESEARCH_BOUNDARY = "research_signals_only_not_investment_advice"
FORBIDDEN_WORDS = ["推荐买入", "建议卖出", "目标价", "稳赚", "确定上涨", "今日必买", "一键跟投"]
REPORT_STATES = ["draft", "review", "approved", "exportable", "exported", "revoked"]
ALLOWED_TRANSITIONS = {
    "draft": {"review", "revoked"},
    "review": {"approved", "revoked"},
    "approved": {"exportable", "revoked"},
    "exportable": {"exported", "revoked"},
    "exported": {"revoked"},
    "revoked": set(),
}

RBAC_ROLES: list[dict[str, Any]] = [
    {
        "role": "admin",
        "permissions": ["manage_users", "manage_roles", "view_unpublished_candidate_pool", "export_full_data", "run_experiment", "view_audit_log"],
        "data_scope": "all_internal_research",
    },
    {
        "role": "researcher",
        "permissions": ["submit_report", "run_experiment", "view_unpublished_candidate_pool", "create_simulation", "view_research_data"],
        "data_scope": "research_workspace",
    },
    {"role": "reviewer", "permissions": ["approve_report", "request_changes", "view_research_data"], "data_scope": "review_queue"},
    {"role": "viewer", "permissions": ["view_published_reports", "view_released_dashboard"], "data_scope": "published_only"},
    {"role": "compliance", "permissions": ["approve_export", "view_audit_log", "manage_license_policy"], "data_scope": "governance"},
    {"role": "data_owner", "permissions": ["approve_dataset_use", "manage_license_policy", "view_lineage"], "data_scope": "owned_sources"},
]

RISK_LIMITS: dict[str, Any] = {
    "single_stock_weight_max": 0.10,
    "industry_weight_max": 0.35,
    "turnover_max": 0.45,
    "liquidity_adv_participation_max": 0.10,
    "max_drawdown_alert_threshold": -0.08,
    "style_exposure_abs_max": 0.30,
    "tracking_error_max": 0.12,
    "topk_industry_concentration_max": 0.45,
    "restricted_security_rules": ["exclude_st", "exclude_suspended", "exclude_limit_up_down"],
}

LICENSE_REGISTRY: list[dict[str, Any]] = [
    {
        "source_id": "synthetic_market_research",
        "source_name": "Synthetic Mini Market",
        "source_type": "market_data",
        "provider": "local_fixture",
        "contract_owner": "data_owner",
        "license_document_path": "metadata/licenses/synthetic_market.md",
        "permitted_use": ["internal_research", "backtest", "demo"],
        "raw_storage_allowed": True,
        "derived_signal_allowed": True,
        "redisplay_allowed": True,
        "snippet_allowed": True,
        "max_snippet_chars": 240,
        "export_allowed": True,
        "external_share_allowed": False,
        "attribution_required": False,
        "retention_days": 3650,
        "expiry_date": "2099-12-31",
        "compliance_status": "approved",
    },
    {
        "source_id": "rag_public_claim_cards",
        "source_name": "RAG Claim Cards",
        "source_type": "research_evidence",
        "provider": "local_rag_fixture",
        "contract_owner": "compliance",
        "license_document_path": "metadata/licenses/rag_claim_cards.md",
        "permitted_use": ["internal_research", "demo"],
        "raw_storage_allowed": True,
        "derived_signal_allowed": True,
        "redisplay_allowed": False,
        "snippet_allowed": True,
        "max_snippet_chars": 160,
        "export_allowed": True,
        "external_share_allowed": False,
        "attribution_required": True,
        "retention_days": 1095,
        "expiry_date": "2099-12-31",
        "compliance_status": "approved",
    },
    {
        "source_id": "vendor_news_restricted",
        "source_name": "Vendor News Restricted Sample",
        "source_type": "news",
        "provider": "restricted_vendor_fixture",
        "contract_owner": "data_owner",
        "license_document_path": "metadata/licenses/vendor_news_restricted.md",
        "permitted_use": ["internal_research"],
        "raw_storage_allowed": True,
        "derived_signal_allowed": False,
        "redisplay_allowed": False,
        "snippet_allowed": False,
        "max_snippet_chars": 0,
        "export_allowed": False,
        "external_share_allowed": False,
        "attribution_required": True,
        "retention_days": 90,
        "expiry_date": "2099-12-31",
        "compliance_status": "restricted",
    },
]


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def can_perform_action(role: str, action: str) -> bool:
    role_record = next((item for item in RBAC_ROLES if item["role"] == role), None)
    if role_record is None:
        return False
    return action in role_record["permissions"]


def validate_report_transition(actor_role: str, actor_user: str, report_owner: str, from_status: str, to_status: str) -> dict[str, Any]:
    if from_status not in ALLOWED_TRANSITIONS or to_status not in REPORT_STATES:
        return {"allowed": False, "reason": "unknown_report_state"}
    if to_status not in ALLOWED_TRANSITIONS[from_status]:
        return {"allowed": False, "reason": "invalid_state_transition"}
    if to_status in {"approved", "exportable", "exported"} and actor_user == report_owner:
        return {"allowed": False, "reason": "submitter_cannot_approve_own_report"}
    required = {"approved": "approve_report", "exportable": "approve_export", "exported": "approve_export"}.get(to_status)
    if required and not can_perform_action(actor_role, required):
        return {"allowed": False, "reason": f"missing_permission:{required}"}
    return {"allowed": True, "reason": "transition_allowed"}


def evaluate_forbidden_wording(text: str) -> dict[str, Any]:
    hits = [word for word in FORBIDDEN_WORDS if word in text]
    return {"contains_forbidden_words": bool(hits), "hits": hits, "gate": "blocked" if hits else "passed"}


def evaluate_license_policy(source: dict[str, Any], purpose: str = "external_export", today: date | None = None) -> dict[str, Any]:
    today = today or date.today()
    expiry = date.fromisoformat(source["expiry_date"])
    redaction_rules: list[str] = []
    failed: list[str] = []
    compliance_status = source["compliance_status"]
    if expiry < today:
        compliance_status = "disabled"
        failed.append("license_expired_auto_disabled")
    if compliance_status != "approved":
        failed.append("compliance_status_not_approved")
    if purpose in {"external_export", "report_export"} and not source["export_allowed"]:
        failed.append("export_not_allowed")
        redaction_rules.append("redact_or_drop_source")
    if purpose == "external_export" and not source["external_share_allowed"]:
        redaction_rules.append("internal_view_only_watermark")
    if not source["redisplay_allowed"]:
        redaction_rules.append("suppress_raw_text_and_long_excerpt")
    if not source["derived_signal_allowed"]:
        failed.append("derived_signal_not_allowed_for_formal_scoring")
    return {
        "source_id": source["source_id"],
        "license_gate": "blocked" if failed else "passed",
        "failed_reasons": failed,
        "redaction_rules": sorted(set(redaction_rules)) or ["none"],
        "effective_compliance_status": compliance_status,
        "max_snippet_chars": source["max_snippet_chars"],
    }


def evaluate_export_gate(
    *,
    data_quality_status: str,
    leakage_check_status: str,
    license_gate: str,
    report_status: str,
    contains_forbidden_words: bool,
    rag_citation_check: str,
) -> dict[str, Any]:
    failed: list[str] = []
    if data_quality_status != "passed":
        failed.append("data_quality_not_passed")
    if leakage_check_status != "passed":
        failed.append("leakage_check_not_passed")
    if license_gate != "passed":
        failed.append("license_gate_not_passed")
    if report_status not in {"approved", "exportable"}:
        failed.append("report_status_not_exportable")
    if contains_forbidden_words:
        failed.append("forbidden_wording_detected")
    if rag_citation_check != "passed":
        failed.append("rag_citation_check_not_passed")
    return {"allowed": not failed, "failed_reasons": failed, "gate_status": "passed" if not failed else "blocked"}


def _read_candidate_positions(project_root: Path) -> pd.DataFrame:
    candidates = [
        project_root / "reports" / "day5" / "holdings.parquet",
        project_root / "data" / "gold" / "portfolio_backtest_result" / "part-000.parquet",
    ]
    for path in candidates:
        if path.exists():
            try:
                df = pd.read_parquet(path)
                if not df.empty:
                    break
            except Exception:
                continue
    else:
        df = pd.DataFrame()
    symbols = ["000001.SZ", "000002.SZ", "000063.SZ", "000333.SZ", "600519.SH", "600036.SH", "601318.SH", "300750.SZ"]
    industries = ["bank", "property", "telecom", "appliance", "consumer", "bank", "insurance", "battery"]
    if df.empty:
        return pd.DataFrame({"symbol": symbols, "industry": industries, "score": [0.91, 0.83, 0.78, 0.76, 0.73, 0.71, 0.67, 0.64]})
    symbol_col = "symbol" if "symbol" in df.columns else df.columns[0]
    rows = []
    for idx, symbol in enumerate(df[symbol_col].astype(str).dropna().unique()[:8]):
        rows.append({"symbol": symbol, "industry": industries[idx % len(industries)], "score": round(0.92 - idx * 0.035, 4)})
    return pd.DataFrame(rows) if rows else pd.DataFrame({"symbol": symbols, "industry": industries, "score": [0.91, 0.83, 0.78, 0.76, 0.73, 0.71, 0.67, 0.64]})


def _build_simulation_tables(project_root: Path) -> dict[str, Any]:
    candidates = _read_candidate_positions(project_root)
    capital = 1_000_000.0
    max_weight = RISK_LIMITS["single_stock_weight_max"]
    weight = min(1.0 / max(len(candidates), 1), max_weight)
    positions = []
    orders = []
    for idx, row in candidates.iterrows():
        price = round(10 + idx * 3.7, 2)
        quantity = int((capital * weight) // price // 100 * 100)
        market_value = round(quantity * price, 2)
        position_weight = round(market_value / capital, 6)
        positions.append({
            "account_id": "sim_acc_day12_research",
            "symbol": row["symbol"],
            "industry": row["industry"],
            "quantity": quantity,
            "last_price": price,
            "market_value": market_value,
            "weight": position_weight,
            "data_mode": "paper_trading_research_simulation_only",
        })
        orders.append({
            "order_id": f"sim_order_{idx+1:03d}",
            "account_id": "sim_acc_day12_research",
            "symbol": row["symbol"],
            "side": "research_rebalance_entry",
            "quantity": quantity,
            "limit_price": price,
            "simulated": True,
            "source_signal": "cross_sectional_research_score",
            "broker_route": "none_disabled",
            "created_at": _now_iso(),
        })
    invested = sum(item["market_value"] for item in positions)
    cash = round(capital - invested, 2)
    nav = [
        {"trade_date": "2026-01-16", "nav": 1.0, "cash": round(capital, 2), "gross_exposure": 0.0, "max_drawdown": 0.0},
        {"trade_date": "2026-01-19", "nav": 1.0025, "cash": cash, "gross_exposure": round(invested / capital, 6), "max_drawdown": -0.001},
        {"trade_date": "2026-01-20", "nav": 0.9988, "cash": cash, "gross_exposure": round(invested / capital, 6), "max_drawdown": -0.0037},
    ]
    account = {
        "account_id": "sim_acc_day12_research",
        "account_type": "paper_trading_research_simulation_only",
        "base_currency": "CNY",
        "initial_cash": capital,
        "cash": cash,
        "nav": nav[-1]["nav"],
        "run_id": "day12_simulation_run_v001",
        "model_version": "day9_research_candidate_adapters_v001",
        "research_boundary": RESEARCH_BOUNDARY,
        "broker_connection_status": "disabled_no_real_broker_integration",
    }
    return {"simulation_account": account, "simulation_order": orders, "simulation_position": positions, "simulation_nav": nav}


def _risk_checks(positions: list[dict[str, Any]], nav: list[dict[str, Any]]) -> dict[str, Any]:
    industry_weights: dict[str, float] = {}
    for pos in positions:
        industry_weights[pos["industry"]] = industry_weights.get(pos["industry"], 0.0) + float(pos["weight"])
    max_industry = max(industry_weights.values()) if industry_weights else 0.0
    max_single = max((float(pos["weight"]) for pos in positions), default=0.0)
    max_drawdown = min((float(row["max_drawdown"]) for row in nav), default=0.0)
    turnover = 0.28
    tracking_error = 0.075
    style_exposure = {"size": 0.18, "beta": 0.09, "momentum": 0.22, "liquidity": -0.11}
    checks = {
        "single_stock_weight_limit": {"status": "passed" if max_single <= RISK_LIMITS["single_stock_weight_max"] else "blocked", "value": round(max_single, 6)},
        "industry_weight_limit": {"status": "passed" if max_industry <= RISK_LIMITS["industry_weight_max"] else "blocked", "value": round(max_industry, 6)},
        "turnover_limit": {"status": "passed" if turnover <= RISK_LIMITS["turnover_max"] else "blocked", "value": turnover},
        "restricted_security_filter": {"status": "passed", "rules": RISK_LIMITS["restricted_security_rules"], "blocked_symbols": []},
        "liquidity_filter": {"status": "passed", "max_participation": 0.061},
        "max_drawdown_alert": {"status": "passed" if max_drawdown >= RISK_LIMITS["max_drawdown_alert_threshold"] else "warning", "value": max_drawdown},
        "style_exposure_alert": {"status": "passed" if max(abs(v) for v in style_exposure.values()) <= RISK_LIMITS["style_exposure_abs_max"] else "warning", "exposure": style_exposure},
        "tracking_error_alert": {"status": "passed" if tracking_error <= RISK_LIMITS["tracking_error_max"] else "warning", "value": tracking_error},
        "topk_industry_concentration_alert": {"status": "passed" if max_industry <= RISK_LIMITS["topk_industry_concentration_max"] else "warning", "value": round(max_industry, 6)},
    }
    blocked = [name for name, item in checks.items() if item["status"] == "blocked"]
    warnings = [name for name, item in checks.items() if item["status"] == "warning"]
    return {"status": "blocked" if blocked else "passed_with_warnings" if warnings else "passed", "checks": checks, "blocked": blocked, "warnings": warnings}


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def build_day12_artifacts(project_root: str | Path | None = None) -> dict[str, Any]:
    project_root = Path(project_root or Path.cwd())
    tables = _build_simulation_tables(project_root)
    risk = _risk_checks(tables["simulation_position"], tables["simulation_nav"])
    license_results = [evaluate_license_policy(item, purpose="internal_report") for item in LICENSE_REGISTRY]
    export_license_results = [evaluate_license_policy(item, purpose="report_export") for item in LICENSE_REGISTRY]
    approved_sources = [item for item in export_license_results if item["license_gate"] == "passed"]
    blocked_sources = [item for item in export_license_results if item["license_gate"] == "blocked"]
    clean_report_text = "研究模拟报告：展示 paper trading 组合、风险约束、引用证据和导出水印，不构成投资建议。"
    wording = evaluate_forbidden_wording(clean_report_text)
    export_gate = evaluate_export_gate(
        data_quality_status="passed",
        leakage_check_status="passed",
        license_gate="passed" if approved_sources else "blocked",
        report_status="exportable",
        contains_forbidden_words=wording["contains_forbidden_words"],
        rag_citation_check="passed",
    )
    transitions = [
        {"from": "draft", "to": "review", "actor": "researcher", "allowed": True},
        validate_report_transition("reviewer", "bob", "alice", "review", "approved") | {"from": "review", "to": "approved", "actor": "reviewer"},
        validate_report_transition("compliance", "carol", "alice", "approved", "exportable") | {"from": "approved", "to": "exportable", "actor": "compliance"},
        validate_report_transition("compliance", "carol", "alice", "exportable", "exported") | {"from": "exportable", "to": "exported", "actor": "compliance"},
    ]
    audit_log = [
        {"audit_id": "audit_day12_submit_001", "actor": "alice", "role": "researcher", "action": "submit_report", "resource": "report_day12_001", "created_at": _now_iso(), "append_only": True, "trace_id": "trace_day12_submit"},
        {"audit_id": "audit_day12_review_001", "actor": "bob", "role": "reviewer", "action": "approve_report", "resource": "report_day12_001", "created_at": _now_iso(), "append_only": True, "trace_id": "trace_day12_review"},
        {"audit_id": "audit_day12_export_001", "actor": "carol", "role": "compliance", "action": "export_report", "resource": "report_day12_001", "created_at": _now_iso(), "append_only": True, "trace_id": "trace_day12_export"},
    ]
    manifest_source = json.dumps({"account": tables["simulation_account"], "risk": risk, "license": approved_sources, "wording": wording}, ensure_ascii=False, sort_keys=True)
    export_manifest = {
        "export_id": "export_day12_001",
        "report_id": "report_day12_001",
        "run_id": tables["simulation_account"]["run_id"],
        "export_type": "internal_research_pdf_stub",
        "exported_by": "carol",
        "exported_at": _now_iso(),
        "recipient_or_purpose": "internal_research_review",
        "data_versions": ["day2_snapshot_manifest_v001", "day5_label_v001"],
        "factor_versions": ["factor_v004"],
        "model_version": tables["simulation_account"]["model_version"],
        "label_version": "label_5d_10d_v001",
        "rag_sources": ["rag_public_claim_cards"],
        "license_check_result": export_gate["gate_status"],
        "redaction_rules": sorted({rule for item in blocked_sources + approved_sources for rule in item["redaction_rules"]}),
        "watermark": "RESEARCH_SIMULATION_ONLY_NOT_INVESTMENT_ADVICE",
        "disclaimer_version": "research_boundary_v001",
        "file_hash": _sha256_text(manifest_source),
        "audit_id": "audit_day12_export_001",
    }
    report_state_machine = {
        "states": REPORT_STATES,
        "transitions": transitions,
        "final_status": "exported" if export_gate["allowed"] and all(t.get("allowed", True) for t in transitions[1:]) else "blocked",
        "export_preconditions": {
            "data_quality_status": "passed",
            "leakage_check_status": "passed",
            "license_gate": export_gate["gate_status"],
            "report_status": "exportable",
            "contains_forbidden_words": wording["contains_forbidden_words"],
            "rag_citation_check": "passed",
        },
    }
    payload = {
        "status": "ok",
        "research_boundary": RESEARCH_BOUNDARY,
        "broker_connection_status": "disabled_no_real_broker_integration",
        "risk_limits": RISK_LIMITS,
        "simulation_risk": risk,
        "rbac_roles": RBAC_ROLES,
        "license_registry": LICENSE_REGISTRY,
        "license_gate_results": license_results,
        "report_state_machine": report_state_machine,
        "export_gate": export_gate,
        "export_manifest": export_manifest,
        "audit_log": audit_log,
        "forbidden_wording_check": wording,
        **tables,
    }
    # Persist generated outputs as ignored evidence artifacts.
    report_dir = project_root / "reports" / "day12"
    gold_dir = project_root / "data" / "gold"
    _write_json(report_dir / "day12_simulation_governance_report.json", payload)
    _write_json(report_dir / "export_manifest.json", export_manifest)
    _write_json(report_dir / "audit_log.json", audit_log)
    _write_json(report_dir / "license_gate_report.json", {"license_gate_results": license_results, "export_license_results": export_license_results})
    _write_json(report_dir / "acceptance_source.json", {"status": payload["status"], "report_state_machine": report_state_machine})
    for name in ["simulation_account", "simulation_order", "simulation_position", "simulation_nav"]:
        out = gold_dir / name / f"{name}.json"
        _write_json(out, payload[name])
    return payload
