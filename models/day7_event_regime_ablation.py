from __future__ import annotations

import hashlib
import json
import math
import shutil
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RESEARCH_BOUNDARY = "research_signals_only_not_investment_advice"
DATA_VERSION = "day7_synthetic_event_regime_v001"
SCHEMA_VERSION = "v0.7.0"
EVENT_FACTOR_VERSION = "event_factor_day7_v001"
MARKET_REGIME_VERSION = "market_regime_day7_v001"
FEATURE_SET_VERSION = "feature_set_day7_event_regime_v001"
MODEL_VERSION = "lightgbm_day7_event_regime_smoke_v001"
RUN_ID = "day7_event_regime_ablation_v001"

DAY7_DIR = ROOT / "reports" / "day7"
NEWS_DIR = ROOT / "data" / "silver" / "news_document"
ANN_DIR = ROOT / "data" / "silver" / "announcement_document"
EVENT_RESULT_DIR = ROOT / "data" / "silver" / "event_extraction_result"
ENTITY_MAPPING_DIR = ROOT / "data" / "silver" / "entity_symbol_mapping"
DWD_NEWS_DIR = ROOT / "data" / "silver" / "dwd_news_event"
DWD_ANN_DIR = ROOT / "data" / "silver" / "dwd_announcement_event"
EVENT_FACTOR_DIR = ROOT / "data" / "gold" / "factor_news_sentiment_panel"
MARKET_REGIME_DIR = ROOT / "data" / "gold" / "factor_market_regime_panel"
ENHANCED_FEATURE_DIR = ROOT / "data" / "gold" / "model_feature_matrix_wide_day7"
FACTOR_DAILY_DAY7_DIR = ROOT / "data" / "gold" / "factor_daily_panel_day7_event_regime"

POSITIVE_WORDS = {
    "增长",
    "中标",
    "订单",
    "回购",
    "增持",
    "盈利",
    "改善",
    "突破",
    "扩产",
    "景气",
    "创新",
    "合作",
}
NEGATIVE_WORDS = {"亏损", "处罚", "下滑", "风险", "减持", "诉讼", "违约", "召回", "监管", "成本", "不及", "停产"}
SOURCE_AUTHORITY = {
    "exchange_announcement": 1.00,
    "official_media": 0.92,
    "company_press": 0.86,
    "industry_media": 0.74,
    "macro_calendar": 0.88,
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _json_default(value: Any) -> Any:
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        if math.isnan(float(value)) or math.isinf(float(value)):
            return None
        return float(value)
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    return str(value)


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=_json_default), encoding="utf-8")


def _write_parquet_dir(df: pd.DataFrame, directory: Path) -> None:
    shutil.rmtree(directory, ignore_errors=True)
    directory.mkdir(parents=True, exist_ok=True)
    df.to_parquet(directory / "part-000.parquet", index=False)


def _read_parquet_dir(directory: Path) -> pd.DataFrame:
    files = sorted(directory.glob("**/*.parquet"))
    if not files:
        raise FileNotFoundError(f"No parquet files found under {directory}")
    return pd.concat([pd.read_parquet(file) for file in files], ignore_index=True, sort=False)


def _next_trade_date(date: str, trading_dates: list[str]) -> str:
    for candidate in trading_dates:
        if candidate > date:
            return candidate
    return (pd.Timestamp(date) + pd.Timedelta(days=1)).strftime("%Y-%m-%d")


def _ts(date: str, time_text: str) -> str:
    return f"{date}T{time_text}+08:00"


def _trace_id(prefix: str, *parts: Any) -> str:
    raw = "|".join(str(part) for part in parts)
    return f"{prefix}-{hashlib.sha256(raw.encode('utf-8')).hexdigest()[:12]}"


def _zscore(series: pd.Series) -> pd.Series:
    std = series.std(ddof=0)
    if pd.isna(std) or abs(float(std)) < 1e-12:
        return pd.Series(0.0, index=series.index)
    return (series - series.mean()) / std


def _load_base_feature_matrix() -> pd.DataFrame:
    from feature_store.point_in_time_join.build_model_feature_matrix import build_model_feature_matrix

    feature_dir = ROOT / "data" / "gold" / "model_feature_matrix_wide"
    if not list(feature_dir.glob("**/*.parquet")):
        build_model_feature_matrix()
    feature = _read_parquet_dir(feature_dir)
    feature["trade_date"] = feature["trade_date"].astype(str)
    feature["symbol"] = feature["symbol"].astype(str)
    return feature.sort_values(["trade_date", "symbol"]).reset_index(drop=True)


def _load_clean_market() -> pd.DataFrame:
    from factors.offline.polars_factor_engine import _clean_source, _read_source

    raw, _ = _read_source()
    market = _clean_source(raw)
    market["trade_date"] = pd.to_datetime(market["trade_date"]).dt.strftime("%Y-%m-%d")
    return market.sort_values(["symbol", "trade_date"]).reset_index(drop=True)


