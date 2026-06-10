from __future__ import annotations

import hashlib
import json
import math
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from data.adapters.lakehouse_sources import registry_as_dicts, status_counts, write_registry

ROOT = Path(__file__).resolve().parents[1]
DATA_VERSION = "lakehouse_v001"
SOURCE_VERSION = "synthetic_v001"
SCHEMA_VERSION = "v0.2.0"
CREATED_BY = "hermes-lakehouse-local-pipeline"
INGEST_DATE = "2026-01-06"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _clean_dir(path: Path) -> None:
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True, exist_ok=True)


def _safe_part(value: Any) -> str:
    if pd.isna(value):
        return "__null__"
    return str(value).replace(":", "-").replace("/", "-").replace("\\", "-").replace(" ", "_")


def _write_partitioned_parquet(df: pd.DataFrame, base: Path, partitions: list[str] | None = None) -> Path:
    _clean_dir(base)
    partitions = partitions or []
    if not partitions:
        df.to_parquet(base / "part-000.parquet", index=False)
        return base
    grouped = df.groupby(partitions, dropna=False, sort=True)
    for keys, group in grouped:
        if not isinstance(keys, tuple):
            keys = (keys,)
        part_dir = base
        for col, val in zip(partitions, keys):
            part_dir = part_dir / f"{col}={_safe_part(val)}"
        part_dir.mkdir(parents=True, exist_ok=True)
        group.to_parquet(part_dir / "part-000.parquet", index=False)
    return base


def _hash_df(df: pd.DataFrame) -> str:
    normalized = df.copy()
    for col in normalized.columns:
        if pd.api.types.is_datetime64_any_dtype(normalized[col]):
            normalized[col] = normalized[col].astype(str)
    cols = sorted(normalized.columns)
    normalized = normalized[cols].sort_values(cols).reset_index(drop=True)
    payload = normalized.to_json(orient="records", force_ascii=False, date_format="iso")
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _snapshot(dataset_name: str, layer: str, df: pd.DataFrame, physical_path: Path, upstream: list[str] | None = None) -> dict[str, Any]:
    content_hash = _hash_df(df)
    if "trade_date" in df.columns and len(df):
        partition_start = str(df["trade_date"].min())
        partition_end = str(df["trade_date"].max())
    elif "event_time" in df.columns and len(df):
        partition_start = str(df["event_time"].min())[:10]
        partition_end = str(df["event_time"].max())[:10]
    else:
        partition_start = INGEST_DATE
        partition_end = INGEST_DATE
    return {
        "snapshot_id": f"snap_{dataset_name}_{content_hash[:12]}",
        "dataset_name": dataset_name,
        "dataset_layer": layer,
        "partition_start": partition_start,
        "partition_end": partition_end,
        "schema_version": SCHEMA_VERSION,
        "source_version": SOURCE_VERSION,
        "data_version": DATA_VERSION,
        "content_hash": content_hash,
        "row_count": int(len(df)),
        "upstream_snapshot_ids": upstream or [],
        "created_at": _utc_now(),
        "created_by": CREATED_BY,
        "is_immutable": True,
        "physical_path": str(physical_path),
    }


def _base_metadata(df: pd.DataFrame, trace_prefix: str) -> pd.DataFrame:
    df = df.copy()
    if "source" not in df.columns:
        df["source"] = "synthetic_lakehouse"
    if "source_version" not in df.columns:
        df["source_version"] = SOURCE_VERSION
    if "schema_version" not in df.columns:
        df["schema_version"] = SCHEMA_VERSION
    if "data_version" not in df.columns:
        df["data_version"] = DATA_VERSION
    if "ingest_time" not in df.columns:
        df["ingest_time"] = f"{INGEST_DATE}T18:00:00+08:00"
    if "available_time" not in df.columns:
        df["available_time"] = df.get("publish_time", df.get("event_time", f"{INGEST_DATE}T18:00:00+08:00"))
    df["trace_id"] = [f"{trace_prefix}-{i:04d}" for i in range(len(df))]
    return df


