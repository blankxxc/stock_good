from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def project_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def event_regime_payload(research_boundary: str) -> dict[str, Any]:
    root = project_root()
    report = _read_json(root / "reports" / "day7" / "day7_event_regime_report.json")
    ablation = _read_json(root / "reports" / "day7" / "event_regime_ablation_report.json")
    if report.get("status") == "ok":
        return {
            "module": "event-regime",
            "status": "day7_event_regime_ready",
            "maturity": report.get("maturity"),
            "research_boundary": research_boundary,
            "run_id": report.get("run_id"),
            "data_version": report.get("data_version"),
            "event_factor_version": report.get("event_factor_version"),
            "market_regime_version": report.get("market_regime_version"),
            "feature_set_version": report.get("feature_set_version"),
            "text_model_status": report.get("text_model_status"),
            "event_type_model_status": report.get("event_type_model_status"),
            "event_document_rows": report.get("event_document_rows"),
            "announcement_document_rows": report.get("announcement_document_rows"),
            "event_factor_rows": report.get("event_factor_rows"),
            "market_regime_rows": report.get("market_regime_rows"),
            "enhanced_feature_rows": report.get("enhanced_feature_rows"),
            "ablation_status": report.get("ablation_status"),
            "ablation_config_count": report.get("ablation_config_count"),
            "latest_available_time": report.get("latest_available_time"),
            "leakage_check_status": report.get("leakage_check_status"),
            "regime_semantics": report.get("regime_semantics", {}),
            "llm_policy": report.get("llm_policy"),
            "ablation_summary": {
                name: {
                    "rank_ic_smoke": item.get("rank_ic_smoke"),
                    "top5_forward_return_smoke": item.get("top5_forward_return_smoke"),
                    "feature_count": item.get("feature_count"),
                    "model_status": item.get("model_status"),
                }
                for name, item in ablation.get("configs", {}).items()
            },
            "artifacts": report.get("artifacts", {}),
        }
    return {
        "module": "event-regime",
        "status": "day7_event_regime_pending",
        "maturity": "L1-contract-ready",
        "research_boundary": research_boundary,
        "description": "新闻/公告/事件因子、market regime、时间语义和 ablation 状态",
    }
