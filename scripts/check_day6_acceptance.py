from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

RESEARCH_BOUNDARY = "research_signals_only_not_investment_advice"
DAY6_DIR = ROOT / "reports" / "day6"
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


def _read_parquet(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    return pd.read_parquet(path)


def _docker_compose_services() -> set[str]:
    compose = ROOT / "deploy" / "docker" / "docker-compose.yml"
    try:
        proc = subprocess.run(["docker", "compose", "-f", str(compose), "config", "--services"], cwd=ROOT, text=True, capture_output=True, timeout=60, check=False)
    except Exception:
        return set()
    if proc.returncode != 0:
        return set()
    return {line.strip() for line in proc.stdout.splitlines() if line.strip()}


def run_acceptance() -> dict[str, Any]:
    from backend.app.main import app
    from fastapi.testclient import TestClient
    from streaming.flink.day6_realtime_pipeline import run_day6_realtime_pipeline

    report = run_day6_realtime_pipeline(write_outputs=True)
    topic_health = _read_json(DAY6_DIR / "topic_health.json")
    flink_status = _read_json(DAY6_DIR / "flink_job_status.json")
    snapshot = _read_json(DAY6_DIR / "online_feature_snapshot.json")
    diff = _read_json(DAY6_DIR / "realtime_vs_offline_diff_report.json")
    factors = _read_parquet(DAY6_DIR / "realtime_factor_latest.parquet")
    gold = _read_parquet(ROOT / "data" / "gold" / "factor_intraday_panel" / "part-000.parquet")
    services = _docker_compose_services()
    client = TestClient(app)
    failed: list[str] = []

    def check(name: str, condition: bool) -> None:
        if not condition:
            failed.append(name)

    topic_map = topic_health.get("topics", {})
    factor_names = set(factors["factor_name"]) if not factors.empty and "factor_name" in factors else set()
    required_factor_names = {"rt_ret_1m", "rt_ret_5m", "rt_vwap_deviation", "rt_volume_shock", "rt_market_breadth", "rt_news_sentiment_decay_1h", "rt_neighbor_return_5m"}

    check("redpanda_compose_service_declared", "redpanda" in services or (ROOT / "deploy" / "docker" / "docker-compose.yml").read_text(encoding="utf-8").find("redpanda") >= 0)
    check("flink_compose_services_declared", {"flink-jobmanager", "flink-taskmanager"}.issubset(services) or "flink-jobmanager" in (ROOT / "deploy" / "docker" / "docker-compose.yml").read_text(encoding="utf-8"))
    check("standard_topics_configured", EXPECTED_TOPICS.issubset(set(report.get("topics", []))))
    check("raw_topics_written", report.get("producer_status") == "raw_topics_written" and report.get("raw_events_written", 0) >= 30)
    check("raw_minute_topic_has_events", topic_map.get("raw.market.minute", {}).get("event_count", 0) > 0)
    check("raw_tick_topic_has_events", topic_map.get("raw.market.tick", {}).get("event_count", 0) > 0)
    check("raw_orderbook_trade_topics_have_events", topic_map.get("raw.market.orderbook", {}).get("event_count", 0) > 0 and topic_map.get("raw.market.trade", {}).get("event_count", 0) > 0)
    check("raw_news_announcement_macro_dim_have_events", all(topic_map.get(topic, {}).get("event_count", 0) > 0 for topic in ["raw.news", "raw.announcement", "raw.macro.event", "raw.dim.update"]))
    check("message_contract_fields_present", all(topic_map.get(topic, {}).get("required_fields_present") is True for topic in EXPECTED_TOPICS if topic_map.get(topic, {}).get("event_count", 0) > 0))
    check("five_flink_jobs_ready", report.get("flink_jobs_ready") == 5 and len(flink_status.get("jobs", [])) == 5)
    check("clean_topics_written", topic_map.get("clean.market.minute", {}).get("event_count", 0) > 0 and topic_map.get("clean.market.tick", {}).get("event_count", 0) > 0)
    check("factor_topics_written", all(topic_map.get(topic, {}).get("event_count", 0) > 0 for topic in ["factor.realtime.price_volume", "factor.realtime.microstructure", "factor.realtime.market_regime", "factor.realtime.news_sentiment", "factor.realtime.relation"]))
    check("realtime_factor_latest_written", not factors.empty and report.get("realtime_factor_rows") == len(factors))
    check("required_realtime_factors_available", required_factor_names.issubset(factor_names))
    check("research_boundary_and_maturity_present", not factors.empty and factors["research_boundary"].eq(RESEARCH_BOUNDARY).all() and factors["maturity"].eq("PoC").all())
    check("idempotent_keys_present", not factors.empty and factors["idempotent_key"].notna().all())
    check("online_feature_snapshot_written", snapshot.get("status") == "redis_json_cache_ready" and snapshot.get("row_count", 0) > 0)
    check("sink_status_has_queryable_store", report.get("sink_status", {}).get("sqlite_postgres_compatible") == "written" or report.get("sink_status", {}).get("parquet") == "written")
    check("gold_factor_intraday_panel_written", not gold.empty and len(gold) == len(factors))
    check("diff_report_written_and_zero_diff", diff.get("status") == "ok" and diff.get("max_abs_diff", 1) <= 1e-12)

    api_realtime = client.get("/api/realtime")
    api_flink = client.get("/api/flink-jobs")
    check("backend_realtime_api_ready", api_realtime.status_code == 200 and api_realtime.json().get("status") == "day6_realtime_pipeline_ready")
    check("backend_flink_jobs_api_ready", api_flink.status_code == 200 and api_flink.json().get("status") == "day6_flink_jobs_ready")

    realtime_page = (ROOT / "frontend" / "src" / "app" / "realtime" / "page.tsx").read_text(encoding="utf-8")
    flink_page = (ROOT / "frontend" / "src" / "app" / "flink-jobs" / "page.tsx").read_text(encoding="utf-8")
    check("frontend_realtime_page_day6_ready", "Day 6" in realtime_page and "/api/realtime" in realtime_page and "PoC / not formal signal" in realtime_page)
    check("frontend_flink_page_day6_ready", "Day 6" in flink_page and "/api/flink-jobs" in flink_page)

    result = {
        "status": "ok" if not failed else "failed",
        "checks": 24,
        "failed": failed,
        "feed_mode": report.get("feed_mode"),
        "raw_events_written": report.get("raw_events_written"),
        "topics": report.get("topics", []),
        "flink_jobs_ready": report.get("flink_jobs_ready"),
        "realtime_factor_rows": int(len(factors)),
        "online_feature_rows": int(snapshot.get("row_count", 0)),
        "diff_report": diff,
        "sink_status": report.get("sink_status", {}),
        "artifacts": report.get("artifacts", {}),
    }
    (DAY6_DIR / "acceptance_report.json").write_text(json.dumps(result, ensure_ascii=False, indent=2, default=_json_default), encoding="utf-8")
    return result


if __name__ == "__main__":
    print(json.dumps(run_acceptance(), ensure_ascii=False, indent=2, default=_json_default))