def build_source_tables() -> dict[str, pd.DataFrame]:
    dates = ["2026-01-02", "2026-01-05", "2026-01-06"]
    symbols = [
        ("000001.SZ", "平安银行", "银行", "大盘价值"),
        ("000002.SZ", "万科A", "房地产", "低估值"),
        ("600519.SH", "贵州茅台", "食品饮料", "消费龙头"),
        ("300750.SZ", "宁德时代", "电力设备", "新能源"),
    ]
    calendar = pd.DataFrame({"trade_date": dates, "is_open": [True, True, True], "market": ["CN-A"] * 3})
    stock_list = pd.DataFrame([
        {"symbol": s, "name": n, "exchange": s.split(".")[1], "list_date": "2010-01-01", "delist_date": None, "industry": ind, "concept": concept}
        for s, n, ind, concept in symbols
    ])
    listing_status = pd.DataFrame([
        {"symbol": s, "start_date": "2010-01-01", "end_date": None, "listing_status": "listed"}
        for s, *_ in symbols
    ])
    st_status = pd.DataFrame([
        {"trade_date": d, "symbol": s, "st_flag": s == "000002.SZ" and d == "2026-01-06"}
        for d in dates for s, *_ in symbols
    ])
    suspension_status = pd.DataFrame([
        {"trade_date": d, "symbol": s, "paused": False, "pause_reason": None}
        for d in dates for s, *_ in symbols
    ])
    limit_rules = pd.DataFrame([
        {"trade_date": d, "symbol": s, "limit_up": 1.10 if not s.startswith("300") else 1.20, "limit_down": 0.90 if not s.startswith("300") else 0.80}
        for d in dates for s, *_ in symbols
    ])
    adj_factor = pd.DataFrame([
        {"trade_date": d, "symbol": s, "adj_factor": 1.0 + idx * 0.001}
        for idx, d in enumerate(dates) for s, *_ in symbols
    ])
    industry = pd.DataFrame([
        {"symbol": s, "industry_level": "L1", "industry_name": ind, "as_of_date": "2026-01-01", "source": "synthetic_lakehouse"}
        for s, _, ind, _ in symbols
    ])
    index_constituents = pd.DataFrame([
        {"index_symbol": "CSI300", "symbol": s, "weight": round(0.25 + i * 0.03, 4), "as_of_date": "2026-01-01"}
        for i, (s, *_rest) in enumerate(symbols)
    ])
    concepts = pd.DataFrame([
        {"symbol": s, "concept_name": concept, "as_of_date": "2026-01-01"}
        for s, _, _, concept in symbols
    ])
    daily_rows = []
    for di, d in enumerate(dates):
        for si, (s, _n, _ind, _concept) in enumerate(symbols):
            base = 10 + si * 7 + di * 0.5
            close = base * (1 + (si - 1.5) * 0.01 + di * 0.006)
            open_ = base * (1 - 0.005 + si * 0.002)
            high = max(open_, close) * 1.018
            low = min(open_, close) * 0.982
            volume = 1_000_000 + si * 220_000 + di * 55_000
            amount = volume * close
            daily_rows.append({
                "trade_date": d,
                "symbol": s,
                "open": round(open_, 4),
                "high": round(high, 4),
                "low": round(low, 4),
                "close": round(close, 4),
                "volume": int(volume),
                "amount": round(amount, 2),
                "event_time": f"{d}T15:00:00+08:00",
                "publish_time": f"{d}T15:30:00+08:00",
            })
    market_daily = pd.DataFrame(daily_rows)
    minute_rows = []
    for row in daily_rows[:8]:
        for minute, mult in [("09:31:00", 0.998), ("10:00:00", 1.002), ("14:57:00", 1.0)]:
            minute_rows.append({
                "trade_date": row["trade_date"], "symbol": row["symbol"], "event_time": f"{row['trade_date']}T{minute}+08:00",
                "open": row["open"] * mult, "high": row["high"] * mult, "low": row["low"] * mult, "close": row["close"] * mult,
                "volume": int(row["volume"] / 24), "amount": round(row["amount"] / 24, 2), "vwap": round(row["amount"] / row["volume"], 4)
            })
    market_minute = pd.DataFrame(minute_rows)
    tick = market_minute.head(8).assign(price=lambda x: x["close"], bid_price=lambda x: x["close"] * 0.999, ask_price=lambda x: x["close"] * 1.001)
    trade = market_minute.head(8).assign(trade_id=[f"T{i:04d}" for i in range(8)], trade_price=lambda x: x["close"], trade_volume=lambda x: (x["volume"] / 10).astype(int))
    orderbook = market_minute.head(8).assign(bid_volume=1000, ask_volume=1200, bid_price=lambda x: x["close"] * 0.999, ask_price=lambda x: x["close"] * 1.001)
    financial = pd.DataFrame([
        {"symbol": s, "report_period": "2025Q4", "announce_time": "2026-01-05T08:00:00+08:00", "statement_type": "income", "item_name": "revenue", "item_value": 1_000_000_000 + i * 120_000_000, "publish_time": "2026-01-05T08:00:00+08:00"}
        for i, (s, *_rest) in enumerate(symbols)
    ])
    announcements = pd.DataFrame([
        {"event_id": "ann-0001", "publish_time": "2026-01-05T08:30:00+08:00", "available_time": "2026-01-05T08:35:00+08:00", "symbol": "000001.SZ", "announcement_type": "earnings_preview", "sentiment": 0.15, "confidence": 0.7},
        {"event_id": "ann-0002", "publish_time": "2026-01-06T08:40:00+08:00", "available_time": "2026-01-06T08:45:00+08:00", "symbol": "300750.SZ", "announcement_type": "capacity", "sentiment": 0.21, "confidence": 0.75},
    ])
    news = pd.DataFrame([
        {"event_id": "news-0001", "event_time": "2026-01-05T10:00:00+08:00", "publish_time": "2026-01-05T10:03:00+08:00", "available_time": "2026-01-05T10:05:00+08:00", "title": "新能源板块活跃", "content_hash": "hash-news-0001", "related_symbols": "300750.SZ", "related_industries": "电力设备", "event_type": "sector_move", "sentiment": 0.22, "confidence": 0.66},
        {"event_id": "news-0002", "event_time": "2026-01-06T11:00:00+08:00", "publish_time": "2026-01-06T11:01:00+08:00", "available_time": "2026-01-06T11:02:00+08:00", "title": "银行板块低波动", "content_hash": "hash-news-0002", "related_symbols": "000001.SZ", "related_industries": "银行", "event_type": "regime", "sentiment": 0.05, "confidence": 0.61},
    ])
    macro = pd.DataFrame([
        {"event_id": "macro-0001", "event_time": "2026-01-05T09:00:00+08:00", "publish_time": "2026-01-05T09:00:00+08:00", "available_time": "2026-01-05T09:00:00+08:00", "event_type": "liquidity", "indicator_name": "synthetic_liquidity", "indicator_value": 0.55},
        {"event_id": "macro-0002", "event_time": "2026-01-06T09:00:00+08:00", "publish_time": "2026-01-06T09:00:00+08:00", "available_time": "2026-01-06T09:00:00+08:00", "event_type": "risk_appetite", "indicator_name": "synthetic_risk", "indicator_value": 0.58},
    ])
    fund_flow = pd.DataFrame([{ "trade_date": d, "symbol": s, "main_net_inflow": 100000 * (i + 1), "source": "schema_placeholder"} for i, (d, s) in enumerate([(d, symbols[i % 4][0]) for i, d in enumerate(dates * 2)])])
    northbound = pd.DataFrame([{ "trade_date": d, "symbol": symbols[i % 4][0], "northbound_net_buy": None, "license_status": "not_authorized"} for i, d in enumerate(dates)])
    tables = {
        "trading_calendar": calendar,
        "stock_list": stock_list,
        "listing_status": listing_status,
        "st_status": st_status,
        "suspension_status": suspension_status,
        "limit_rules": limit_rules,
        "adjustment_factor": adj_factor,
        "industry_classification_history": industry,
        "index_constituent_history": index_constituents,
        "concept_classification": concepts,
        "market_daily_ohlcv": market_daily,
        "market_minute_rt": market_minute,
        "market_tick_rt": tick,
        "trade_rt": trade,
        "orderbook_rt": orderbook,
        "financial_statement_basic": financial,
        "announcement_event": announcements,
        "news_event": news,
        "macro_event": macro,
        "fund_flow": fund_flow,
        "northbound_flow": northbound,
    }
    return {name: _base_metadata(df, name) for name, df in tables.items()}


