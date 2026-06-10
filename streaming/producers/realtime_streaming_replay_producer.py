from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[2]
TOPIC_CONTRACT = ROOT / "streaming" / "kafka" / "topics.yaml"
TOPIC_LOG_DIR = ROOT / "data" / "realtime" / "kafka_topics"
SCHEMA_VERSION = "realtime_streaming.v1"
FEED_MODE = "replay_simulated_not_live_market_data"


@dataclass(frozen=True)
class TopicEvent:
    topic: str
    key: str
    value: dict[str, Any]


def load_topic_contract() -> dict[str, Any]:
    return yaml.safe_load(TOPIC_CONTRACT.read_text(encoding="utf-8")) or {}


def expected_topics() -> list[str]:
    return sorted((load_topic_contract().get("topics") or {}).keys())


def _base_event(*, topic: str, symbol: str, event_time: datetime, source: str, payload: dict[str, Any], exchange: str = "SSE") -> dict[str, Any]:
    trade_date = event_time.date().isoformat()
    trace_id = f"realtime_streaming-{topic}-{symbol}-{event_time.strftime('%Y%m%d%H%M%S')}"
    return {
        "event_time": event_time.isoformat(),
        "ingest_time": (event_time + timedelta(seconds=2)).isoformat(),
        "source": source,
        "feed_mode": FEED_MODE,
        "symbol": symbol,
        "exchange": exchange,
        "trade_date": trade_date,
        "payload": payload,
        "trace_id": trace_id,
        "schema_version": SCHEMA_VERSION,
    }


