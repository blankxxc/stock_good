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


def relation_graph_payload(research_boundary: str) -> dict[str, Any]:
    root = project_root()
    report = _read_json(root / "reports" / "day8" / "day8_relation_graph_report.json")
    ablation = _read_json(root / "reports" / "day8" / "relation_factor_ablation_report.json")
    graph_summary = _read_json(root / "reports" / "day8" / "graph_summary.json")
    spark_job = _read_json(root / "reports" / "day8" / "spark_price_corr_edge_job.json")
    if report.get("status") == "ok":
        return {
            "module": "graph",
            "status": "day8_relation_graph_ready",
            "maturity": report.get("maturity"),
            "research_boundary": research_boundary,
            "run_id": report.get("run_id"),
            "data_version": report.get("data_version"),
            "relation_edge_version": report.get("relation_edge_version"),
            "relation_factor_version": report.get("relation_factor_version"),
            "feature_set_version": report.get("feature_set_version"),
            "edge_rows": report.get("edge_rows"),
            "relation_type_count": report.get("relation_type_count"),
            "relation_types": report.get("relation_types", []),
            "relation_factor_rows": report.get("relation_factor_rows"),
            "factor_daily_relation_rows": report.get("factor_daily_relation_rows"),
            "enhanced_feature_rows": report.get("enhanced_feature_rows"),
            "networkx_status": report.get("networkx_status"),
            "spark_price_corr_status": report.get("spark_price_corr_status"),
            "spark_job": spark_job,
            "hist_trsr_adapter_status": report.get("hist_trsr_adapter_status"),
            "adapter_summary": report.get("adapter_summary", {}),
            "ablation_status": report.get("ablation_status"),
            "relation_ablation_gain_status": report.get("relation_ablation_gain_status"),
            "ablation_summary": {
                name: {
                    "rank_ic_smoke": item.get("rank_ic_smoke"),
                    "feature_count": item.get("feature_count"),
                    "model_status": item.get("model_status"),
                    "approval_status": item.get("approval_status"),
                }
                for name, item in ablation.get("configs", {}).items()
            },
            "graph_summary": graph_summary,
            "leakage_check_status": report.get("leakage_check_status"),
            "latest_available_time": report.get("latest_available_time"),
            "artifacts": report.get("artifacts", {}),
        }
    return {
        "module": "graph",
        "status": "day8_relation_graph_pending",
        "maturity": "L1-contract-and-route-stub",
        "research_boundary": research_boundary,
        "description": "股票关系边、NetworkX centrality、传播因子、HIST/TRSR 适配和图谱页",
    }