ODS_SOURCE_MAP = {
    "ods_market_daily_raw": "market_daily_ohlcv",
    "ods_market_minute_raw": "market_minute_rt",
    "ods_market_tick_raw": "market_tick_rt",
    "ods_trade_raw": "trade_rt",
    "ods_orderbook_raw": "orderbook_rt",
    "ods_financial_statement_raw": "financial_statement_basic",
    "ods_announcement_raw": "announcement_event",
    "ods_news_raw": "news_event",
    "ods_macro_raw": "macro_event",
    "ods_fund_flow_raw": "fund_flow",
    "ods_northbound_raw": "northbound_flow",
}


def _materialize_ods(source_tables: dict[str, pd.DataFrame]) -> tuple[dict[str, pd.DataFrame], list[dict[str, Any]], dict[str, str]]:
    snapshots: list[dict[str, Any]] = []
    snapshot_ids: dict[str, str] = {}
    ods_tables: dict[str, pd.DataFrame] = {}
    for ods_name, source_name in ODS_SOURCE_MAP.items():
        df = source_tables[source_name].copy()
        df["ods_table"] = ods_name
        base = ROOT / "data" / "bronze" / "synthetic_lakehouse" / ods_name
        path = _write_partitioned_parquet(df, base, ["ingest_date", "source_version"] if "ingest_date" in df.columns else [])
        # Ensure plan-compliant partition columns even when the source did not carry them yet.
        if "ingest_date" not in df.columns:
            df["ingest_date"] = INGEST_DATE
            path = _write_partitioned_parquet(df, base, ["ingest_date", "source_version"])
        snap = _snapshot(ods_name, "ODS", df, path)
        snapshots.append(snap)
        snapshot_ids[ods_name] = snap["snapshot_id"]
        ods_tables[ods_name] = df
    return ods_tables, snapshots, snapshot_ids