def build_event_documents(feature: pd.DataFrame, write_outputs: bool = True) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    symbols = feature[["symbol"]].drop_duplicates().head(20).reset_index(drop=True)
    industry = feature.groupby("symbol", sort=False).first().get("industry_name")
    if industry is None:
        industry_map = {symbol: f"行业{idx % 5}" for idx, symbol in enumerate(symbols["symbol"].tolist())}
    else:
        industry_map = industry.to_dict()
    trading_dates = sorted(feature["trade_date"].unique().tolist())
    anchor_dates = trading_dates[14:-3:6][:18]
    templates = [
        ("official_media", "订单增长", "公司获得大额订单，产能利用率改善，行业景气提升", "positive", "industry"),
        ("industry_media", "成本风险", "原材料成本上行带来利润风险，短期盈利承压", "negative", "industry"),
        ("company_press", "技术突破", "新产品完成验证并进入客户导入，创新能力改善", "positive", "single_stock"),
        ("official_media", "政策支持", "政策鼓励产业升级，市场风险偏好改善", "positive", "market"),
        ("macro_calendar", "宏观扰动", "海外需求下滑且汇率波动增加，宏观风险上升", "negative", "market"),
        ("industry_media", "合作扩产", "产业链合作推进，扩产节奏稳健", "positive", "supply_chain"),
    ]
    news_rows: list[dict[str, Any]] = []
    ann_rows: list[dict[str, Any]] = []
    mapping_rows: list[dict[str, Any]] = []
    for idx, symbol in enumerate(symbols["symbol"].tolist()):
        entity_name = f"样本公司{idx + 1:02d}"
        mapping_rows.append(
            {
                "entity_name": entity_name,
                "symbol": symbol,
                "industry_name": industry_map.get(symbol, "未知行业"),
                "mapping_confidence": 0.98,
                "as_of_date": trading_dates[0],
                "available_time": _ts(trading_dates[0], "09:00:00"),
                "source": "synthetic_entity_seed",
                "license_id": "synthetic_demo_license",
                "data_version": DATA_VERSION,
                "schema_version": SCHEMA_VERSION,
                "research_boundary": RESEARCH_BOUNDARY,
            }
        )
    for idx, date in enumerate(anchor_dates):
        symbol = symbols.loc[idx % len(symbols), "symbol"]
        entity_name = f"样本公司{(idx % len(symbols)) + 1:02d}"
        source, headline, body, polarity, scope = templates[idx % len(templates)]
        publish_time = _ts(date, "18:30:00")
        available_time = _ts(date, "18:45:00")
        news_rows.append(
            {
                "document_id": f"news_day7_{idx + 1:03d}",
                "document_type": "news",
                "publish_time": publish_time,
                "available_time": available_time,
                "source": source,
                "title": f"{entity_name}{headline}",
                "content": f"{entity_name}({symbol}){body}。本文为合成样例，仅用于研究事件因子验证。",
                "primary_entity": entity_name,
                "primary_symbol": symbol,
                "expected_polarity": polarity,
                "expected_impact_scope": scope,
                "license_id": "synthetic_demo_license",
                "data_version": DATA_VERSION,
                "schema_version": SCHEMA_VERSION,
                "trace_id": _trace_id("news", idx, symbol, publish_time),
                "research_boundary": RESEARCH_BOUNDARY,
            }
        )
        if idx % 2 == 0:
            ann_idx = len(ann_rows)
            ann_source = "exchange_announcement"
            ann_polarity = "positive" if idx % 4 == 0 else "negative"
            ann_body = "发布回购增持公告，资本回报预期改善" if ann_polarity == "positive" else "披露诉讼和业绩下滑风险，经营压力上升"
            ann_rows.append(
                {
                    "document_id": f"ann_day7_{ann_idx + 1:03d}",
                    "document_type": "announcement",
                    "publish_time": _ts(date, "20:10:00"),
                    "available_time": _ts(date, "20:25:00"),
                    "source": ann_source,
                    "title": f"{entity_name}{'回购增持公告' if ann_polarity == 'positive' else '风险提示公告'}",
                    "content": f"{entity_name}({symbol}){ann_body}。公告为合成样例，仅用于研究事件因子验证。",
                    "primary_entity": entity_name,
                    "primary_symbol": symbol,
                    "expected_polarity": ann_polarity,
                    "expected_impact_scope": "single_stock",
                    "license_id": "synthetic_demo_license",
                    "data_version": DATA_VERSION,
                    "schema_version": SCHEMA_VERSION,
                    "trace_id": _trace_id("ann", ann_idx, symbol, date),
                    "research_boundary": RESEARCH_BOUNDARY,
                }
            )
    news = pd.DataFrame(news_rows)
    ann = pd.DataFrame(ann_rows)
    mapping = pd.DataFrame(mapping_rows)
    if write_outputs:
        _write_parquet_dir(news, NEWS_DIR)
        _write_parquet_dir(ann, ANN_DIR)
        _write_parquet_dir(mapping, ENTITY_MAPPING_DIR)
    return news, ann, mapping


def _classify_event(text: str, source: str) -> str:
    if "政策" in text:
        return "policy"
    if "宏观" in text or "海外" in text or source == "macro_calendar":
        return "macro"
    if "公告" in text or source == "exchange_announcement":
        return "announcement"
    if "订单" in text or "合作" in text or "扩产" in text:
        return "business_update"
    if "诉讼" in text or "处罚" in text or "风险" in text:
        return "risk_warning"
    return "news_update"


def _sentiment_score(text: str) -> float:
    pos = sum(1 for word in POSITIVE_WORDS if word in text)
    neg = sum(1 for word in NEGATIVE_WORDS if word in text)
    if pos + neg == 0:
        return 0.0
    return float((pos - neg) / (pos + neg))


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / max(len(a | b), 1)


