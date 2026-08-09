from __future__ import annotations

import hashlib
import json
import math
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable
from uuid import uuid4

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
DAILY_PATH = ROOT / "data" / "real" / "csi300_daily" / "part-000.parquet"
NEWS_PATH = ROOT / "data" / "real" / "csi300_news" / "part-000.parquet"
MARKET_SENTIMENT_PATH = (
    ROOT / "data" / "real" / "sentiment_event" / "market_sentiment_daily.parquet"
)
REPORT_PATH = ROOT / "reports" / "real_data" / "sentiment_event_data_report.json"
RESEARCH_BOUNDARY = "research_signals_only_not_investment_advice"

POSITIVE_TERMS = (
    "增长", "上调", "超预期", "盈利", "扭亏", "中标", "增持", "买入", "突破", "创新高",
    "回购", "分红", "扩产", "获批", "利好", "改善", "提振", "强劲", "领先", "签约",
)
NEGATIVE_TERMS = (
    "下滑", "下调", "低于预期", "亏损", "减持", "卖出", "违约", "诉讼", "处罚", "立案",
    "退市", "暴跌", "风险", "停产", "召回", "利空", "恶化", "质押", "调查", "警示",
)
EVENT_TYPE_TERMS: dict[str, tuple[str, ...]] = {
    "earnings": ("业绩", "营收", "净利润", "财报", "预告", "快报"),
    "guidance": ("展望", "指引", "目标价", "评级", "买入", "增持"),
    "capital_action": ("回购", "分红", "减持", "增发", "并购", "重组"),
    "regulation": ("监管", "处罚", "立案", "调查", "政策", "获批"),
    "operations": ("中标", "签约", "订单", "扩产", "停产", "召回"),
    "macro": ("央行", "利率", "通胀", "就业", "GDP", "CPI", "PPI", "汇率"),
}


def _json_default(value: Any) -> Any:
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        number = float(value)
        return None if math.isnan(number) or math.isinf(number) else number
    if isinstance(value, (pd.Timestamp, datetime, Path)):
        return str(value)
    return value


def _write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
    try:
        temporary.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, default=_json_default),
            encoding="utf-8",
        )
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _write_parquet_atomic(path: Path, frame: pd.DataFrame) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.stem}.{uuid4().hex}.tmp.parquet")
    try:
        frame.to_parquet(temporary, index=False)
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _sha256(path: Path) -> str | None:
    if not path.exists():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def score_chinese_financial_sentiment(text: str) -> tuple[float, int, int]:
    normalized = str(text or "")
    positive_hits = sum(normalized.count(term) for term in POSITIVE_TERMS)
    negative_hits = sum(normalized.count(term) for term in NEGATIVE_TERMS)
    total = positive_hits + negative_hits
    if total == 0:
        return 0.0, 0, 0
    score = float(np.clip((positive_hits - negative_hits) / math.sqrt(total), -1.0, 1.0))
    return score, positive_hits, negative_hits


def classify_event_type(text: str) -> str:
    normalized = str(text or "")
    matches = {
        event_type: sum(normalized.count(term) for term in terms)
        for event_type, terms in EVENT_TYPE_TERMS.items()
    }
    best_type, best_count = max(matches.items(), key=lambda item: item[1])
    return best_type if best_count > 0 else "general_news"


def _rolling_zscore(series: pd.Series, window: int = 60) -> pd.Series:
    minimum = min(10, window)
    mean = series.rolling(window, min_periods=minimum).mean()
    std = series.rolling(window, min_periods=minimum).std().replace(0, np.nan)
    return ((series - mean) / std).replace([np.inf, -np.inf], np.nan).fillna(0.0)


