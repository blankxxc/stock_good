from __future__ import annotations

import json
import math
from pathlib import Path

import pandas as pd
from fastapi.testclient import TestClient

PROJECT_ROOT = Path(__file__).resolve().parents[1]
RESEARCH_BOUNDARY = "research_signals_only_not_investment_advice"


def _ensure_relation_graph() -> dict:
    from graph.relation_graph_relation_graph import run_relation_graph_relation_graph_pipeline

    return run_relation_graph_relation_graph_pipeline(write_outputs=True)


def _read_parquet_dir(path: Path) -> pd.DataFrame:
    files = sorted(path.glob("**/*.parquet"))
    assert files, f"no parquet files under {path}"
    return pd.concat([pd.read_parquet(file) for file in files], ignore_index=True, sort=False)


def test_relation_graph_stock_relation_edges_cover_required_relation_types_and_time_semantics():
    report = _ensure_relation_graph()
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


def test_relation_graph_relation_factor_panel_and_feature_matrix_are_model_ready():
    report = _ensure_relation_graph()
    assert report["relation_factor_rows"] > 0
    assert report["enhanced_feature_rows"] > 0
    assert report["leakage_check_status"] == "passed"

    relation = _read_parquet_dir(PROJECT_ROOT / "data" / "gold" / "factor_relation_panel")
    feature = _read_parquet_dir(PROJECT_ROOT / "data" / "gold" / "model_feature_matrix_wide_relation_graph")
    daily = _read_parquet_dir(PROJECT_ROOT / "data" / "gold" / "factor_daily_panel_relation_graph_relation")
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
    assert feature["feature_set_version"].astype(str).str.contains("relation_graph_relation_graph").all()


def test_relation_graph_hist_trsr_adapter_artifacts_and_relation_ablation_are_ready():
    report = _ensure_relation_graph()
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

    ablation = json.loads((PROJECT_ROOT / "reports" / "relation_graph" / "relation_factor_ablation_report.json").read_text(encoding="utf-8"))
    assert ablation["leakage_check_status"] == "passed"
    assert {"base_event_regime", "base_plus_relation_graph", "full_minus_relation_graph"}.issubset(ablation["configs"].keys())
    assert ablation["approval_status"] == "not_approved_research_candidate_only"


def test_relation_graph_backend_frontend_and_acceptance_are_ready():
    report = _ensure_relation_graph()
    from backend.app.main import app

    client = TestClient(app)
    graph = client.get("/api/graph")
    factors = client.get("/api/factors")
    health = client.get("/health")
    assert graph.status_code == 200
    assert graph.json()["status"] == "relation_graph_relation_graph_ready"
    assert graph.json()["edge_rows"] == report["edge_rows"]
    network = graph.json()["network"]
    assert len(network["nodes"]) == 300
    assert 1000 <= len(network["edges"]) <= 12000
    assert network["as_of_date"]
    assert network["available_node_counts"] == [20, 50, 100, 200, 300]
    assert network["available_community_counts"] == [2, 4, 6, 8, 10]
    assert network["default_node_count"] == 50
    assert network["default_community_count"] == 4
    node_symbols = {node["symbol"] for node in network["nodes"]}
    assert len(node_symbols) == 300
    assert all(
        node.get("name")
        and {"community_id", "community_assignments", "centrality_score", "degree"}.issubset(node)
        and set(node["community_assignments"]) == {"2", "4", "6", "8", "10"}
        for node in network["nodes"]
    )
    for community_count in network["available_community_counts"]:
        assignments = {node["community_assignments"][str(community_count)] for node in network["nodes"]}
        assert assignments == set(range(community_count))
    assert all(
        edge["source"] in node_symbols
        and edge["target"] in node_symbols
        and edge["source"] != edge["target"]
        and {"relation_type", "weight", "confidence", "directed"}.issubset(edge)
        and math.isfinite(edge["weight"])
        and math.isfinite(edge["confidence"])
        and 0 < edge["weight"] <= 1
        and 0 <= edge["confidence"] <= 1
        for edge in network["edges"]
    )
    assert factors.status_code == 200
    assert factors.json()["relation_graph"]["status"] == "relation_graph_relation_graph_ready"
    assert health.status_code == 200
    assert health.json()["modules"]["relation_graph"] == "relation_graph_stock_relation_graph_ready"

    page = (PROJECT_ROOT / "frontend" / "src" / "app" / "graph" / "page.tsx").read_text(encoding="utf-8")
    explorer = (PROJECT_ROOT / "frontend" / "src" / "components" / "StockRelationNetwork.tsx").read_text(encoding="utf-8")
    required_public_copy = {
        "股票关系洞察",
        "股票节点",
        "可视关系",
        "关系类型",
        "关系社区",
        "关系因子效果",
    }
    required_explorer_copy = {
        "股票关系网络",
        "graph-node",
        "graph-edge",
        "graph-relation-filter",
        "graph-node-count-select",
        "graph-community-count-select",
        "节点数量",
        "社区数量",
        "关联股票",
        "显示全部关系",
        "network.edges",
    }
    forbidden_internal_copy = {
        "ArtifactStatusCard",
        "compatibility-checkpoints",
        "真实数据入口",
        "可追溯字段",
        "验收兼容说明",
        "data_mode",
        "stock_relation_edge",
        "factor_relation_panel",
    }
    public_source = page + explorer
    assert all(text in public_source for text in required_public_copy)
    assert all(text in explorer for text in required_explorer_copy)
    assert "makeEdges" not in explorer
    assert all(text not in page and text not in explorer for text in forbidden_internal_copy)

    from scripts.check_relation_graph_acceptance import run_acceptance

    acceptance = run_acceptance()
    assert acceptance["status"] == "ok"
    assert acceptance["checks"] == 17
    assert acceptance["failed"] == []