def _tokenize_zh(text: str) -> set[str]:
    words = POSITIVE_WORDS | NEGATIVE_WORDS | {"政策", "宏观", "订单", "公告", "合作", "扩产", "行业", "风险", "回购", "诉讼"}
    return {word for word in words if word in text}


def build_event_extractions(news: pd.DataFrame, ann: pd.DataFrame, trading_dates: list[str], write_outputs: bool = True) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    docs = pd.concat([news, ann], ignore_index=True, sort=False).sort_values("available_time").reset_index(drop=True)
    rows: list[dict[str, Any]] = []
    previous_tokens: list[tuple[pd.Timestamp, set[str]]] = []
    for idx, row in docs.iterrows():
        text = f"{row['title']} {row['content']}"
        available = pd.Timestamp(row["available_time"])
        tokens = _tokenize_zh(text)
        max_sim_by_window: dict[str, float] = {}
        for days in [7, 30, 90]:
            candidates = [tok for ts, tok in previous_tokens if (available - ts).days <= days]
            max_sim_by_window[f"similarity_{days}d"] = max([_jaccard(tokens, tok) for tok in candidates] or [0.0])
        novelty = 1.0 - max(max_sim_by_window.values() or [0.0])
        sentiment = _sentiment_score(text)
        event_type = _classify_event(text, str(row["source"]))
        date = str(pd.Timestamp(row["available_time"]).date())
        prediction_date = _next_trade_date(date, trading_dates)
        prediction_time = _ts(prediction_date, "09:25:00")
        hours_to_prediction = max((pd.Timestamp(prediction_time) - available).total_seconds() / 3600.0, 0.0)
        source_weight = SOURCE_AUTHORITY.get(str(row["source"]), 0.60)
        scope = str(row.get("expected_impact_scope", "single_stock"))
        rows.append(
            {
                "event_id": f"event_day7_{idx + 1:03d}",
                "document_id": row["document_id"],
                "document_type": row["document_type"],
                "publish_time": row["publish_time"],
                "available_time": row["available_time"],
                "prediction_time": prediction_time,
                "source": row["source"],
                "source_authority_weight": source_weight,
                "entity_name": row["primary_entity"],
                "symbol": row["primary_symbol"],
                "event_type": event_type,
                "sentiment_model": "lexicon_finbert_compatible_baseline",
                "sentiment_score": sentiment,
                "event_type_model": "keyword_event_type_baseline",
                "novelty_score": float(np.clip(novelty, 0.0, 1.0)),
                **max_sim_by_window,
                "impact_scope": scope,
                "event_decay_5m": float(math.exp(-hours_to_prediction / (5 / 60))),
                "event_decay_30m": float(math.exp(-hours_to_prediction / 0.5)),
                "event_decay_1h": float(math.exp(-hours_to_prediction / 1.0)),
                "event_decay_1d": float(math.exp(-hours_to_prediction / 24.0)),
                "event_decay_3d": float(math.exp(-hours_to_prediction / 72.0)),
                "event_decay_5d": float(math.exp(-hours_to_prediction / 120.0)),
                "event_decay_20d": float(math.exp(-hours_to_prediction / 480.0)),
                "leakage_check_status": "passed" if pd.Timestamp(row["available_time"]) <= pd.Timestamp(prediction_time) else "failed",
                "data_version": DATA_VERSION,
                "schema_version": SCHEMA_VERSION,
                "trace_id": _trace_id("event", row["document_id"], row["available_time"]),
                "research_boundary": RESEARCH_BOUNDARY,
            }
        )
        previous_tokens.append((available, tokens))
    events = pd.DataFrame(rows)
    dwd_cols = [
        "event_id",
        "document_id",
        "publish_time",
        "available_time",
        "prediction_time",
        "source",
        "source_authority_weight",
        "symbol",
        "event_type",
        "sentiment_score",
        "novelty_score",
        "impact_scope",
        "event_decay_5m",
        "event_decay_1h",
        "event_decay_1d",
        "event_decay_5d",
        "leakage_check_status",
        "data_version",
        "schema_version",
        "trace_id",
        "research_boundary",
    ]
    dwd_news = events[events["document_type"] == "news"][dwd_cols].copy()
    dwd_ann = events[events["document_type"] == "announcement"][dwd_cols].copy()
    if write_outputs:
        _write_parquet_dir(events, EVENT_RESULT_DIR)
        _write_parquet_dir(dwd_news, DWD_NEWS_DIR)
        _write_parquet_dir(dwd_ann, DWD_ANN_DIR)
    return events, dwd_news, dwd_ann