def build_realtime_streaming_replay_events() -> list[TopicEvent]:
    start = datetime(2026, 1, 5, 9, 31, tzinfo=timezone.utc)
    symbols = ["600001.SH", "600002.SH", "000001.SZ", "000002.SZ", "300001.SZ"]
    industries = {
        "600001.SH": "bank",
        "600002.SH": "bank",
        "000001.SZ": "broker",
        "000002.SZ": "property",
        "300001.SZ": "technology",
    }
    base_prices = {
        "600001.SH": 10.0,
        "600002.SH": 12.0,
        "000001.SZ": 16.0,
        "000002.SZ": 8.0,
        "300001.SZ": 22.0,
    }
    events: list[TopicEvent] = []
    for i in range(6):
        event_time = start + timedelta(minutes=i)
        for idx, symbol in enumerate(symbols):
            drift = (i * 0.015) + (idx * 0.01)
            close = round(base_prices[symbol] * (1 + drift / 100), 4)
            open_price = round(close * (1 - 0.0008), 4)
            high = round(max(open_price, close) * 1.0015, 4)
            low = round(min(open_price, close) * 0.9985, 4)
            volume = 12000 + i * 700 + idx * 450
            amount = round(volume * close, 2)
            vwap = round(amount / volume, 4)
            minute_payload = {
                "open": open_price,
                "high": high,
                "low": low,
                "close": close,
                "volume": volume,
                "amount": amount,
                "vwap": vwap,
                "industry": industries[symbol],
                "prev_close": base_prices[symbol],
                "limit_up": round(base_prices[symbol] * 1.1, 4),
                "limit_down": round(base_prices[symbol] * 0.9, 4),
            }
            key = f"{symbol}|{event_time.isoformat()}|raw|1m"
            events.append(TopicEvent("raw.market.minute", key, _base_event(topic="raw.market.minute", symbol=symbol, event_time=event_time, source="synthetic_minute_replay", payload=minute_payload, exchange=symbol.split(".")[-1])))

            tick_payload = {
                "last_price": close,
                "bid_price_1": round(close * 0.999, 4),
                "ask_price_1": round(close * 1.001, 4),
                "bid_volume_1": 2000 + idx * 100,
                "ask_volume_1": 1800 + i * 80,
                "trade_count": 80 + i * 8 + idx,
            }
            events.append(TopicEvent("raw.market.tick", key.replace("raw", "tick"), _base_event(topic="raw.market.tick", symbol=symbol, event_time=event_time, source="synthetic_tick_simulator", payload=tick_payload, exchange=symbol.split(".")[-1])))

            trade_payload = {"price": close, "volume": int(volume / 20), "side": "buy" if (i + idx) % 2 == 0 else "sell"}
            events.append(TopicEvent("raw.market.trade", key.replace("raw", "trade"), _base_event(topic="raw.market.trade", symbol=symbol, event_time=event_time, source="synthetic_trade_simulator", payload=trade_payload, exchange=symbol.split(".")[-1])))

            orderbook_payload = {
                "bid_price_1": tick_payload["bid_price_1"],
                "ask_price_1": tick_payload["ask_price_1"],
                "bid_volume_1": tick_payload["bid_volume_1"],
                "ask_volume_1": tick_payload["ask_volume_1"],
                "order_imbalance": round((tick_payload["bid_volume_1"] - tick_payload["ask_volume_1"]) / max(tick_payload["bid_volume_1"] + tick_payload["ask_volume_1"], 1), 6),
            }
            events.append(TopicEvent("raw.market.orderbook", key.replace("raw", "orderbook"), _base_event(topic="raw.market.orderbook", symbol=symbol, event_time=event_time, source="synthetic_orderbook_simulator", payload=orderbook_payload, exchange=symbol.split(".")[-1])))

        index_payload = {"close": round(3500 * (1 + i * 0.01 / 100), 4), "return_1m": round(i * 0.0001, 6), "volume": 800000 + i * 12000}
        events.append(TopicEvent("raw.index.realtime", f"CSI300|{event_time.isoformat()}|index|1m", _base_event(topic="raw.index.realtime", symbol="CSI300", event_time=event_time, source="synthetic_index_replay", payload=index_payload, exchange="CSI")))
        futures_payload = {"close": round(3550 * (1 + i * 0.008 / 100), 4), "basis_bp": round(5 + i * 0.2, 4)}
        events.append(TopicEvent("raw.futures.realtime", f"IF|{event_time.isoformat()}|futures|1m", _base_event(topic="raw.futures.realtime", symbol="IF_DEMO", event_time=event_time, source="synthetic_futures_replay", payload=futures_payload, exchange="CFFEX")))

    news_time = start + timedelta(minutes=2)
    news_payload = {
        "title": "银行板块获得政策支持的样例新闻",
        "content_hash": "realtime_streaming-news-001",
        "related_symbols": ["600001.SH", "600002.SH"],
        "related_industries": ["bank"],
        "event_type": "policy_support",
        "sentiment": "positive",
        "confidence": 0.78,
        "source_authority_weight": 0.7,
    }
    events.append(TopicEvent("raw.news", f"NEWS001|{news_time.isoformat()}|news|1h", _base_event(topic="raw.news", symbol="MULTI", event_time=news_time, source="synthetic_news_event", payload=news_payload, exchange="CN")))
    ann_payload = {
        "announcement_id": "ANN001",
        "related_symbols": ["300001.SZ"],
        "announcement_type": "order_win",
        "sentiment": "positive",
        "confidence": 0.73,
    }
    events.append(TopicEvent("raw.announcement", f"ANN001|{news_time.isoformat()}|announcement|1h", _base_event(topic="raw.announcement", symbol="300001.SZ", event_time=news_time, source="synthetic_announcement_event", payload=ann_payload, exchange="SZ")))
    social_payload = {"related_symbols": ["000002.SZ"], "sentiment": "negative", "confidence": 0.55, "source_authority_weight": 0.3}
    events.append(TopicEvent("raw.social.sentiment", f"SOC001|{news_time.isoformat()}|social|1h", _base_event(topic="raw.social.sentiment", symbol="000002.SZ", event_time=news_time, source="synthetic_social_sentiment", payload=social_payload, exchange="CN")))
    macro_payload = {"event_type": "liquidity_injection", "sentiment": "positive", "risk_appetite_delta": 0.12, "confidence": 0.66}
    events.append(TopicEvent("raw.macro.event", f"MACRO001|{news_time.isoformat()}|macro|1h", _base_event(topic="raw.macro.event", symbol="CN_MACRO", event_time=news_time, source="synthetic_macro_event", payload=macro_payload, exchange="CN")))
    dim_payload = {"relation_updates": [{"src_symbol": "600001.SH", "dst_symbol": "600002.SH", "relation_type": "industry_same", "relation_weight": 0.8}, {"src_symbol": "600001.SH", "dst_symbol": "000001.SZ", "relation_type": "financial_sector", "relation_weight": 0.45}]}
    events.append(TopicEvent("raw.dim.update", f"DIM001|{news_time.isoformat()}|dim|1d", _base_event(topic="raw.dim.update", symbol="DIM_STOCK_RELATION", event_time=news_time, source="synthetic_dim_update", payload=dim_payload, exchange="CN")))
    return events


def write_events(events: list[TopicEvent], *, reset: bool = True) -> dict[str, Any]:
    if reset and TOPIC_LOG_DIR.exists():
        shutil.rmtree(TOPIC_LOG_DIR)
    TOPIC_LOG_DIR.mkdir(parents=True, exist_ok=True)
    for topic in expected_topics():
        (TOPIC_LOG_DIR / f"{topic}.jsonl").write_text("", encoding="utf-8")
    counts: dict[str, int] = {topic: 0 for topic in expected_topics()}
    for event in events:
        with (TOPIC_LOG_DIR / f"{event.topic}.jsonl").open("a", encoding="utf-8") as fh:
            fh.write(json.dumps({"key": event.key, **event.value}, ensure_ascii=False) + "\n")
        counts[event.topic] = counts.get(event.topic, 0) + 1
    return {
        "status": "raw_topics_written",
        "feed_mode": FEED_MODE,
        "topic_log_dir": str(TOPIC_LOG_DIR),
        "event_counts": counts,
        "raw_events_written": sum(counts.values()),
    }


def produce_realtime_streaming_replay(*, reset: bool = True) -> dict[str, Any]:
    return write_events(build_realtime_streaming_replay_events(), reset=reset)
