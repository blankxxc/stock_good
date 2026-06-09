from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
from fastapi.testclient import TestClient

PROJECT_ROOT = Path(__file__).resolve().parents[1]
RESEARCH_BOUNDARY = "research_signals_only_not_investment_advice"


def _ensure_day8() -> dict:
    from graph.day8_relation_graph import run_day8_relation_graph_pipeline

    return run_day8_relation_graph_pipeline(write_outputs=True)


def _read_parquet_dir(path: Path) -> pd.DataFrame:
    files = sorted(path.glob("**/*.parquet"))
    assert files, f"no parquet files under {path}"
    return pd.concat([pd.read_parquet(file) for file in files], ignore_index=True, sort=False)


def test_day8_stock_relation_edges_cover_required_relation_types_and_time_semantics():
    report = _ensure_day8()
    assert report["status"] == "ok"
    assert report["relation_type_count"] >= 5
    assert report["edge_rows"] >= 100
    assert report["networkx_status"] == "networkx_centrality_ready"
    assert report["spark_price_corr_status"] in {"spark_price_corr_edges_ready", "spark_compatible_price_corr_edges_ready"}

    edges = _read_parquet_dir(PROJECT_ROOT / "data" / "gold" / "stock_relation_edge")
    required_cols = {
        "as_of_date",
        "src_symbol",
        "dst_symbol",
        "relation_type",
        "relation_weight",
        "direction",
        "confidence",
        "start_time",
        "end_time",
        "source",
        "license_id",
        "data_version",
        "schema_version",
        "available_time",
        "prediction_time",
        "research_boundary",
    }
    assert required_cols.issubset(edges.columns)
    required_types = {"industry_same", "concept_same", "index_member_same", "price_corr"}
    assert required_types.issubset(set(edges["relation_type"].astype(str)))
    assert {"lead_lag", "news_co_mention"}.intersection(set(edges["relation_type"].astype(str)))
    assert not edges.empty
    assert not edges["src_symbol"].eq(edges["dst_symbol"]).any()
    assert edges["relation_weight"].between(-1.0, 1.0).all()
    assert edges["research_boundary"].eq(RESEARCH_BOUNDARY).all()
    assert pd.to_datetime(edges["available_time"], utc=True).le(pd.to_datetime(edges["prediction_time"], utc=True)).all()


def test_day8_relation_factor_panel_and_feature_matrix_are_model_ready():
    report = _ensure_day8()
    assert report["relation_factor_rows"] > 0
    assert report["enhanced_feature_rows"] > 0
    assert report["leakage_check_status"] == "passed"

    relation = _read_parquet_dir(PROJECT_ROOT / "data" / "gold" / "factor_relation_panel")
    feature = _read_parquet_dir(PROJECT_ROOT / "data" / "gold" / "model_feature_matrix_wide_day8")
    daily = _read_parquet_dir(PROJECT_ROOT / "data" / "gold" / "factor_daily_panel_day8_relation")
    required_relation_cols = {
        "neighbor_return_5m",
        "neighbor_return_1d",
        "neighbor_volume_shock",
        "neighbor_sentiment_1h",
        "industry_spillover",
        "concept_spillover",
        "supply_chain_spillover",
        "lead_lag_signal",
        "relation_risk_score",
        "centrality_score",
        "community_momentum",
        "correlation_cluster_momentum",
    }
    assert required_relation_cols.issubset(relation.columns)
    assert required_relation_cols.issubset(feature.columns)
    assert set(required_relation_cols).issubset(set(daily["factor_name"].astype(str)))
    assert pd.to_datetime(relation["available_time"], utc=True).le(pd.to_datetime(relation["prediction_time"], utc=True)).all()
    assert feature["feature_set_version"].astype(str).str.contains("day8_relation_graph").all()


def test_day8_hist_trsr_adapter_artifacts_and_relation_ablation_are_ready():
    report = _ensure_day8()
    assert report["hist_trsr_adapter_status"] == "hist_trsr_relation_inputs_ready"
    assert report["ablation_status"] in {"lightgbm_smoke_trained", "linear_fallback_smoke_trained"}
    assert report["relation_ablation_gain_status"] in {"measured_not_approved", "no_positive_gain_observed_not_approved"}

    adapter_dir = PROJECT_ROOT / "data" / "gold" / "graph_model_adapters" / "hist_trsr"
    required_files = [
        "stock_id_mapping.json",
        "relation_type_mapping.json",
        "relation_matrix.parquet",
        "concept_matrix.parquet",
        "stock_feature_tensor.parquet",
        "label_tensor.parquet",
    ]
    for file_name in required_files:
        assert (adapter_dir / file_name).is_file(), file_name
    relation_matrix = pd.read_parquet(adapter_dir / "relation_matrix.parquet")
    stock_tensor = pd.read_parquet(adapter_dir / "stock_feature_tensor.parquet")
    label_tensor = pd.read_parquet(adapter_dir / "label_tensor.parquet")
    assert {"src_id", "dst_id", "relation_type_id", "weight"}.issubset(relation_matrix.columns)
    assert {"stock_id", "trade_date", "feature_name", "feature_value"}.issubset(stock_tensor.columns)
    assert {"stock_id", "trade_date", "horizon", "label_value"}.issubset(label_tensor.columns)

    ablation = json.loads((PROJECT_ROOT / "reports" / "day8" / "relation_factor_ablation_report.json").read_text(encoding="utf-8"))
    assert ablation["leakage_check_status"] == "passed"
    assert {"base_day7", "base_plus_relation_graph", "full_minus_relation_graph"}.issubset(ablation["configs"].keys())
    assert ablation["approval_status"] == "not_approved_research_candidate_only"


def test_day8_backend_frontend_and_acceptance_are_ready():
    report = _ensure_day8()
    from backend.app.main import app

    client = TestClient(app)
    graph = client.get("/api/graph")
    factors = client.get("/api/factors")
    health = client.get("/health")
    assert graph.status_code == 200
    assert graph.json()["status"] == "day8_relation_graph_ready"
    assert graph.json()["edge_rows"] == report["edge_rows"]
    assert factors.status_code == 200
    assert factors.json()["relation_graph"]["status"] == "day8_relation_graph_ready"
    assert health.status_code == 200
    assert health.json()["modules"]["relation_graph"] == "day8_stock_relation_graph_ready"

    page = (PROJECT_ROOT / "frontend" / "src" / "app" / "graph" / "page.tsx").read_text(encoding="utf-8")
    assert "Day 8" in page
    assert "stock_relation_edge" in page
    assert "factor_relation_panel" in page
    assert "HIST / TRSR" in page
    assert "/api/graph" in page

    from scripts.check_day8_acceptance import run_acceptance

    acceptance = run_acceptance()
    assert acceptance["status"] == "ok"
    assert acceptance["checks"] == 17
    assert acceptance["failed"] == []