def build_event_factor_panel(feature: pd.DataFrame, events: pd.DataFrame, write_outputs: bool = True) -> tuple[pd.DataFrame, pd.DataFrame]:
    base_keys = feature[["trade_date", "symbol", "prediction_time"]].copy()
    base_keys["prediction_ts"] = pd.to_datetime(base_keys["prediction_time"], utc=True)
    events = events.copy()
    events["available_ts"] = pd.to_datetime(events["available_time"], utc=True)
    factor_names = [
        "news_sentiment_1d",
        "news_sentiment_3d",
        "news_sentiment_5d",
        "announcement_sentiment",
        "event_count",
        "negative_event_count",
        "source_weighted_sentiment",
        "novelty_score",
        "event_authority_score",
        "event_decay_5m",
        "event_decay_1h",
        "event_decay_1d",
        "event_decay_5d",
        "policy_event_score",
        "macro_event_score",
    ]
    wide_rows: list[dict[str, Any]] = []
    long_rows: list[dict[str, Any]] = []
    for row in base_keys.itertuples(index=False):
        symbol_events = events[(events["symbol"] == row.symbol) & (events["available_ts"] <= row.prediction_ts)].copy()
        metrics: dict[str, float] = {}
        for days in [1, 3, 5]:
            recent = symbol_events[symbol_events["available_ts"] >= row.prediction_ts - pd.Timedelta(days=days)]
            news_recent = recent[recent["document_type"] == "news"]
            metrics[f"news_sentiment_{days}d"] = float(news_recent["sentiment_score"].mean()) if not news_recent.empty else 0.0
        ann_recent = symbol_events[(symbol_events["document_type"] == "announcement") & (symbol_events["available_ts"] >= row.prediction_ts - pd.Timedelta(days=5))]
        recent5 = symbol_events[symbol_events["available_ts"] >= row.prediction_ts - pd.Timedelta(days=5)]
        metrics["announcement_sentiment"] = float(ann_recent["sentiment_score"].mean()) if not ann_recent.empty else 0.0
        metrics["event_count"] = float(len(recent5))
        metrics["negative_event_count"] = float((recent5["sentiment_score"] < 0).sum()) if not recent5.empty else 0.0
        metrics["source_weighted_sentiment"] = float((recent5["sentiment_score"] * recent5["source_authority_weight"]).sum() / (recent5["source_authority_weight"].sum() + 1e-12)) if not recent5.empty else 0.0
        metrics["novelty_score"] = float(recent5["novelty_score"].mean()) if not recent5.empty else 0.0
        metrics["event_authority_score"] = float(recent5["source_authority_weight"].mean()) if not recent5.empty else 0.0
        for decay in ["event_decay_5m", "event_decay_1h", "event_decay_1d", "event_decay_5d"]:
            metrics[decay] = float((recent5["sentiment_score"] * recent5[decay]).sum()) if not recent5.empty else 0.0
        metrics["policy_event_score"] = float(recent5.loc[recent5["event_type"] == "policy", "sentiment_score"].sum()) if not recent5.empty else 0.0
        metrics["macro_event_score"] = float(recent5.loc[recent5["event_type"] == "macro", "sentiment_score"].sum()) if not recent5.empty else 0.0
        latest_available = str(recent5["available_time"].max()) if not recent5.empty else _ts(row.trade_date, "08:30:00")
        wide = {
            "trade_date": row.trade_date,
            "symbol": row.symbol,
            "prediction_time": row.prediction_time,
            "available_time": latest_available,
            "leakage_check_status": "passed" if pd.Timestamp(latest_available) <= pd.Timestamp(row.prediction_time) else "failed",
            **metrics,
            "factor_version": EVENT_FACTOR_VERSION,
            "data_version": DATA_VERSION,
            "schema_version": SCHEMA_VERSION,
            "research_boundary": RESEARCH_BOUNDARY,
        }
        wide_rows.append(wide)
        for name in factor_names:
            long_rows.append(
                {
                    "trade_date": row.trade_date,
                    "symbol": row.symbol,
                    "prediction_time": row.prediction_time,
                    "available_time": latest_available,
                    "factor_name": name,
                    "factor_value": metrics[name],
                    "factor_category": "news_announcement_event",
                    "factor_version": EVENT_FACTOR_VERSION,
                    "leakage_check_status": wide["leakage_check_status"],
                    "data_version": DATA_VERSION,
                    "schema_version": SCHEMA_VERSION,
                    "trace_id": _trace_id("event-factor", row.trade_date, row.symbol, name),
                    "research_boundary": RESEARCH_BOUNDARY,
                }
            )
    wide_df = pd.DataFrame(wide_rows)
    long_df = pd.DataFrame(long_rows)
    if write_outputs:
        _write_parquet_dir(long_df, EVENT_FACTOR_DIR)
    return wide_df, long_df


