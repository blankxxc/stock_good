from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

RESEARCH_BOUNDARY = "research_signals_only_not_investment_advice"
DAY8_DIR = ROOT / "reports" / "day8"


def _json_default(value: Any) -> Any:
    try:
        if pd.isna(value):
            return None
    except Exception:
        pass
    return str(value)


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _read_parquet_dir(path: Path) -> pd.DataFrame:
    files = sorted(path.glob("**/*.parquet"))
    if not files:
        return pd.DataFrame()
    return pd.concat([pd.read_parquet(file) for file in files], ignore_index=True, sort=False)


def run_acceptance() -> dict[str, Any]:
    from backend.app.main import app
    from fastapi.testclient import TestClient
    from graph.day8_relation_graph import run_day8_relation_graph_pipeline

    report = run_day8_relation_graph_pipeline(write_outputs=True)
    edges = _read_parquet_dir(ROOT / "data" / "gold" / "stock_relation_edge")
    relation = _read_parquet_dir(ROOT / "data" / "gold" / "factor_relation_panel")
    daily = _read_parquet_dir(ROOT / "data" / "gold" / "factor_daily_panel_day8_relation")
    feature = _read_parquet_dir(ROOT / "data" / "gold" / "model_feature_matrix_wide_day8")
    ablation = _read_json(DAY8_DIR / "relation_factor_ablation_report.json")
    graph_summary = _read_json(DAY8_DIR / "graph_summary.json")
    client = TestClient(app)
    api_graph = client.get("/api/graph")
    api_factors = client.get("/api/factors")
    health = client.get("/health")

    failed: list[str] = []

    def check(name: str, condition: bool) -> None:
        if not condition:
            failed.append(name)

    required_edge_cols = {
        "as_of_date", "src_symbol", "dst_symbol", "relation_type", "relation_weight", "direction",
        "confidence", "start_time", "end_time", "source", "license_id", "data_version", "schema_version",
        "available_time", "prediction_time", "research_boundary",
    }
    required_relation_types = {"industry_same", "concept_same", "index_member_same", "price_corr"}
    required_factor_cols = {
        "neighbor_return_5m", "neighbor_return_1d", "neighbor_volume_shock", "neighbor_sentiment_1h",
        "industry_spillover", "concept_spillover", "supply_chain_spillover", "lead_lag_signal",
        "relation_risk_score", "centrality_score", "community_momentum", "correlation_cluster_momentum",
    }
    adapter_dir = ROOT / "data" / "gold" / "graph_model_adapters" / "hist_trsr"
    adapter_files = [
        "stock_id_mapping.json", "relation_type_mapping.json", "relation_matrix.parquet", "concept_matrix.parquet",
        "stock_feature_tensor.parquet", "label_tensor.parquet",
    ]
    expected_ablation = {"base_day7", "base_plus_relation_graph", "full_minus_relation_graph"}

    check("stock_relation_edge_written", not edges.empty and len(edges) >= 100 and required_edge_cols.issubset(edges.columns))
    check("required_relation_types_ready", required_relation_types.issubset(set(edges.get("relation_type", pd.Series(dtype=str)).astype(str))) and {"lead_lag", "news_co_mention"}.intersection(set(edges.get("relation_type", pd.Series(dtype=str)).astype(str))))
    check("edge_time_semantics_no_leakage", not edges.empty and pd.to_datetime(edges["available_time"], utc=True).le(pd.to_datetime(edges["prediction_time"], utc=True)).all())
    check("edge_weights_bounded_and_no_self_loop", not edges.empty and edges["relation_weight"].between(-1.0, 1.0).all() and not edges["src_symbol"].eq(edges["dst_symbol"]).any())
    check("networkx_centrality_ready", report.get("networkx_status") == "networkx_centrality_ready" and graph_summary.get("nodes", 0) > 0)
    check("spark_price_corr_job_ready", report.get("spark_price_corr_status") in {"spark_price_corr_edges_ready", "spark_compatible_price_corr_edges_ready"})
    check("relation_factor_panel_written", not relation.empty and required_factor_cols.issubset(relation.columns))
    check("relation_factor_time_semantics", not relation.empty and pd.to_datetime(relation["available_time"], utc=True).le(pd.to_datetime(relation["prediction_time"], utc=True)).all())
    check("factor_daily_relation_written", not daily.empty and required_factor_cols.issubset(set(daily.get("factor_name", pd.Series(dtype=str)).astype(str))))
    check("day8_feature_matrix_written", not feature.empty and required_factor_cols.issubset(feature.columns) and feature["feature_set_version"].astype(str).str.contains("day8_relation_graph").all())
    check("hist_trsr_adapter_files_ready", all((adapter_dir / name).is_file() for name in adapter_files) and report.get("hist_trsr_adapter_status") == "hist_trsr_relation_inputs_ready")
    check("relation_ablation_report_written", bool(ablation) and expected_ablation.issubset(set(ablation.get("configs", {}).keys())))
    check("ablation_not_auto_approved", ablation.get("approval_status") == "not_approved_research_candidate_only" and report.get("relation_ablation_gain_status") in {"measured_not_approved", "no_positive_gain_observed_not_approved"})
    check("leakage_check_passed", report.get("leakage_check_status") == "passed" and ablation.get("leakage_check_status") == "passed")
    check("backend_graph_api_ready", api_graph.status_code == 200 and api_graph.json().get("status") == "day8_relation_graph_ready")
    check("backend_factors_api_has_relation_graph", api_factors.status_code == 200 and api_factors.json().get("relation_graph", {}).get("status") == "day8_relation_graph_ready")
    check("frontend_graph_page_day8_ready", "Day 8" in (ROOT / "frontend" / "src" / "app" / "graph" / "page.tsx").read_text(encoding="utf-8") and "/api/graph" in (ROOT / "frontend" / "src" / "app" / "graph" / "page.tsx").read_text(encoding="utf-8") and health.status_code == 200 and health.json().get("modules", {}).get("relation_graph") == "day8_stock_relation_graph_ready")

    result = {
        "status": "ok" if not failed else "failed",
        "checks": 17,
        "failed": failed,
        "edge_rows": report.get("edge_rows"),
        "relation_type_count": report.get("relation_type_count"),
        "relation_factor_rows": report.get("relation_factor_rows"),
        "enhanced_feature_rows": report.get("enhanced_feature_rows"),
        "networkx_status": report.get("networkx_status"),
        "spark_price_corr_status": report.get("spark_price_corr_status"),
        "hist_trsr_adapter_status": report.get("hist_trsr_adapter_status"),
        "relation_ablation_gain_status": report.get("relation_ablation_gain_status"),
        "latest_available_time": report.get("latest_available_time"),
        "artifacts": report.get("artifacts", {}),
    }
    DAY8_DIR.mkdir(parents=True, exist_ok=True)
    (DAY8_DIR / "acceptance_report.json").write_text(json.dumps(result, ensure_ascii=False, indent=2, default=_json_default), encoding="utf-8")
    return result


if __name__ == "__main__":
    print(json.dumps(run_acceptance(), ensure_ascii=False, indent=2, default=_json_default))