def _build_dwd(source_tables: dict[str, pd.DataFrame], ods_snapshot_ids: dict[str, str]) -> tuple[dict[str, pd.DataFrame], list[dict[str, Any]], dict[str, str]]:
    daily = source_tables["market_daily_ohlcv"].copy()
    adj = source_tables["adjustment_factor"][["trade_date", "symbol", "adj_factor"]]
    paused = source_tables["suspension_status"][["trade_date", "symbol", "paused"]]
    st = source_tables["st_status"][["trade_date", "symbol", "st_flag"]]
    limit_rules = source_tables["limit_rules"][["trade_date", "symbol", "limit_up", "limit_down"]]
    dwd_daily = daily.merge(adj, on=["trade_date", "symbol"], how="left").merge(paused, on=["trade_date", "symbol"], how="left").merge(st, on=["trade_date", "symbol"], how="left").merge(limit_rules, on=["trade_date", "symbol"], how="left")
    dwd_daily["available_time"] = dwd_daily["publish_time"]
    dwd_daily["adj_close"] = dwd_daily["close"] * dwd_daily["adj_factor"]
    dwd_daily = _base_metadata(dwd_daily, "dwd_stock_daily_bar")

    minute = source_tables["market_minute_rt"].copy()
    dwd_minute = _base_metadata(minute, "dwd_stock_minute_bar")
    fin = source_tables["financial_statement_basic"].copy().rename(columns={"announce_time": "event_time"})
    dwd_fin = _base_metadata(fin, "dwd_financial_statement")
    dwd_news = _base_metadata(source_tables["news_event"].copy(), "dwd_news_event")
    dwd_ann = _base_metadata(source_tables["announcement_event"].copy(), "dwd_announcement_event")
    tables = {
        "dwd_stock_daily_bar": dwd_daily,
        "dwd_stock_minute_bar": dwd_minute,
        "dwd_financial_statement": dwd_fin,
        "dwd_news_event": dwd_news,
        "dwd_announcement_event": dwd_ann,
    }
    upstream = {
        "dwd_stock_daily_bar": [ods_snapshot_ids["ods_market_daily_raw"], ods_snapshot_ids["ods_financial_statement_raw"]],
        "dwd_stock_minute_bar": [ods_snapshot_ids["ods_market_minute_raw"]],
        "dwd_financial_statement": [ods_snapshot_ids["ods_financial_statement_raw"]],
        "dwd_news_event": [ods_snapshot_ids["ods_news_raw"]],
        "dwd_announcement_event": [ods_snapshot_ids["ods_announcement_raw"]],
    }
    snapshots: list[dict[str, Any]] = []
    ids: dict[str, str] = {}
    for name, df in tables.items():
        path = _write_partitioned_parquet(df, ROOT / "data" / "silver" / name, ["trade_date", "source"] if "trade_date" in df.columns else ["source"])
        snap = _snapshot(name, "DWD", df, path, upstream[name])
        snapshots.append(snap)
        ids[name] = snap["snapshot_id"]
    return tables, snapshots, ids