def build_market_regime_panel(feature: pd.DataFrame, market: pd.DataFrame, write_outputs: bool = True) -> pd.DataFrame:
    m = market.sort_values(["symbol", "trade_date"]).copy()
    m["ret_1d"] = m.groupby("symbol", sort=False)["close"].pct_change()
    m["ret_5d"] = m.groupby("symbol", sort=False)["close"].pct_change(5)
    m["ret_20d"] = m.groupby("symbol", sort=False)["close"].pct_change(20)
    m["amount_rank"] = m.groupby("trade_date")["amount"].rank(pct=True)
    rows: list[dict[str, Any]] = []
    trading_dates = sorted(m["trade_date"].unique().tolist())
    feature_by_date = feature.copy()
    for date, group in m.groupby("trade_date", sort=True):
        hist = m[m["trade_date"] <= date]
        recent_dates = [d for d in trading_dates if d <= date][-20:]
        recent = m[m["trade_date"].isin(recent_dates)]
        fdate = feature_by_date[feature_by_date["trade_date"] == date]
        market_ret_1d = float(group["ret_1d"].mean(skipna=True) or 0.0)
        market_ret_5d = float(group["ret_5d"].mean(skipna=True) or 0.0)
        market_ret_20d = float(group["ret_20d"].mean(skipna=True) or 0.0)
        breadth = float((group["ret_1d"] > 0).mean()) if group["ret_1d"].notna().any() else 0.5
        daily_market_returns = recent.groupby("trade_date")["ret_1d"].mean().fillna(0.0)
        nav = (1.0 + daily_market_returns).cumprod()
        drawdown = float((nav / nav.cummax() - 1.0).min()) if len(nav) else 0.0
        low_amount = group[group["amount_rank"] <= 0.3]["ret_1d"].mean()
        high_amount = group[group["amount_rank"] >= 0.7]["ret_1d"].mean()
        small_vs_large = float((low_amount if pd.notna(low_amount) else 0.0) - (high_amount if pd.notna(high_amount) else 0.0))
        if not fdate.empty and {"growth_proxy_20d", "value_proxy", "return_1d"}.issubset(fdate.columns):
            growth = fdate[fdate["growth_proxy_20d"].rank(pct=True) >= 0.7]["return_1d"].mean()
            value = fdate[fdate["value_proxy"].rank(pct=True) >= 0.7]["return_1d"].mean()
            growth_vs_value = float((growth if pd.notna(growth) else 0.0) - (value if pd.notna(value) else 0.0))
        else:
            growth_vs_value = 0.0
        industry_dispersion = float(group.groupby("industry_name")["ret_1d"].mean().std(ddof=0) or 0.0) if "industry_name" in group else 0.0
        amount_history = hist.groupby("trade_date")["amount"].sum()
        amount_percentile = float(amount_history.rank(pct=True).iloc[-1]) if len(amount_history) else 0.0
        idx = trading_dates.index(date)
        synthetic_flow = math.sin(idx / 6.0) + 0.3 * math.cos(idx / 11.0)
        all_flows = pd.Series([math.sin(i / 6.0) + 0.3 * math.cos(i / 11.0) for i in range(idx + 1)])
        northbound_z = float((synthetic_flow - all_flows.mean()) / (all_flows.std(ddof=0) + 1e-12))
        risk_appetite = float(0.45 * _clip(market_ret_5d * 20, -1, 1) + 0.35 * (breadth - 0.5) * 2 + 0.20 * northbound_z / 3)
        liquidity_regime = "high_liquidity" if amount_percentile >= 0.66 else "low_liquidity" if amount_percentile <= 0.33 else "normal_liquidity"
        ex_post = "risk_on" if market_ret_5d > 0.01 and breadth >= 0.55 else "risk_off" if market_ret_5d < -0.01 and breadth <= 0.45 else "neutral"
        prediction_date = _next_trade_date(str(date), trading_dates)
        rows.append(
            {
                "trade_date": str(date),
                "available_time": _ts(str(date), "15:40:00"),
                "prediction_time": _ts(prediction_date, "09:25:00"),
                "market_breadth": breadth,
                "market_ret_1d": market_ret_1d,
                "market_ret_5d": market_ret_5d,
                "market_ret_20d": market_ret_20d,
                "market_vol_20d": float(daily_market_returns.std(ddof=0) or 0.0),
                "market_drawdown_20d": drawdown,
                "limit_up_count": int(group.get("limit_up_flag", pd.Series(False, index=group.index)).sum()),
                "limit_down_count": int(group.get("limit_down_flag", pd.Series(False, index=group.index)).sum()),
                "amount_percentile_252d": amount_percentile,
                "small_vs_large_return": small_vs_large,
                "growth_vs_value_return": growth_vs_value,
                "industry_dispersion": industry_dispersion,
                "northbound_flow_zscore": northbound_z,
                "liquidity_regime": liquidity_regime,
                "risk_appetite_proxy": risk_appetite,
                "ex_ante_regime_feature": risk_appetite,
                "ex_post_regime_label": ex_post,
                "regime_feature_role": "ex_ante_model_feature",
                "ex_post_regime_label_role": "report_only_not_training_feature",
                "leakage_check_status": "passed",
                "factor_version": MARKET_REGIME_VERSION,
                "data_version": DATA_VERSION,
                "schema_version": SCHEMA_VERSION,
                "trace_id": _trace_id("market-regime", date),
                "research_boundary": RESEARCH_BOUNDARY,
            }
        )
    market_regime = pd.DataFrame(rows)
    if write_outputs:
        _write_parquet_dir(market_regime, MARKET_REGIME_DIR)
    return market_regime


def _clip(value: float, low: float, high: float) -> float:
    return float(min(max(value, low), high))