def build_market_sentiment_panel(market: pd.DataFrame) -> pd.DataFrame:
    required = {"trade_date", "symbol", "close", "amount", "turnover_rate"}
    missing = required.difference(market.columns)
    if missing:
        raise ValueError(f"market data is missing required columns: {sorted(missing)}")

    frame = market.copy()
    frame["trade_date"] = pd.to_datetime(frame["trade_date"], errors="coerce")
    frame = frame.dropna(subset=["trade_date", "symbol", "close"])
    frame = frame.sort_values(["symbol", "trade_date"]).drop_duplicates(
        ["symbol", "trade_date"], keep="last"
    )
    frame["stock_return_1d"] = frame.groupby("symbol", sort=False)["close"].pct_change(
        fill_method=None
    )
    frame["amount"] = pd.to_numeric(frame["amount"], errors="coerce").fillna(0.0)
    frame["turnover_rate"] = pd.to_numeric(
        frame["turnover_rate"], errors="coerce"
    ).fillna(0.0)

    panel = (
        frame.groupby("trade_date", as_index=False)
        .agg(
            market_return_1d=("stock_return_1d", "mean"),
            market_breadth=("stock_return_1d", lambda values: float((values > 0).mean())),
            market_down_ratio=("stock_return_1d", lambda values: float((values < 0).mean())),
            market_dispersion=("stock_return_1d", "std"),
            market_amount=("amount", "sum"),
            market_turnover=("turnover_rate", "median"),
            constituent_count=("symbol", "nunique"),
        )
        .sort_values("trade_date")
        .reset_index(drop=True)
    )
    panel["market_return_1d"] = panel["market_return_1d"].fillna(0.0)
    panel["market_dispersion"] = panel["market_dispersion"].fillna(0.0)
    panel["market_return_5d"] = (
        (1.0 + panel["market_return_1d"]).rolling(5, min_periods=1).apply(np.prod, raw=True)
        - 1.0
    )
    panel["market_return_20d"] = (
        (1.0 + panel["market_return_1d"]).rolling(20, min_periods=1).apply(np.prod, raw=True)
        - 1.0
    )
    panel["market_volatility_20d"] = panel["market_return_1d"].rolling(
        20, min_periods=5
    ).std().fillna(0.0)
    market_index = (1.0 + panel["market_return_1d"]).cumprod()
    panel["market_drawdown_20d"] = (
        market_index / market_index.rolling(20, min_periods=1).max() - 1.0
    )
    panel["market_amount_zscore_60d"] = _rolling_zscore(
        np.log1p(panel["market_amount"]), 60
    )
    panel["market_turnover_zscore_60d"] = _rolling_zscore(panel["market_turnover"], 60)
    return_strength = _rolling_zscore(panel["market_return_5d"], 60)
    volatility_pressure = _rolling_zscore(panel["market_volatility_20d"], 60)
    breadth_balance = (panel["market_breadth"] - panel["market_down_ratio"]).clip(-1, 1)
    panel["risk_appetite_proxy"] = (
        0.35 * return_strength
        + 0.35 * breadth_balance
        + 0.15 * panel["market_amount_zscore_60d"]
        - 0.15 * volatility_pressure
    ).clip(-3, 3)
    volatility_floor = panel["market_volatility_20d"].replace(0, np.nan)
    panel["market_event_shock"] = (
        panel["market_return_1d"].abs() / volatility_floor
    ).replace([np.inf, -np.inf], np.nan).fillna(0.0).clip(0, 8)
    panel["market_sentiment_proxy"] = np.tanh(
        panel["risk_appetite_proxy"]
        + 0.25 * breadth_balance
        - 0.08 * panel["market_event_shock"]
    )
    panel["available_time"] = panel["trade_date"].dt.strftime("%Y-%m-%dT15:30:00+08:00")
    panel["prediction_time"] = panel["trade_date"].dt.strftime("%Y-%m-%dT16:00:00+08:00")
    panel["trade_date"] = panel["trade_date"].dt.strftime("%Y-%m-%d")
    panel["data_version"] = "real_csi300_market_sentiment_proxy_v001"
    panel["schema_version"] = "sentiment_event_market_daily_v001"
    panel["research_boundary"] = RESEARCH_BOUNDARY
    return panel


