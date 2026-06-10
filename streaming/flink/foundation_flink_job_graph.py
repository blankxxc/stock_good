from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
GRAPH = {
    "job_name": "foundation_realtime_factor_job_graph",
    "maturity": "L1-job-graph-submit-contract",
    "runtime": "Flink/PyFlink planned; generated graph is used when PyFlink runtime is unavailable",
    "jobs": [
        {"name": "market_cleaning", "inputs": ["raw.market.tick", "raw.market.minute"], "outputs": ["clean.market.tick", "clean.market.minute"], "time_semantics": "event_time + watermark + late_data_side_output"},
        {"name": "price_volume_factor", "inputs": ["clean.market.minute"], "outputs": ["factor.realtime.price_volume"], "windows": ["1m", "5m", "15m", "30m"]},
        {"name": "news_announcement_factor", "inputs": ["raw.news", "raw.announcement"], "outputs": ["clean.news.event", "clean.announcement.event", "factor.realtime.news_sentiment"]},
        {"name": "market_regime_factor", "inputs": ["raw.index.realtime", "raw.macro.event"], "outputs": ["factor.realtime.market_regime"]},
        {"name": "relation_spillover_factor", "inputs": ["clean.market.minute", "clean.news.event", "stock_relation_edge"], "outputs": ["factor.realtime.relation"]},
    ],
}


def main() -> None:
    out = ROOT / "reports" / "foundation" / "flink_job_graph.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(GRAPH, ensure_ascii=False, indent=2), encoding="utf-8")
    print(out)


if __name__ == "__main__":
    main()