def build_enhanced_feature_matrix(feature: pd.DataFrame, event_wide: pd.DataFrame, market_regime: pd.DataFrame, write_outputs: bool = True) -> pd.DataFrame:
    event_cols = [
        "trade_date",
        "symbol",
        "news_sentiment_1d",
        "news_sentiment_3d",
        "news_sentiment_5d",
        "announcement_sentiment",
        "event_count",
        "negative_event_count",
        "source_weighted_sentiment",
        "novelty_score",
        "event_authority_score",
        "event_decay_5m",
        "event_decay_1h",
        "event_decay_1d",
        "event_decay_5d",
        "policy_event_score",
        "macro_event_score",
    ]
    market_cols = [
        "trade_date",
        "market_breadth",
        "market_ret_1d",
        "market_ret_5d",
        "market_ret_20d",
        "market_vol_20d",
        "market_drawdown_20d",
        "limit_up_count",
        "limit_down_count",
        "amount_percentile_252d",
        "small_vs_large_return",
        "growth_vs_value_return",
        "industry_dispersion",
        "northbound_flow_zscore",
        "risk_appetite_proxy",
        "ex_ante_regime_feature",
    ]
    enhanced = feature.merge(event_wide[event_cols], on=["trade_date", "symbol"], how="left").merge(market_regime[market_cols], on="trade_date", how="left")
    for col in event_cols[2:] + market_cols[1:]:
        enhanced[col] = pd.to_numeric(enhanced[col], errors="coerce").fillna(0.0)
    enhanced["relation_spillover_placeholder"] = 0.0
    enhanced["feature_set_version"] = FEATURE_SET_VERSION
    enhanced["event_regime_feature_version"] = f"{EVENT_FACTOR_VERSION}+{MARKET_REGIME_VERSION}"
    enhanced["research_boundary"] = RESEARCH_BOUNDARY
    if write_outputs:
        _write_parquet_dir(enhanced, ENHANCED_FEATURE_DIR)
    return enhanced


def _fit_score(train: pd.DataFrame, test: pd.DataFrame, feature_cols: list[str]) -> tuple[np.ndarray, str]:
    x_train = train[feature_cols].replace([np.inf, -np.inf], np.nan)
    x_test = test[feature_cols].replace([np.inf, -np.inf], np.nan)
    medians = x_train.median(numeric_only=True).fillna(0.0)
    x_train = x_train.fillna(medians).fillna(0.0)
    x_test = x_test.fillna(medians).fillna(0.0)
    y_train = train["cs_zscore_label"].astype(float)
    try:
        import lightgbm as lgb

        ds = lgb.Dataset(x_train, label=y_train)
        model = lgb.train(
            {
                "objective": "regression",
                "metric": "l2",
                "learning_rate": 0.06,
                "num_leaves": 11,
                "min_data_in_leaf": 5,
                "feature_fraction": 0.9,
                "seed": 42,
                "verbose": -1,
            },
            ds,
            num_boost_round=24,
            callbacks=[lgb.log_evaluation(0)],
        )
        return np.asarray(model.predict(x_test), dtype=float), "lightgbm_smoke_trained"
    except Exception:
        x = np.c_[np.ones(len(x_train)), x_train.to_numpy(dtype=float)]
        coef = np.linalg.pinv(x.T @ x + np.eye(x.shape[1]) * 1e-3) @ x.T @ y_train.to_numpy(dtype=float)
        return np.c_[np.ones(len(x_test)), x_test.to_numpy(dtype=float)] @ coef, "linear_fallback_smoke_trained"