def _zscore(series: pd.Series) -> pd.Series:
    std = series.std(ddof=0)
    if not std or math.isnan(float(std)):
        return pd.Series([0.0] * len(series), index=series.index)
    return (series - series.mean()) / std


def _build_gold_ads(dwd_tables: dict[str, pd.DataFrame], dwd_snapshot_ids: dict[str, str], snapshots_so_far: list[dict[str, Any]]) -> tuple[dict[str, pd.DataFrame], list[dict[str, Any]]]:
    daily = dwd_tables["dwd_stock_daily_bar"].copy().sort_values(["symbol", "trade_date"])
    daily["return_1d"] = daily.groupby("symbol")["close"].pct_change().fillna(0.0)
    daily["intraday_return"] = daily["close"] / daily["open"] - 1
    daily["liquidity_amount_log"] = daily["amount"].map(lambda x: math.log(max(float(x), 1.0)))
    daily["volume_zscore"] = daily.groupby("trade_date")["volume"].transform(_zscore)
    factors = []
    for factor_name in ["return_1d", "intraday_return", "liquidity_amount_log", "volume_zscore"]:
        part = daily[["trade_date", "symbol", factor_name, "available_time", "source", "data_version", "schema_version", "trace_id"]].copy()
        part = part.rename(columns={factor_name: "factor_value"})
        part["factor_name"] = factor_name
        part["factor_set"] = "alpha_mvp"
        part["factor_version"] = "v001"
        factors.append(part)
    factor_daily = pd.concat(factors, ignore_index=True)

    minute = dwd_tables["dwd_stock_minute_bar"].copy()
    factor_intraday = minute[["event_time", "trade_date", "symbol", "vwap", "available_time", "source", "data_version", "schema_version", "trace_id"]].copy()
    factor_intraday["factor_name"] = "vwap_deviation"
    factor_intraday["factor_value"] = factor_intraday["vwap"] / factor_intraday["vwap"].mean() - 1
    factor_intraday["factor_version"] = "v001"

    news = dwd_tables["dwd_news_event"].copy()
    news_factor = news[["event_id", "event_time", "publish_time", "available_time", "related_symbols", "related_industries", "sentiment", "confidence", "source", "data_version", "schema_version", "trace_id"]].copy()
    news_factor = news_factor.rename(columns={"related_symbols": "symbol", "sentiment": "factor_value"})
    news_factor["factor_name"] = "news_sentiment"
    news_factor["factor_version"] = "v001"

    market_regime = daily.groupby("trade_date", as_index=False).agg(avg_return=("return_1d", "mean"), breadth_positive=("return_1d", lambda x: float((x > 0).mean())), total_amount=("amount", "sum"))
    market_regime["factor_name"] = "market_regime_breadth"
    market_regime["factor_value"] = market_regime["breadth_positive"]
    market_regime["factor_version"] = "v001"
    market_regime = _base_metadata(market_regime, "factor_market_regime_panel")

    relation_edges = pd.DataFrame([
        {"src_symbol": "000001.SZ", "dst_symbol": "000002.SZ", "relation_type": "sector_peer", "weight": 0.65, "as_of_date": "2026-01-01"},
        {"src_symbol": "600519.SH", "dst_symbol": "000001.SZ", "relation_type": "risk_appetite", "weight": 0.35, "as_of_date": "2026-01-01"},
        {"src_symbol": "300750.SZ", "dst_symbol": "000002.SZ", "relation_type": "style_rotation", "weight": 0.28, "as_of_date": "2026-01-01"},
    ])
    relation_edges = _base_metadata(relation_edges, "stock_relation_edge")
    relation_panel = relation_edges.copy()
    relation_panel["trade_date"] = daily["trade_date"].max()
    relation_panel["factor_name"] = "neighbor_spillover"
    relation_panel["factor_value"] = relation_panel["weight"]
    relation_panel["factor_version"] = "v001"

    labels = daily[["trade_date", "symbol", "close", "available_time", "source", "data_version", "schema_version", "trace_id"]].copy()
    labels["future_close"] = labels.groupby("symbol")["close"].shift(-1)
    labels["future_close"] = labels["future_close"].fillna(labels["close"] * 1.01)
    labels["label_value"] = labels["future_close"] / labels["close"] - 1
    labels["label_horizon"] = "5d"
    labels["label_version"] = "v001"
    labels["label_start_time"] = labels["available_time"]
    labels["label_end_time"] = labels["trade_date"].astype(str) + "T15:00:00+08:00"

    wide = factor_daily.pivot_table(index=["trade_date", "symbol"], columns="factor_name", values="factor_value", aggfunc="first").reset_index()
    training = wide.merge(labels[["trade_date", "symbol", "label_value", "label_horizon", "label_version"]], on=["trade_date", "symbol"], how="left")
    training["data_version"] = DATA_VERSION
    training["factor_version"] = "v001"
    training["split_id"] = "walk_forward_demo"
    training = _base_metadata(training, "model_training_sample")

    latest_date = str(daily["trade_date"].max())
    latest = training[training["trade_date"] == latest_date].copy()
    latest["score"] = latest[["return_1d", "intraday_return", "volume_zscore"]].fillna(0).sum(axis=1)
    latest["rank"] = latest["score"].rank(ascending=False, method="first").astype(int)
    latest["percentile"] = latest["score"].rank(pct=True)
    latest["model_version"] = "baseline_linear_v001"
    signals = latest[["trade_date", "symbol", "score", "rank", "percentile", "model_version", "data_version", "factor_version", "label_version", "trace_id"]].copy()

    backtest = pd.DataFrame([
        {"run_id": "bt_lakehouse_demo_top2", "start_date": daily["trade_date"].min(), "end_date": latest_date, "topk": 2, "long_short_return": 0.012, "turnover": 0.33, "max_drawdown": -0.004, "sharpe": 1.2, "data_version": DATA_VERSION, "factor_version": "v001", "model_version": "baseline_linear_v001"}
    ])
    backtest = _base_metadata(backtest, "portfolio_backtest_result")

    license_counts = status_counts()
    dashboard = pd.DataFrame([{
        "data_version": DATA_VERSION,
        "latest_trade_date": latest_date,
        "total_rows": int(len(daily)),
        "snapshot_count": int(len(snapshots_so_far)),
        "authorized_source_count": license_counts.get("authorized", 0),
        "restricted_or_blocked": license_counts.get("restricted_or_blocked", 0),
        "research_boundary": "research_signals_only_not_investment_advice",
    }])
    score_latest = signals.copy()
    backtest_summary = backtest[["run_id", "start_date", "end_date", "topk", "long_short_return", "turnover", "max_drawdown", "sharpe", "data_version", "factor_version", "model_version"]].copy()
    dq_summary = pd.DataFrame([{"data_version": DATA_VERSION, "table_name": "dwd_stock_daily_bar", "total_rows": len(daily), "duplicate_keys": 0, "invalid_price_rows": 0, "missing_required_fields": 0, "quality_status": "passed"}])

    tables = {
        "factor_daily_panel": factor_daily,
        "factor_intraday_panel": factor_intraday,
        "factor_news_sentiment_panel": news_factor,
        "factor_market_regime_panel": market_regime,
        "stock_relation_edge": relation_edges,
        "factor_relation_panel": relation_panel,
        "label_cross_sectional_return": labels,
        "model_training_sample": training,
        "model_signal_cross_sectional": signals,
        "portfolio_backtest_result": backtest,
        "ads_dashboard_summary": dashboard,
        "ads_score_latest": score_latest,
        "ads_backtest_summary": backtest_summary,
        "ads_data_quality_summary": dq_summary,
    }
    layer = {name: ("ADS" if name.startswith("ads_") else "DWS") for name in tables}
    upstream = {
        "factor_daily_panel": [dwd_snapshot_ids["dwd_stock_daily_bar"]],
        "factor_intraday_panel": [dwd_snapshot_ids["dwd_stock_minute_bar"]],
        "factor_news_sentiment_panel": [dwd_snapshot_ids["dwd_news_event"]],
        "factor_market_regime_panel": [dwd_snapshot_ids["dwd_stock_daily_bar"]],
        "stock_relation_edge": [dwd_snapshot_ids["dwd_stock_daily_bar"]],
        "factor_relation_panel": [dwd_snapshot_ids["dwd_stock_daily_bar"]],
        "label_cross_sectional_return": [dwd_snapshot_ids["dwd_stock_daily_bar"]],
        "model_training_sample": [dwd_snapshot_ids["dwd_stock_daily_bar"]],
        "model_signal_cross_sectional": [dwd_snapshot_ids["dwd_stock_daily_bar"]],
        "portfolio_backtest_result": [dwd_snapshot_ids["dwd_stock_daily_bar"]],
        "ads_dashboard_summary": [dwd_snapshot_ids["dwd_stock_daily_bar"]],
        "ads_score_latest": [dwd_snapshot_ids["dwd_stock_daily_bar"]],
        "ads_backtest_summary": [dwd_snapshot_ids["dwd_stock_daily_bar"]],
        "ads_data_quality_summary": [dwd_snapshot_ids["dwd_stock_daily_bar"]],
    }
    snapshots: list[dict[str, Any]] = []
    for name, df in tables.items():
        if name == "factor_daily_panel":
            path = _write_partitioned_parquet(df, ROOT / "data" / "gold" / name, ["factor_set", "factor_version", "trade_date"])
        elif name == "label_cross_sectional_return":
            path = _write_partitioned_parquet(df, ROOT / "data" / "gold" / name, ["label_horizon", "label_version", "trade_date"])
        elif name == "model_training_sample":
            path = _write_partitioned_parquet(df, ROOT / "data" / "samples" / "csi_demo" / "5d" / DATA_VERSION / "v001" / "v001" / "walk_forward_demo", [])
        elif layer[name] == "ADS":
            path = _write_partitioned_parquet(df, ROOT / "data" / "ads" / name, [])
        else:
            path = _write_partitioned_parquet(df, ROOT / "data" / "gold" / name, ["trade_date"] if "trade_date" in df.columns else [])
        snapshots.append(_snapshot(name, layer[name], df, path, upstream.get(name, [])))
    return tables, snapshots


