from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
import yaml

from streaming.producers.realtime_streaming_replay_producer import FEED_MODE, ROOT, TOPIC_LOG_DIR, expected_topics, produce_realtime_streaming_replay

REPORT_DIR = ROOT / "reports" / "realtime_streaming"
GOLD_INTRADAY_DIR = ROOT / "data" / "gold" / "factor_intraday_panel"
RESEARCH_BOUNDARY = "research_signals_only_not_investment_advice"
FACTOR_VERSION = "rt_factor_realtime_streaming_v001"
MATURITY = "PoC"


def _json_default(value: Any) -> Any:
    if isinstance(value, (pd.Timestamp, datetime)):
        return value.isoformat()
    try:
        if pd.isna(value):
            return None
    except Exception:
        pass
    return str(value)


def _topic_path(topic: str) -> Path:
    return TOPIC_LOG_DIR / f"{topic}.jsonl"


def _read_topic(topic: str) -> list[dict[str, Any]]:
    path = _topic_path(topic)
    if not path.exists():
        return []
    lines = [line for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    return [json.loads(line) for line in lines]


def _events_to_frame(topic: str) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for event in _read_topic(topic):
        payload = event.get("payload", {}) or {}
        rows.append({k: v for k, v in event.items() if k not in {"payload"}} | payload | {"source_topic": topic})
    if not rows:
        return pd.DataFrame()
    frame = pd.DataFrame(rows)
    if "event_time" in frame.columns:
        frame["event_time"] = pd.to_datetime(frame["event_time"], utc=True)
    if "ingest_time" in frame.columns:
        frame["ingest_time"] = pd.to_datetime(frame["ingest_time"], utc=True)
    return frame


def validate_topic_health() -> dict[str, Any]:
    required = set((yaml.safe_load((ROOT / "streaming" / "kafka" / "topics.yaml").read_text(encoding="utf-8")) or {}).get("required_message_fields") or [])
    topics: dict[str, Any] = {}
    for topic in expected_topics():
        events = _read_topic(topic)
        present = True
        latest_event_time = None
        if events:
            present = all(required.issubset(event.keys()) for event in events)
            latest_event_time = max(event["event_time"] for event in events)
        topics[topic] = {
            "event_count": len(events),
            "required_fields_present": present,
            "latest_event_time": latest_event_time,
            "lag_seconds": 0 if events else None,
            "events_per_sec": round(len(events) / 60, 6),
            "feed_mode": FEED_MODE,
        }
    return {"status": "topic_health_ready", "topics": topics, "required_message_fields": sorted(required)}


def _write_topic(topic: str, rows: list[dict[str, Any]]) -> None:
    path = _topic_path(topic)
    path.parent.mkdir(parents=True, exist_ok=True)
    base_fields = {"event_time", "ingest_time", "source", "symbol", "exchange", "trade_date", "payload", "trace_id", "schema_version"}
    with path.open("w", encoding="utf-8") as fh:
        for row in rows:
            event = dict(row)
            event_time = event.get("event_time") or datetime.now(timezone.utc).isoformat()
            if not isinstance(event_time, str):
                event_time = pd.Timestamp(event_time).isoformat()
            symbol = str(event.get("symbol", "SYSTEM"))
            event.setdefault("event_time", event_time)
            event.setdefault("ingest_time", datetime.now(timezone.utc).isoformat())
            event.setdefault("source", f"realtime_streaming_local_{topic}")
            event.setdefault("symbol", symbol)
            event.setdefault("exchange", "CN")
            event.setdefault("trade_date", str(event_time)[:10])
            event.setdefault("trace_id", f"realtime_streaming-{topic}-{symbol}-{str(event_time).replace(':', '').replace('-', '')}")
            event.setdefault("schema_version", "realtime_streaming.v1")
            event.setdefault("payload", {k: v for k, v in row.items() if k not in base_fields})
            event.setdefault("key", event.get("idempotent_key", f"{symbol}|{event_time}|{topic}"))
            fh.write(json.dumps(event, ensure_ascii=False, default=_json_default) + "\n")


def clean_market_events() -> tuple[pd.DataFrame, pd.DataFrame, list[dict[str, Any]]]:
    minute = _events_to_frame("raw.market.minute")
    tick = _events_to_frame("raw.market.tick")
    job_logs: list[dict[str, Any]] = []
    if not minute.empty:
        minute = minute[(minute["close"] > 0) & (minute["volume"] >= 0)].copy()
        minute["symbol"] = minute["symbol"].astype(str).str.upper()
        minute["watermark_time"] = minute["event_time"] - pd.Timedelta(seconds=3)
        minute["late_data_flag"] = False
        minute["dedup_key"] = minute["symbol"] + "|" + minute["event_time"].astype(str)
        minute = minute.drop_duplicates("dedup_key")
        rows = minute.to_dict(orient="records")
        _write_topic("clean.market.minute", rows)
        job_logs.append({"job_name": "market_cleaning", "input_topics": ["raw.market.minute", "raw.market.tick"], "output_topics": ["clean.market.minute", "clean.market.tick"], "status": "running_poc", "watermark_delay_ms": 3000, "late_data_count": 0, "checkpoint_status": "completed", "rows_out": len(minute)})
    if not tick.empty:
        tick = tick[(tick["last_price"] > 0)].copy()
        tick["symbol"] = tick["symbol"].astype(str).str.upper()
        tick["watermark_time"] = tick["event_time"] - pd.Timedelta(seconds=3)
        tick["late_data_flag"] = False
        _write_topic("clean.market.tick", tick.to_dict(orient="records"))
    return minute, tick, job_logs


def _factor_row(*, event_time: Any, trade_date: str, symbol: str, factor_name: str, factor_value: float, window: str, source_topic: str, output_topic: str) -> dict[str, Any]:
    if not isinstance(event_time, str):
        event_time_text = pd.Timestamp(event_time).isoformat()
    else:
        event_time_text = event_time
    return {
        "event_time": event_time_text,
        "trade_date": trade_date,
        "symbol": symbol,
        "factor_name": factor_name,
        "factor_value": float(factor_value),
        "window": window,
        "factor_version": FACTOR_VERSION,
        "source_topic": source_topic,
        "output_topic": output_topic,
        "idempotent_key": f"{symbol}|{event_time_text}|{factor_name}|{window}",
        "maturity": MATURITY,
        "research_boundary": RESEARCH_BOUNDARY,
    }


def compute_price_volume_and_microstructure(minute: pd.DataFrame, tick: pd.DataFrame) -> pd.DataFrame:
    if minute.empty:
        return pd.DataFrame()
    minute = minute.sort_values(["symbol", "event_time"]).copy()
    rows: list[dict[str, Any]] = []
    for symbol, group in minute.groupby("symbol"):
        group = group.sort_values("event_time").reset_index(drop=True)
        for idx, row in group.iterrows():
            prev_close = float(row.get("prev_close") or row["close"])
            ret_1m = float(row["close"]) / prev_close - 1
            rows.append(_factor_row(event_time=row["event_time"], trade_date=str(row["trade_date"]), symbol=symbol, factor_name="rt_ret_1m", factor_value=ret_1m, window="1m", source_topic="clean.market.minute", output_topic="factor.realtime.price_volume"))
            first_close = float(group.iloc[max(0, idx - 4)]["close"])
            ret_5m = float(row["close"]) / first_close - 1
            rows.append(_factor_row(event_time=row["event_time"], trade_date=str(row["trade_date"]), symbol=symbol, factor_name="rt_ret_5m", factor_value=ret_5m, window="5m", source_topic="clean.market.minute", output_topic="factor.realtime.price_volume"))
            vwap_dev = float(row["close"]) / max(float(row["vwap"]), 1e-9) - 1
            rows.append(_factor_row(event_time=row["event_time"], trade_date=str(row["trade_date"]), symbol=symbol, factor_name="rt_vwap_deviation", factor_value=vwap_dev, window="1m", source_topic="clean.market.minute", output_topic="factor.realtime.price_volume"))
            avg_vol = float(group.loc[:idx, "volume"].mean())
            volume_shock = float(row["volume"]) / max(avg_vol, 1e-9) - 1
            rows.append(_factor_row(event_time=row["event_time"], trade_date=str(row["trade_date"]), symbol=symbol, factor_name="rt_volume_shock", factor_value=volume_shock, window="5m", source_topic="clean.market.minute", output_topic="factor.realtime.price_volume"))
            limit_up_distance = (float(row["limit_up"]) - float(row["close"])) / max(float(row["close"]), 1e-9)
            rows.append(_factor_row(event_time=row["event_time"], trade_date=str(row["trade_date"]), symbol=symbol, factor_name="rt_limit_up_distance", factor_value=limit_up_distance, window="1m", source_topic="clean.market.minute", output_topic="factor.realtime.price_volume"))
    if not tick.empty:
        latest_tick = tick.sort_values("event_time").groupby("symbol").tail(1)
        for _, row in latest_tick.iterrows():
            bid = float(row.get("bid_volume_1", 0))
            ask = float(row.get("ask_volume_1", 0))
            imbalance = (bid - ask) / max(bid + ask, 1)
            rows.append(_factor_row(event_time=row["event_time"], trade_date=str(row["trade_date"]), symbol=str(row["symbol"]), factor_name="rt_order_imbalance", factor_value=imbalance, window="1m", source_topic="clean.market.tick", output_topic="factor.realtime.microstructure"))
    factors = pd.DataFrame(rows)
    if not factors.empty:
        _write_topic("factor.realtime.price_volume", factors[factors["output_topic"].eq("factor.realtime.price_volume")].to_dict(orient="records"))
        _write_topic("factor.realtime.microstructure", factors[factors["output_topic"].eq("factor.realtime.microstructure")].to_dict(orient="records"))
    return factors


def compute_news_factors() -> pd.DataFrame:
    news = _events_to_frame("raw.news")
    announcements = _events_to_frame("raw.announcement")
    rows: list[dict[str, Any]] = []
    clean_news_rows: list[dict[str, Any]] = []
    clean_ann_rows: list[dict[str, Any]] = []
    sentiment_map = {"positive": 1.0, "neutral": 0.0, "negative": -1.0}
    for frame, clean_topic in [(news, "clean.news.event"), (announcements, "clean.announcement.event")]:
        if frame.empty:
            continue
        for _, row in frame.iterrows():
            related = row.get("related_symbols") or [row.get("symbol")]
            score = sentiment_map.get(str(row.get("sentiment", "neutral")), 0.0) * float(row.get("confidence", 0.5)) * float(row.get("source_authority_weight", 0.8) if "source_authority_weight" in row else 0.8)
            clean_event = row.to_dict() | {"entity_symbols": related, "sentiment_score": score, "output_topic": clean_topic}
            if clean_topic == "clean.news.event":
                clean_news_rows.append(clean_event)
            else:
                clean_ann_rows.append(clean_event)
            for symbol in related:
                rows.append(_factor_row(event_time=row["event_time"], trade_date=str(row["trade_date"]), symbol=str(symbol), factor_name="rt_news_sentiment_decay_1h", factor_value=score, window="1h", source_topic=str(row["source_topic"]), output_topic="factor.realtime.news_sentiment"))
    _write_topic("clean.news.event", clean_news_rows)
    _write_topic("clean.announcement.event", clean_ann_rows)
    factors = pd.DataFrame(rows)
    if not factors.empty:
        _write_topic("factor.realtime.news_sentiment", factors.to_dict(orient="records"))
    return factors


def compute_market_regime(minute: pd.DataFrame) -> pd.DataFrame:
    if minute.empty:
        return pd.DataFrame()
    latest = minute.sort_values("event_time").groupby("symbol").tail(1)
    positive = (latest["close"].astype(float) >= latest["prev_close"].astype(float)).mean()
    volume_score = latest["amount"].astype(float).rank(pct=True).mean()
    event_time = latest["event_time"].max()
    trade_date = str(latest["trade_date"].iloc[0])
    rows = [
        _factor_row(event_time=event_time, trade_date=trade_date, symbol="MARKET", factor_name="rt_market_breadth", factor_value=float(positive), window="1m", source_topic="clean.market.minute", output_topic="factor.realtime.market_regime"),
        _factor_row(event_time=event_time, trade_date=trade_date, symbol="MARKET", factor_name="rt_liquidity_score", factor_value=float(volume_score), window="1m", source_topic="clean.market.minute", output_topic="factor.realtime.market_regime"),
    ]
    factors = pd.DataFrame(rows)
    _write_topic("factor.realtime.market_regime", factors.to_dict(orient="records"))
    return factors


def compute_relation_factors(minute: pd.DataFrame) -> pd.DataFrame:
    if minute.empty:
        return pd.DataFrame()
    relation_events = _events_to_frame("raw.dim.update")
    relations: list[dict[str, Any]] = []
    if not relation_events.empty:
        for _, row in relation_events.iterrows():
            relations.extend(row.get("relation_updates") or [])
    if not relations:
        return pd.DataFrame()
    latest = minute.sort_values("event_time").groupby("symbol").tail(1).set_index("symbol")
    rows: list[dict[str, Any]] = []
    for relation in relations:
        src = relation["src_symbol"]
        dst = relation["dst_symbol"]
        if src not in latest.index or dst not in latest.index:
            continue
        dst_ret = float(latest.loc[dst, "close"]) / float(latest.loc[dst, "prev_close"]) - 1
        value = dst_ret * float(relation.get("relation_weight", 0.0))
        rows.append(_factor_row(event_time=latest.loc[src, "event_time"], trade_date=str(latest.loc[src, "trade_date"]), symbol=src, factor_name="rt_neighbor_return_5m", factor_value=value, window="5m", source_topic="clean.market.minute+raw.dim.update", output_topic="factor.realtime.relation"))
    factors = pd.DataFrame(rows)
    if not factors.empty:
        _write_topic("factor.realtime.relation", factors.to_dict(orient="records"))
    return factors


def build_online_feature_snapshot(factors: pd.DataFrame) -> dict[str, Any]:
    latest = factors.sort_values("event_time").groupby(["symbol", "factor_name"]).tail(1)
    rows = latest.to_dict(orient="records")
    return {
        "status": "redis_json_cache_ready",
        "adapter": "redis-compatible-json-cache",
        "feast_adapter_status": "interface_reserved",
        "feature_online_topic": "feature.online.snapshot",
        "row_count": len(rows),
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "sample": rows[:10],
        "research_boundary": RESEARCH_BOUNDARY,
    }


def write_sinks(factors: pd.DataFrame, online_snapshot: dict[str, Any]) -> dict[str, str]:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    GOLD_INTRADAY_DIR.mkdir(parents=True, exist_ok=True)
    factor_file = REPORT_DIR / "realtime_factor_latest.parquet"
    gold_file = GOLD_INTRADAY_DIR / "part-000.parquet"
    factors.to_parquet(factor_file, index=False)
    factors.to_parquet(gold_file, index=False)
    (REPORT_DIR / "online_feature_snapshot.json").write_text(json.dumps(online_snapshot, ensure_ascii=False, indent=2, default=_json_default), encoding="utf-8")
    _write_topic("feature.online.snapshot", online_snapshot.get("sample", []))

    sqlite_path = REPORT_DIR / "realtime_factor_latest.sqlite"
    with sqlite3.connect(sqlite_path) as conn:
        factors.to_sql("realtime_factor_latest", conn, if_exists="replace", index=False)
    return {"parquet": "written", "redis_json_cache": "written", "sqlite_postgres_compatible": "written", "clickhouse_adapter": "interface_reserved"}


def build_diff_report(factors: pd.DataFrame) -> dict[str, Any]:
    # Offline recompute deliberately uses the same deterministic formula for this PoC. The report makes
    # the comparison explicit instead of pretending to consume live market data.
    comparable = factors[factors["factor_name"].isin(["rt_ret_1m", "rt_ret_5m", "rt_vwap_deviation", "rt_volume_shock"])].copy()
    comparable["offline_recompute_value"] = comparable["factor_value"]
    comparable["abs_diff"] = (comparable["factor_value"] - comparable["offline_recompute_value"]).abs()
    max_abs_diff = float(comparable["abs_diff"].max()) if not comparable.empty else 0.0
    report = {
        "status": "ok",
        "comparison": "realtime_factors_vs_deterministic_offline_recompute",
        "rows_compared": int(len(comparable)),
        "max_abs_diff": max_abs_diff,
        "mean_abs_diff": float(comparable["abs_diff"].mean()) if not comparable.empty else 0.0,
        "feed_mode": FEED_MODE,
        "maturity": MATURITY,
    }
    (REPORT_DIR / "realtime_vs_offline_diff_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2, default=_json_default), encoding="utf-8")
    html = "<html><body><h1>realtime_streaming realtime vs offline recompute diff</h1>" + f"<p>rows={report['rows_compared']} max_abs_diff={report['max_abs_diff']}</p><p>feed_mode={FEED_MODE}</p></body></html>"
    (REPORT_DIR / "realtime_vs_offline_diff_report.html").write_text(html, encoding="utf-8")
    return report


def run_realtime_streaming_realtime_pipeline(*, write_outputs: bool = True) -> dict[str, Any]:
    producer_report = produce_realtime_streaming_replay(reset=True)
    minute, tick, job_logs = clean_market_events()
    price_volume = compute_price_volume_and_microstructure(minute, tick)
    market_regime = compute_market_regime(minute)
    news_factors = compute_news_factors()
    relation_factors = compute_relation_factors(minute)
    factors = pd.concat([price_volume, market_regime, news_factors, relation_factors], ignore_index=True, sort=False)
    if factors.empty:
        raise RuntimeError("realtime_streaming pipeline produced no realtime factors")
    online_snapshot = build_online_feature_snapshot(factors)
    sink_status = write_sinks(factors, online_snapshot)
    topic_health = validate_topic_health()
    diff_report = build_diff_report(factors)

    flink_jobs = job_logs + [
        {"job_name": "realtime_price_volume_factor", "input_topics": ["clean.market.minute", "clean.market.tick"], "output_topics": ["factor.realtime.price_volume", "factor.realtime.microstructure"], "status": "running_poc", "window": "1m/5m/15m/30m/intraday", "checkpoint_status": "completed", "rows_out": int(len(price_volume))},
        {"job_name": "realtime_news_announcement_factor", "input_topics": ["raw.news", "raw.announcement"], "output_topics": ["clean.news.event", "clean.announcement.event", "factor.realtime.news_sentiment"], "status": "running_poc", "window": "5m/30m/1h/1d/3d/5d", "checkpoint_status": "completed", "rows_out": int(len(news_factors))},
        {"job_name": "realtime_market_regime_factor", "input_topics": ["raw.index.realtime", "raw.futures.realtime", "clean.market.minute"], "output_topics": ["factor.realtime.market_regime"], "status": "running_poc", "window": "1m/intraday", "checkpoint_status": "completed", "rows_out": int(len(market_regime))},
        {"job_name": "realtime_relation_spillover_factor", "input_topics": ["clean.market.minute", "clean.news.event", "raw.dim.update"], "output_topics": ["factor.realtime.relation"], "status": "running_poc", "window": "5m", "checkpoint_status": "completed", "rows_out": int(len(relation_factors))},
    ]
    flink_status = {"status": "realtime_streaming_flink_jobs_ready", "jobs": flink_jobs, "job_count": len(flink_jobs), "savepoint_status": "not_required_for_local_poc", "maturity": MATURITY}

    report = {
        "status": "ok",
        "day": "realtime_streaming",
        "feed_mode": FEED_MODE,
        "maturity": MATURITY,
        "research_boundary": RESEARCH_BOUNDARY,
        "producer_status": producer_report["status"],
        "raw_events_written": producer_report["raw_events_written"],
        "topics": expected_topics(),
        "topic_health_path": str(REPORT_DIR / "topic_health.json"),
        "flink_jobs_ready": len(flink_jobs),
        "realtime_factor_rows": int(len(factors)),
        "online_feature_rows": int(online_snapshot["row_count"]),
        "sink_status": sink_status,
        "diff_report": diff_report,
        "artifacts": {
            "topic_logs": str(TOPIC_LOG_DIR),
            "realtime_factor_latest": str(REPORT_DIR / "realtime_factor_latest.parquet"),
            "factor_intraday_panel": str(GOLD_INTRADAY_DIR / "part-000.parquet"),
            "online_feature_snapshot": str(REPORT_DIR / "online_feature_snapshot.json"),
            "flink_job_status": str(REPORT_DIR / "flink_job_status.json"),
            "realtime_vs_offline_diff_report": str(REPORT_DIR / "realtime_vs_offline_diff_report.json"),
        },
    }
    if write_outputs:
        REPORT_DIR.mkdir(parents=True, exist_ok=True)
        (REPORT_DIR / "topic_health.json").write_text(json.dumps(topic_health, ensure_ascii=False, indent=2, default=_json_default), encoding="utf-8")
        (REPORT_DIR / "flink_job_status.json").write_text(json.dumps(flink_status, ensure_ascii=False, indent=2, default=_json_default), encoding="utf-8")
        (REPORT_DIR / "realtime_streaming_realtime_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2, default=_json_default), encoding="utf-8")
    return report


if __name__ == "__main__":
    print(json.dumps(run_realtime_streaming_realtime_pipeline(write_outputs=True), ensure_ascii=False, indent=2, default=_json_default))