def _authority_weight(source_name: str) -> float:
    source = str(source_name or "")
    if any(term in source for term in ("新华社", "证监会", "交易所", "人民银行", "统计局")):
        return 1.0
    if any(term in source for term in ("证券时报", "中国证券报", "上海证券报", "第一财经")):
        return 0.82
    return 0.65


def _local_timestamp(value: Any) -> pd.Timestamp | None:
    try:
        timestamp = pd.Timestamp(value)
    except (TypeError, ValueError):
        return None
    if pd.isna(timestamp):
        return None
    if timestamp.tzinfo is None:
        return timestamp.tz_localize("Asia/Shanghai")
    return timestamp.tz_convert("Asia/Shanghai")


def _news_event_id(symbol: str, title: str, publish_time: str, url: str) -> str:
    raw = "|".join((symbol, title, publish_time, url)).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()[:24]


def _normalize_symbols(symbols: Iterable[str]) -> list[str]:
    normalized = []
    for symbol in symbols:
        text = str(symbol).strip().upper()
        if not text:
            continue
        normalized.append(text if "." in text else f"{text}.SH" if text.startswith("6") else f"{text}.SZ")
    return sorted(set(normalized))


def fetch_real_stock_news(
    symbols: Iterable[str],
    *,
    lookback_days: int = 30,
    request_delay_seconds: float = 0.05,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    import akshare as ak

    normalized_symbols = _normalize_symbols(symbols)
    if not normalized_symbols:
        return pd.DataFrame(), {"requested_symbols": 0, "successful_symbols": 0, "failed_symbols": []}
    latest_market_date = pd.Timestamp(pd.read_parquet(DAILY_PATH, columns=["trade_date"])["trade_date"].max())
    minimum_publish_time = latest_market_date - pd.Timedelta(days=max(1, lookback_days))
    rows: list[dict[str, Any]] = []
    failed_symbols: list[dict[str, str]] = []
    successful_symbols = 0

    for symbol in normalized_symbols:
        code = symbol.split(".", 1)[0]
        try:
            news = ak.stock_news_em(symbol=code)
            successful_symbols += 1
        except Exception as exc:
            failed_symbols.append({"symbol": symbol, "error": f"{type(exc).__name__}: {exc}"})
            continue
        if news is None or news.empty:
            continue
        for item in news.to_dict(orient="records"):
            publish = _local_timestamp(item.get("发布时间"))
            if publish is None or publish.tz_localize(None) < minimum_publish_time:
                continue
            title = str(item.get("新闻标题") or "").strip()
            content = str(item.get("新闻内容") or "").strip()
            url = str(item.get("新闻链接") or "").strip()
            source_name = str(item.get("文章来源") or "unknown").strip()
            text = f"{title} {content}"
            sentiment, positive_hits, negative_hits = score_chinese_financial_sentiment(text)
            publish_text = publish.isoformat()
            available = publish + pd.Timedelta(minutes=5)
            rows.append(
                {
                    "event_id": _news_event_id(symbol, title, publish_text, url),
                    "symbol": symbol,
                    "keyword": str(item.get("关键词") or code),
                    "title": title,
                    "content_excerpt": content[:1000],
                    "publish_time": publish_text,
                    "available_time": available.isoformat(),
                    "source_name": source_name,
                    "source": "eastmoney_stock_news",
                    "url": url,
                    "event_type": classify_event_type(text),
                    "sentiment_score": sentiment,
                    "positive_term_hits": positive_hits,
                    "negative_term_hits": negative_hits,
                    "source_authority_weight": _authority_weight(source_name),
                    "sentiment_method": "deterministic_chinese_financial_lexicon_v002",
                    "source_version": "akshare_stock_news_em_v001",
                    "license_id": "eastmoney_public_web_research_only",
                    "data_version": "real_eastmoney_stock_news_incremental_v002",
                    "schema_version": "real_csi300_news_v002",
                    "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                    "research_boundary": RESEARCH_BOUNDARY,
                }
            )
        if request_delay_seconds > 0:
            time.sleep(request_delay_seconds)

    fetched = pd.DataFrame(rows)
    report = {
        "requested_symbols": len(normalized_symbols),
        "successful_symbols": successful_symbols,
        "failed_symbols": failed_symbols,
        "fetched_event_rows": int(len(fetched)),
        "lookback_days": lookback_days,
    }
    return fetched, report


def _merge_news(existing: pd.DataFrame, fetched: pd.DataFrame) -> tuple[pd.DataFrame, int]:
    if existing.empty and fetched.empty:
        return pd.DataFrame(), 0
    combined = pd.concat([existing, fetched], ignore_index=True, sort=False)
    if "event_id" not in combined.columns:
        raise ValueError("news data must contain event_id")
    before_ids = set(existing.get("event_id", pd.Series(dtype=str)).astype(str))
    combined = combined.drop_duplicates("event_id", keep="last").sort_values(
        ["available_time", "symbol", "event_id"]
    )
    new_count = len(set(combined["event_id"].astype(str)).difference(before_ids))
    return combined.reset_index(drop=True), int(new_count)


def update_sentiment_event_data(
    *,
    fetch_news: bool = False,
    symbols: Iterable[str] | None = None,
    max_symbols: int | None = None,
    lookback_days: int = 30,
    request_delay_seconds: float = 0.05,
) -> dict[str, Any]:
    if not DAILY_PATH.exists():
        raise FileNotFoundError(f"daily market data not found: {DAILY_PATH}")
    market = pd.read_parquet(DAILY_PATH)
    market_panel = build_market_sentiment_panel(market)
    _write_parquet_atomic(MARKET_SENTIMENT_PATH, market_panel)

    existing_news = pd.read_parquet(NEWS_PATH) if NEWS_PATH.exists() else pd.DataFrame()
    universe = _normalize_symbols(
        symbols
        if symbols is not None
        else market.loc[
            market["trade_date"].astype(str).eq(str(market["trade_date"].max())), "symbol"
        ].tolist()
    )
    if max_symbols is not None:
        universe = universe[: max(0, max_symbols)]

    fetch_report: dict[str, Any] = {
        "requested_symbols": 0,
        "successful_symbols": 0,
        "failed_symbols": [],
        "fetched_event_rows": 0,
        "lookback_days": lookback_days,
    }
    new_event_rows = 0
    if fetch_news:
        fetched_news, fetch_report = fetch_real_stock_news(
            universe,
            lookback_days=lookback_days,
            request_delay_seconds=request_delay_seconds,
        )
        merged_news, new_event_rows = _merge_news(existing_news, fetched_news)
        if not merged_news.empty:
            _write_parquet_atomic(NEWS_PATH, merged_news)
            existing_news = merged_news

    news_symbols = int(existing_news["symbol"].nunique()) if not existing_news.empty else 0
    latest_market_date = str(market["trade_date"].max())
    report = {
        "status": "ok",
        "latest_market_date": latest_market_date,
        "market_sentiment_rows": int(len(market_panel)),
        "latest_market_sentiment_proxy": float(market_panel.iloc[-1]["market_sentiment_proxy"]),
        "latest_risk_appetite_proxy": float(market_panel.iloc[-1]["risk_appetite_proxy"]),
        "news_fetch_enabled": fetch_news,
        **fetch_report,
        "new_event_rows": new_event_rows,
        "stored_event_rows": int(len(existing_news)),
        "news_symbol_coverage": news_symbols,
        "universe_size": len(_normalize_symbols(market["symbol"].unique())),
        "news_coverage_ratio": float(news_symbols / max(1, market["symbol"].nunique())),
        "sentiment_method": "market_proxy_plus_optional_real_news_lexicon_v001",
        "market_artifact": str(MARKET_SENTIMENT_PATH.relative_to(ROOT)).replace("\\", "/"),
        "news_artifact": str(NEWS_PATH.relative_to(ROOT)).replace("\\", "/"),
        "market_fingerprint": _sha256(MARKET_SENTIMENT_PATH),
        "news_fingerprint": _sha256(NEWS_PATH),
        "research_boundary": RESEARCH_BOUNDARY,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    _write_json_atomic(REPORT_PATH, report)
    return report