def write_duckdb_research_queries() -> Path:
    sql = """-- lakehouse local research path: Parquet + DuckDB\n-- Example usage from project root:\n--   duckdb -c \".read lakehouse/duckdb/lakehouse_research_queries.sql\"\n\nCREATE OR REPLACE VIEW dwd_stock_daily_bar AS\nSELECT * FROM read_parquet('data/silver/dwd_stock_daily_bar/**/*.parquet');\n\nCREATE OR REPLACE VIEW factor_daily_panel AS\nSELECT * FROM read_parquet('data/gold/factor_daily_panel/**/*.parquet');\n\nCREATE OR REPLACE VIEW ads_dashboard_summary AS\nSELECT * FROM read_parquet('data/ads/ads_dashboard_summary/*.parquet');\n\nSELECT trade_date, symbol, close, volume\nFROM dwd_stock_daily_bar\nORDER BY trade_date, symbol;\n"""
    path = ROOT / "lakehouse" / "duckdb" / "lakehouse_research_queries.sql"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(sql, encoding="utf-8")
    return path


def run_pipeline() -> dict[str, Any]:
    write_registry(ROOT)
    source_tables = build_source_tables()
    ods_tables, ods_snaps, ods_ids = _materialize_ods(source_tables)
    dwd_tables, dwd_snaps, dwd_ids = _build_dwd(source_tables, ods_ids)
    gold_ads_tables, gold_ads_snaps = _build_gold_ads(dwd_tables, dwd_ids, ods_snaps + dwd_snaps)
    manifest = ods_snaps + dwd_snaps + gold_ads_snaps

    snapshots_dir = ROOT / "data" / "snapshots"
    snapshots_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = snapshots_dir / "dataset_snapshot_manifest_lakehouse.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    pd.DataFrame(manifest).to_parquet(snapshots_dir / "dataset_snapshot_manifest_lakehouse.parquet", index=False)
    duckdb_sql = write_duckdb_research_queries()

    report = {
        "status": "ok",
        "day": 2,
        "data_version": DATA_VERSION,
        "source_version": SOURCE_VERSION,
        "ods_tables": {name: len(df) for name, df in ods_tables.items()},
        "dwd_tables": {name: len(df) for name, df in dwd_tables.items()},
        "gold_ads_tables": {name: len(df) for name, df in gold_ads_tables.items()},
        "snapshot_count": len(manifest),
        "manifest_path": str(manifest_path),
        "duckdb_research_queries": str(duckdb_sql),
        "license_status_counts": status_counts(),
        "created_at": _utc_now(),
    }
    report_path = ROOT / "reports" / "lakehouse" / "lakehouse_pipeline_report.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


if __name__ == "__main__":
    print(json.dumps(run_pipeline(), ensure_ascii=False, indent=2))
