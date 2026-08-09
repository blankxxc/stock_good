from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
from fastapi.testclient import TestClient

from tests.auth_helpers import authenticated_admin_client

PROJECT_ROOT = Path(__file__).resolve().parents[1]
RESEARCH_BOUNDARY = "research_signals_only_not_investment_advice"


EXPECTED_TOPICS = {
    "raw.market.tick",
    "raw.market.trade",
    "raw.market.orderbook",
    "raw.market.minute",
    "raw.index.realtime",
    "raw.futures.realtime",
    "raw.news",
    "raw.announcement",
    "raw.social.sentiment",
    "raw.macro.event",
    "raw.dim.update",
    "clean.market.tick",
    "clean.market.minute",
    "clean.news.event",
    "clean.announcement.event",
    "factor.realtime.price_volume",
    "factor.realtime.microstructure",
    "factor.realtime.market_regime",
    "factor.realtime.news_sentiment",
    "factor.realtime.relation",
    "feature.online.snapshot",
    "signal.cross_sectional.realtime",
    "alert.data_quality",
    "alert.risk",
}


def _ensure_realtime_streaming() -> dict:
    from streaming.flink.realtime_streaming_realtime_pipeline import run_realtime_streaming_realtime_pipeline

    return run_realtime_streaming_realtime_pipeline(write_outputs=True)


def test_realtime_streaming_topics_producers_and_message_contract_are_ready():
    report = _ensure_realtime_streaming()
    assert report["status"] == "ok"
    assert report["feed_mode"] == "replay_simulated_not_live_market_data"
    assert EXPECTED_TOPICS.issubset(set(report["topics"]))
    assert report["raw_events_written"] >= 30
    assert report["producer_status"] == "raw_topics_written"

    topic_health_path = PROJECT_ROOT / "reports" / "realtime_streaming" / "topic_health.json"
    health = json.loads(topic_health_path.read_text(encoding="utf-8"))
    assert EXPECTED_TOPICS.issubset(set(health["topics"].keys()))
    for topic in ["raw.market.minute", "raw.market.tick", "raw.news", "raw.announcement", "raw.macro.event", "raw.dim.update"]:
        assert health["topics"][topic]["event_count"] > 0
        assert health["topics"][topic]["required_fields_present"] is True

    minute_log = PROJECT_ROOT / "data" / "realtime" / "kafka_topics" / "raw.market.minute.jsonl"
    first = json.loads(minute_log.read_text(encoding="utf-8").splitlines()[0])
    assert {"event_time", "ingest_time", "source", "symbol", "exchange", "trade_date", "payload", "trace_id", "schema_version"}.issubset(first)
    assert first["source"] == "synthetic_minute_replay"


def test_realtime_streaming_flink_like_jobs_emit_realtime_factors_sinks_and_diff_report():
    report = _ensure_realtime_streaming()
    assert report["flink_jobs_ready"] == 5
    assert report["realtime_factor_rows"] > 0
    assert report["online_feature_rows"] > 0
    assert report["sink_status"]["parquet"] == "written"
    assert report["sink_status"]["redis_json_cache"] == "written"
    assert report["sink_status"]["sqlite_postgres_compatible"] == "written"
    assert report["diff_report"]["max_abs_diff"] <= 1e-12

    factors = pd.read_parquet(PROJECT_ROOT / "reports" / "realtime_streaming" / "realtime_factor_latest.parquet")
    required_columns = {
        "event_time",
        "trade_date",
        "symbol",
        "factor_name",
        "factor_value",
        "window",
        "factor_version",
        "source_topic",
        "output_topic",
        "idempotent_key",
        "maturity",
        "research_boundary",
    }
    assert required_columns.issubset(factors.columns)
    assert factors["research_boundary"].eq(RESEARCH_BOUNDARY).all()
    assert factors["maturity"].eq("PoC").all()
    assert {"rt_ret_1m", "rt_ret_5m", "rt_vwap_deviation", "rt_volume_shock", "rt_market_breadth", "rt_news_sentiment_decay_1h", "rt_neighbor_return_5m"}.issubset(set(factors["factor_name"]))
    assert factors["idempotent_key"].str.contains("|").all()

    gold = pd.read_parquet(PROJECT_ROOT / "data" / "gold" / "factor_intraday_panel" / "part-000.parquet")
    assert len(gold) == len(factors)
    assert (PROJECT_ROOT / "reports" / "realtime_streaming" / "realtime_vs_offline_diff_report.json").is_file()
    assert (PROJECT_ROOT / "reports" / "realtime_streaming" / "realtime_vs_offline_diff_report.html").is_file()


def test_realtime_streaming_backend_api_and_frontend_pages_are_ready():
    report = _ensure_realtime_streaming()
    assert report["status"] == "ok"

    from backend.app.main import app

    client = authenticated_admin_client(app)
    realtime = client.get("/api/realtime")
    flink = client.get("/api/flink-jobs")
    assert realtime.status_code == 200
    assert flink.status_code == 200
    assert realtime.json()["status"] == "realtime_streaming_realtime_pipeline_ready"
    assert realtime.json()["topic_health"]["raw.market.minute"]["event_count"] > 0
    assert realtime.json()["online_feature_snapshot"]["status"] == "redis_json_cache_ready"
    assert flink.json()["status"] == "realtime_streaming_flink_jobs_ready"
    assert len(flink.json()["jobs"]) == 5

    realtime_page = (PROJECT_ROOT / "frontend" / "src" / "app" / "realtime" / "page.tsx").read_text(encoding="utf-8")
    flink_page = (PROJECT_ROOT / "frontend" / "src" / "app" / "flink-jobs" / "page.tsx").read_text(encoding="utf-8")
    assert "realtime_streaming" in realtime_page and "/api/realtime" in realtime_page
    assert "PoC / not formal signal" in realtime_page
    assert "realtime_streaming" in flink_page and "/api/flink-jobs" in flink_page


def test_realtime_streaming_acceptance_script_reports_ok():
    from scripts.check_realtime_streaming_acceptance import run_acceptance

    result = run_acceptance()
    assert result["status"] == "ok"
    assert result["checks"] >= 20
    assert result["failed"] == []
    assert result["realtime_factor_rows"] > 0
    assert result["flink_jobs_ready"] == 5
