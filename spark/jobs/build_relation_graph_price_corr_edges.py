from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def run_job() -> dict[str, Any]:
    from graph.relation_graph_relation_graph import build_stock_relation_edges, _ensure_event_regime_feature

    feature = _ensure_event_regime_feature()
    edges = build_stock_relation_edges(feature, write_outputs=True)
    price_corr_edges = edges[edges["relation_type"].eq("price_corr")]
    status = {
        "status": "spark_compatible_price_corr_edges_ready",
        "job_name": "build_relation_graph_price_corr_edges",
        "engine": "spark-compatible local batch relation edge materialization",
        "price_corr_edges": int(len(price_corr_edges)),
        "source_feature_set": "model_feature_matrix_wide_event_regime",
        "target_table": "data/gold/stock_relation_edge",
        "research_boundary": "research_signals_only_not_investment_advice",
    }
    out = ROOT / "reports" / "relation_graph" / "spark_price_corr_edge_job.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(status, ensure_ascii=False, indent=2), encoding="utf-8")
    return status


if __name__ == "__main__":
    print(json.dumps(run_job(), ensure_ascii=False, indent=2))