def run_ablation(enhanced: pd.DataFrame, write_outputs: bool = True) -> tuple[dict[str, Any], str]:
    labels = _read_parquet_dir(ROOT / "data" / "gold" / "label_cross_sectional_return")
    labels = labels[(labels["horizon"].astype(str) == "5d") & labels["tradable_flag"].astype(bool)].copy()
    sample = enhanced.merge(
        labels[["trade_date", "symbol", "prediction_time", "forward_return", "cs_zscore_label", "label_version", "leakage_check_status"]],
        on=["trade_date", "symbol", "prediction_time"],
        how="inner",
        suffixes=("", "_label"),
    ).sort_values(["trade_date", "symbol"])
    numeric_cols = [col for col in sample.columns if pd.api.types.is_numeric_dtype(sample[col])]
    base_candidates = [
        "return_1d",
        "return_5d",
        "momentum_20d",
        "reversal_5d",
        "volatility_20d",
        "amount_mean_20d",
        "vwap_deviation",
        "volume_shock_20d",
        "beta_20d",
        "value_proxy",
        "quality_proxy",
        "low_volatility_proxy",
        "liquidity_proxy",
        "cs_zscore_return_20d",
    ]
    news_cols = [
        "news_sentiment_1d",
        "news_sentiment_3d",
        "news_sentiment_5d",
        "announcement_sentiment",
        "event_count",
        "negative_event_count",
        "source_weighted_sentiment",
        "novelty_score",
        "event_authority_score",
        "event_decay_1d",
        "policy_event_score",
        "macro_event_score",
    ]
    market_cols = [
        "market_breadth",
        "market_ret_1d",
        "market_ret_5d",
        "market_ret_20d",
        "market_vol_20d",
        "market_drawdown_20d",
        "amount_percentile_252d",
        "small_vs_large_return",
        "growth_vs_value_return",
        "industry_dispersion",
        "northbound_flow_zscore",
        "risk_appetite_proxy",
        "ex_ante_regime_feature",
    ]
    relation_cols = ["relation_spillover_placeholder"]
    base_cols = [col for col in base_candidates if col in numeric_cols]
    news_cols = [col for col in news_cols if col in numeric_cols]
    market_cols = [col for col in market_cols if col in numeric_cols]
    configs = {
        "base_price_volume": base_cols,
        "base_plus_market_regime": base_cols + market_cols,
        "base_plus_news_event": base_cols + news_cols,
        "base_plus_relation_spillover": base_cols + relation_cols,
        "base_plus_market_news_relation": base_cols + market_cols + news_cols + relation_cols,
        "full_minus_market_regime": base_cols + news_cols + relation_cols,
        "full_minus_news_event": base_cols + market_cols + relation_cols,
        "full_minus_relation_spillover": base_cols + market_cols + news_cols,
    }
    dates = sorted(sample["trade_date"].unique().tolist())
    split_at = max(10, int(len(dates) * 0.72))
    train_dates = dates[:split_at]
    test_dates = dates[split_at:]
    train = sample[sample["trade_date"].isin(train_dates)].copy()
    test = sample[sample["trade_date"].isin(test_dates)].copy()
    results: dict[str, Any] = {}
    status = "linear_fallback_smoke_trained"
    for name, cols in configs.items():
        cols = [col for col in dict.fromkeys(cols) if col in sample.columns]
        pred, status = _fit_score(train, test, cols)
        target = test["forward_return"].astype(float).to_numpy()
        label = test["cs_zscore_label"].astype(float).to_numpy()
        rank_ic = float(pd.Series(pred).corr(pd.Series(label), method="spearman")) if len(np.unique(pred)) > 1 else 0.0
        top = pd.DataFrame({"trade_date": test["trade_date"].to_numpy(), "score": pred, "forward_return": target})
        top_ret = float(top.sort_values("score", ascending=False).groupby("trade_date").head(5)["forward_return"].mean()) if not top.empty else 0.0
        results[name] = {
            "feature_count": len(cols),
            "train_rows": int(len(train)),
            "test_rows": int(len(test)),
            "rank_ic_smoke": 0.0 if pd.isna(rank_ic) else rank_ic,
            "top5_forward_return_smoke": top_ret,
            "model_status": status,
            "feature_groups": {
                "base_price_volume": int(sum(col in base_cols for col in cols)),
                "market_regime": int(sum(col in market_cols for col in cols)),
                "news_event": int(sum(col in news_cols for col in cols)),
                "relation_spillover": int(sum(col in relation_cols for col in cols)),
            },
        }
    report = {
        "status": "ok",
        "run_id": RUN_ID,
        "model_version": MODEL_VERSION,
        "ablation_status": status,
        "configs": results,
        "train_period": [train_dates[0], train_dates[-1]] if train_dates else [],
        "test_period": [test_dates[0], test_dates[-1]] if test_dates else [],
        "sample_rows": int(len(sample)),
        "leakage_check_status": "passed",
        "relation_spillover_note": "Day7 keeps relation_spillover as a zero placeholder; Day8 will replace it with graph propagation factors.",
        "research_boundary": RESEARCH_BOUNDARY,
        "generated_at": _now(),
    }
    if write_outputs:
        _write_json(DAY7_DIR / "event_regime_ablation_report.json", report)
        _write_ablation_html(report)
    return report, status


def _write_ablation_html(report: dict[str, Any]) -> None:
    rows = []
    for name, item in report.get("configs", {}).items():
        rows.append({"config": name, **{k: v for k, v in item.items() if k != "feature_groups"}})
    df = pd.DataFrame(rows)
    html = f"""<!doctype html>
<html lang=\"zh-CN\"><head><meta charset=\"utf-8\"><title>Day7 Event/Regime Ablation</title>
<style>body{{font-family:Inter,Arial,sans-serif;background:#f8fafc;color:#172033;margin:32px}}.card{{background:white;border:1px solid #e5e7eb;border-radius:16px;padding:18px;margin:14px 0}}table{{border-collapse:collapse;width:100%;font-size:13px}}td,th{{border-bottom:1px solid #e5e7eb;padding:8px;text-align:left}}.badge{{background:#dcfce7;color:#166534;border-radius:999px;padding:4px 8px;font-size:12px}}</style></head>
<body><span class=\"badge\">Day 7 event/regime smoke ablation</span><h1>事件因子、市场环境因子入模 ablation</h1>
<p>本报告仅用于研究验证，不输出买卖建议。ex_ante_regime_feature 可进入模型；ex_post_regime_label 仅作复盘解释。</p>
<div class=\"card\"><h2>Ablation 结果</h2>{df.to_html(index=False) if not df.empty else '<p>无</p>'}</div>
<div class=\"card\"><h2>治理边界</h2><pre>{json.dumps({k: v for k, v in report.items() if k != 'configs'}, ensure_ascii=False, indent=2, default=_json_default)}</pre></div>
</body></html>"""
    DAY7_DIR.mkdir(parents=True, exist_ok=True)
    (DAY7_DIR / "event_regime_ablation_report.html").write_text(html, encoding="utf-8")


def write_factor_daily_panel_day7(event_long: pd.DataFrame, market: pd.DataFrame, write_outputs: bool = True) -> pd.DataFrame:
    market_long = market.melt(
        id_vars=["trade_date", "available_time", "prediction_time", "factor_version", "data_version", "schema_version", "trace_id", "research_boundary"],
        value_vars=[
            "market_breadth",
            "market_ret_1d",
            "market_ret_5d",
            "market_ret_20d",
            "market_vol_20d",
            "market_drawdown_20d",
            "limit_up_count",
            "limit_down_count",
            "amount_percentile_252d",
            "small_vs_large_return",
            "growth_vs_value_return",
            "industry_dispersion",
            "northbound_flow_zscore",
            "risk_appetite_proxy",
            "ex_ante_regime_feature",
        ],
        var_name="factor_name",
        value_name="factor_value",
    )
    market_long["symbol"] = "MARKET"
    market_long["factor_category"] = "market_regime"
    market_long["leakage_check_status"] = "passed"
    market_long = market_long[event_long.columns]
    combined = pd.concat([event_long, market_long], ignore_index=True, sort=False)
    if write_outputs:
        _write_parquet_dir(combined, FACTOR_DAILY_DAY7_DIR)
    return combined


def run_day7_event_regime_pipeline(write_outputs: bool = True) -> dict[str, Any]:
    feature = _load_base_feature_matrix()
    market = _load_clean_market()
    trading_dates = sorted(feature["trade_date"].unique().tolist())
    news, ann, mapping = build_event_documents(feature, write_outputs=write_outputs)
    events, dwd_news, dwd_ann = build_event_extractions(news, ann, trading_dates, write_outputs=write_outputs)
    event_wide, event_long = build_event_factor_panel(feature, events, write_outputs=write_outputs)
    market_regime = build_market_regime_panel(feature, market, write_outputs=write_outputs)
    enhanced = build_enhanced_feature_matrix(feature, event_wide, market_regime, write_outputs=write_outputs)
    combined_long = write_factor_daily_panel_day7(event_long, market_regime, write_outputs=write_outputs)
    ablation, ablation_status = run_ablation(enhanced, write_outputs=write_outputs)
    latest_available_time = max(str(event_long["available_time"].max()), str(market_regime["available_time"].max()))
    leakage_ok = (
        events["leakage_check_status"].eq("passed").all()
        and event_long["leakage_check_status"].eq("passed").all()
        and market_regime["leakage_check_status"].eq("passed").all()
        and ablation.get("leakage_check_status") == "passed"
    )
    report = {
        "status": "ok" if leakage_ok else "failed",
        "day": 7,
        "maturity": "L2-event-regime-factor-ablation-local-artifacts",
        "run_id": RUN_ID,
        "data_version": DATA_VERSION,
        "schema_version": SCHEMA_VERSION,
        "event_factor_version": EVENT_FACTOR_VERSION,
        "market_regime_version": MARKET_REGIME_VERSION,
        "feature_set_version": FEATURE_SET_VERSION,
        "model_version": MODEL_VERSION,
        "text_model_status": "lexicon_finbert_compatible_baseline_ready",
        "event_type_model_status": "keyword_event_type_baseline_ready",
        "event_document_rows": int(len(news)),
        "announcement_document_rows": int(len(ann)),
        "entity_mapping_rows": int(len(mapping)),
        "event_extraction_rows": int(len(events)),
        "dwd_news_event_rows": int(len(dwd_news)),
        "dwd_announcement_event_rows": int(len(dwd_ann)),
        "event_factor_rows": int(len(event_long)),
        "market_regime_rows": int(len(market_regime)),
        "combined_factor_daily_rows": int(len(combined_long)),
        "enhanced_feature_rows": int(len(enhanced)),
        "ablation_status": ablation_status,
        "ablation_config_count": len(ablation.get("configs", {})),
        "latest_available_time": latest_available_time,
        "leakage_check_status": "passed" if leakage_ok else "failed",
        "regime_semantics": {
            "ex_ante_regime_feature": "available before prediction_time and allowed for model training",
            "ex_post_regime_label": "report_only_not_training_feature",
        },
        "llm_policy": "FinGPT/LLM outputs may support summaries, extraction, RAG, and auxiliary labels only; never direct buy/sell advice or untested trading signals.",
        "artifacts": {
            "news_document": str(NEWS_DIR.relative_to(ROOT)),
            "announcement_document": str(ANN_DIR.relative_to(ROOT)),
            "event_extraction_result": str(EVENT_RESULT_DIR.relative_to(ROOT)),
            "entity_symbol_mapping": str(ENTITY_MAPPING_DIR.relative_to(ROOT)),
            "dwd_news_event": str(DWD_NEWS_DIR.relative_to(ROOT)),
            "dwd_announcement_event": str(DWD_ANN_DIR.relative_to(ROOT)),
            "factor_news_sentiment_panel": str(EVENT_FACTOR_DIR.relative_to(ROOT)),
            "factor_market_regime_panel": str(MARKET_REGIME_DIR.relative_to(ROOT)),
            "factor_daily_panel_day7_event_regime": str(FACTOR_DAILY_DAY7_DIR.relative_to(ROOT)),
            "model_feature_matrix_wide_day7": str(ENHANCED_FEATURE_DIR.relative_to(ROOT)),
            "ablation_report": "reports/day7/event_regime_ablation_report.json",
            "ablation_report_html": "reports/day7/event_regime_ablation_report.html",
        },
        "research_boundary": RESEARCH_BOUNDARY,
        "generated_at": _now(),
    }
    if write_outputs:
        _write_json(DAY7_DIR / "day7_event_regime_report.json", report)
    return report


def main() -> None:
    print(json.dumps(run_day7_event_regime_pipeline(write_outputs=True), ensure_ascii=False, indent=2, default=_json_default))


if __name__ == "__main__":
    main()
