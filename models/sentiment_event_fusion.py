from __future__ import annotations

import json
import math
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

import lightgbm as lgb
import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
CURRENT_DAILY = ROOT / "data" / "real" / "csi300_daily" / "part-000.parquet"
NEWS_PATH = ROOT / "data" / "real" / "csi300_news" / "part-000.parquet"
MARKET_SENTIMENT_PATH = (
    ROOT / "data" / "real" / "sentiment_event" / "market_sentiment_daily.parquet"
)
CHECKPOINT_DIR = ROOT / "models" / "checkpoints" / "sentiment_event_fusion"
MODEL_PATH = CHECKPOINT_DIR / "model.txt"
METADATA_PATH = CHECKPOINT_DIR / "metadata.json"
PREDICTIONS_PATH = ROOT / "reports" / "research_loop" / "sentiment_event_predictions.parquet"
PREDICTIONS_REPORT_PATH = (
    ROOT / "reports" / "research_loop" / "sentiment_event_predictions_report.json"
)

MODEL_ID = "sentiment_event"
MODEL_FAMILY = "Sentiment Event Fusion LightGBM"
MODEL_FAMILY_ZH = "情绪/事件融合 LightGBM"
RESEARCH_BOUNDARY = "research_signals_only_not_investment_advice"

STOCK_FEATURES = [
    "stock_return_1d",
    "stock_return_5d",
    "stock_return_10d",
    "stock_return_20d",
    "stock_volatility_5d",
    "stock_volatility_20d",
    "intraday_return",
    "high_low_range",
    "amount_shock_20d",
    "turnover_zscore_20d",
    "cs_rank_return_1d",
    "cs_rank_return_20d",
    "cs_rank_amount_shock",
]
MARKET_FEATURES = [
    "market_return_1d",
    "market_return_5d",
    "market_return_20d",
    "market_breadth",
    "market_down_ratio",
    "market_dispersion",
    "market_volatility_20d",
    "market_drawdown_20d",
    "market_amount_zscore_60d",
    "market_turnover_zscore_60d",
    "risk_appetite_proxy",
    "market_event_shock",
    "market_sentiment_proxy",
]
NEWS_FEATURES = [
    "news_sentiment_1d",
    "news_sentiment_3d",
    "news_sentiment_5d",
    "news_event_count_1d",
    "news_event_count_5d",
    "negative_event_count_5d",
    "news_authority_5d",
    "news_coverage_5d",
    "earnings_event_count_5d",
    "guidance_event_count_5d",
    "regulation_event_count_5d",
]
FUSION_FEATURES = [
    "sentiment_market_alignment",
    "sentiment_disagreement",
    "event_volatility_interaction",
    "authority_weighted_event_gate",
]
FEATURE_COLUMNS = STOCK_FEATURES + MARKET_FEATURES + NEWS_FEATURES + FUSION_FEATURES


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


def _next_weekday(value: str) -> str:
    candidate = pd.Timestamp(value).date() + timedelta(days=1)
    while candidate.weekday() >= 5:
        candidate += timedelta(days=1)
    return candidate.isoformat()


def _rolling_group(frame: pd.DataFrame, column: str, window: int, operation: str) -> pd.Series:
    grouped = frame.groupby("symbol", sort=False)[column]
    if operation == "sum":
        return grouped.transform(lambda values: values.rolling(window, min_periods=1).sum())
    if operation == "mean":
        return grouped.transform(lambda values: values.rolling(window, min_periods=1).mean())
    if operation == "std":
        return grouped.transform(lambda values: values.rolling(window, min_periods=3).std())
    raise ValueError(f"unsupported rolling operation: {operation}")


def _prepare_stock_features(market: pd.DataFrame) -> pd.DataFrame:
    required = {"trade_date", "symbol", "open", "high", "low", "close", "amount", "turnover_rate"}
    missing = required.difference(market.columns)
    if missing:
        raise ValueError(f"market data is missing required columns: {sorted(missing)}")
    frame = market.copy()
    frame["trade_date"] = pd.to_datetime(frame["trade_date"], errors="coerce")
    for column in ("open", "high", "low", "close", "amount", "turnover_rate"):
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    frame = frame.dropna(subset=["trade_date", "symbol", "close"])
    frame = frame.sort_values(["symbol", "trade_date"]).drop_duplicates(
        ["symbol", "trade_date"], keep="last"
    )
    grouped_close = frame.groupby("symbol", sort=False)["close"]
    for days in (1, 5, 10, 20):
        frame[f"stock_return_{days}d"] = grouped_close.pct_change(days, fill_method=None)
    frame["stock_volatility_5d"] = _rolling_group(frame, "stock_return_1d", 5, "std")
    frame["stock_volatility_20d"] = _rolling_group(frame, "stock_return_1d", 20, "std")
    open_price = frame["open"].replace(0, np.nan)
    low_price = frame["low"].replace(0, np.nan)
    frame["intraday_return"] = frame["close"] / open_price - 1.0
    frame["high_low_range"] = frame["high"] / low_price - 1.0
    amount_mean = _rolling_group(frame, "amount", 20, "mean").replace(0, np.nan)
    frame["amount_shock_20d"] = frame["amount"] / amount_mean - 1.0
    turnover_mean = _rolling_group(frame, "turnover_rate", 20, "mean")
    turnover_std = _rolling_group(frame, "turnover_rate", 20, "std").replace(0, np.nan)
    frame["turnover_zscore_20d"] = (frame["turnover_rate"] - turnover_mean) / turnover_std
    frame["cs_rank_return_1d"] = frame.groupby("trade_date")["stock_return_1d"].rank(pct=True)
    frame["cs_rank_return_20d"] = frame.groupby("trade_date")["stock_return_20d"].rank(pct=True)
    frame["cs_rank_amount_shock"] = frame.groupby("trade_date")["amount_shock_20d"].rank(pct=True)
    frame["target_return_pct"] = (grouped_close.shift(-1) / frame["close"] - 1.0) * 100.0
    frame["target_trade_date"] = frame.groupby("symbol", sort=False)["trade_date"].shift(-1)
    return frame


def _prediction_cutoffs(trading_dates: list[pd.Timestamp]) -> tuple[np.ndarray, list[str]]:
    normalized = [pd.Timestamp(value).normalize() for value in trading_dates]
    feature_dates: list[str] = []
    cutoffs: list[pd.Timestamp] = []
    for index, feature_date in enumerate(normalized):
        if index + 1 < len(normalized):
            target_date = normalized[index + 1]
        else:
            target_date = pd.Timestamp(_next_weekday(feature_date.strftime("%Y-%m-%d")))
        cutoff = target_date.tz_localize("Asia/Shanghai") + pd.Timedelta(hours=9, minutes=25)
        feature_dates.append(feature_date.strftime("%Y-%m-%d"))
        cutoffs.append(cutoff)
    return np.asarray([value.value for value in cutoffs], dtype=np.int64), feature_dates


def _map_news_to_feature_dates(news: pd.DataFrame, trading_dates: list[pd.Timestamp]) -> pd.DataFrame:
    if news.empty or "available_time" not in news.columns:
        return pd.DataFrame()
    events = news.copy()
    events["available_timestamp"] = pd.to_datetime(
        events["available_time"], errors="coerce", utc=True
    ).dt.tz_convert("Asia/Shanghai")
    events = events.dropna(subset=["available_timestamp", "symbol"])
    if events.empty:
        return events
    cutoff_ns, feature_dates = _prediction_cutoffs(trading_dates)
    event_ns = events["available_timestamp"].astype("int64").to_numpy()
    positions = np.searchsorted(cutoff_ns, event_ns, side="left")
    valid = positions < len(feature_dates)
    events = events.loc[valid].copy()
    positions = positions[valid]
    events["feature_trade_date"] = [feature_dates[position] for position in positions]
    events["sentiment_score"] = pd.to_numeric(
        events.get("sentiment_score", 0.0), errors="coerce"
    ).fillna(0.0).clip(-1, 1)
    events["source_authority_weight"] = pd.to_numeric(
        events.get("source_authority_weight", 0.65), errors="coerce"
    ).fillna(0.65).clip(0, 1)
    if "event_type" not in events.columns:
        events["event_type"] = "general_news"
    else:
        events["event_type"] = events["event_type"].fillna("general_news")
    return events


def _news_features(
    stock_panel: pd.DataFrame,
    news: pd.DataFrame,
) -> pd.DataFrame:
    trading_dates = sorted(stock_panel["trade_date"].dropna().unique().tolist())
    mapped = _map_news_to_feature_dates(news, trading_dates)
    if mapped.empty:
        daily = pd.DataFrame(
            columns=[
                "trade_date", "symbol", "weighted_sentiment_sum", "authority_sum",
                "news_event_count_1d", "negative_event_count_1d", "earnings_event_count_1d",
                "guidance_event_count_1d", "regulation_event_count_1d",
            ]
        )
    else:
        mapped["weighted_sentiment"] = (
            mapped["sentiment_score"] * mapped["source_authority_weight"]
        )
        mapped["negative_event"] = mapped["sentiment_score"].lt(-0.05).astype(float)
        for event_type in ("earnings", "guidance", "regulation"):
            mapped[f"{event_type}_event"] = mapped["event_type"].eq(event_type).astype(float)
        daily = (
            mapped.groupby(["feature_trade_date", "symbol"], as_index=False)
            .agg(
                weighted_sentiment_sum=("weighted_sentiment", "sum"),
                authority_sum=("source_authority_weight", "sum"),
                news_event_count_1d=("event_id", "nunique"),
                negative_event_count_1d=("negative_event", "sum"),
                earnings_event_count_1d=("earnings_event", "sum"),
                guidance_event_count_1d=("guidance_event", "sum"),
                regulation_event_count_1d=("regulation_event", "sum"),
            )
            .rename(columns={"feature_trade_date": "trade_date"})
        )
    daily["trade_date"] = pd.to_datetime(daily["trade_date"])

    panel = stock_panel[["trade_date", "symbol"]].copy()
    panel = panel.merge(daily, on=["trade_date", "symbol"], how="left")
    numeric = [
        "weighted_sentiment_sum", "authority_sum", "news_event_count_1d",
        "negative_event_count_1d", "earnings_event_count_1d",
        "guidance_event_count_1d", "regulation_event_count_1d",
    ]
    for column in numeric:
        panel[column] = pd.to_numeric(panel[column], errors="coerce").fillna(0.0)
    panel = panel.sort_values(["symbol", "trade_date"])
    authority_1d = panel["authority_sum"].replace(0, np.nan)
    panel["news_sentiment_1d"] = (
        panel["weighted_sentiment_sum"] / authority_1d
    ).fillna(0.0)
    for window in (3, 5):
        weighted_sum = _rolling_group(panel, "weighted_sentiment_sum", window, "sum")
        authority_sum = _rolling_group(panel, "authority_sum", window, "sum").replace(0, np.nan)
        panel[f"news_sentiment_{window}d"] = (weighted_sum / authority_sum).fillna(0.0)
    panel["news_event_count_5d"] = _rolling_group(panel, "news_event_count_1d", 5, "sum")
    panel["negative_event_count_5d"] = _rolling_group(
        panel, "negative_event_count_1d", 5, "sum"
    )
    panel["news_authority_5d"] = _rolling_group(panel, "authority_sum", 5, "sum")
    panel["news_coverage_5d"] = panel["news_event_count_5d"].gt(0).astype(float)
    for event_type in ("earnings", "guidance", "regulation"):
        panel[f"{event_type}_event_count_5d"] = _rolling_group(
            panel, f"{event_type}_event_count_1d", 5, "sum"
        )
    return panel[["trade_date", "symbol", *NEWS_FEATURES]]


def build_sentiment_event_feature_panel(
    market: pd.DataFrame,
    *,
    news: pd.DataFrame | None = None,
    market_sentiment: pd.DataFrame | None = None,
) -> pd.DataFrame:
    stock = _prepare_stock_features(market)
    if market_sentiment is None:
        if not MARKET_SENTIMENT_PATH.exists():
            from data.adapters.sentiment_event_data import build_market_sentiment_panel

            market_sentiment = build_market_sentiment_panel(market)
        else:
            market_sentiment = pd.read_parquet(MARKET_SENTIMENT_PATH)
    market_factors = market_sentiment.copy()
    market_factors["trade_date"] = pd.to_datetime(market_factors["trade_date"], errors="coerce")
    stock = stock.merge(
        market_factors[["trade_date", *MARKET_FEATURES]], on="trade_date", how="left"
    )
    if news is None:
        news = pd.read_parquet(NEWS_PATH) if NEWS_PATH.exists() else pd.DataFrame()
    news_panel = _news_features(stock, news)
    stock = stock.merge(news_panel, on=["trade_date", "symbol"], how="left")
    for column in NEWS_FEATURES:
        stock[column] = pd.to_numeric(stock[column], errors="coerce").fillna(0.0)
    stock["sentiment_market_alignment"] = (
        stock["news_sentiment_5d"] * stock["market_sentiment_proxy"]
    )
    stock["sentiment_disagreement"] = (
        stock["news_sentiment_5d"] - stock["market_sentiment_proxy"]
    ).abs()
    stock["event_volatility_interaction"] = (
        stock["news_sentiment_5d"] * stock["market_event_shock"]
    )
    stock["authority_weighted_event_gate"] = (
        stock["news_sentiment_5d"]
        * np.log1p(stock["news_event_count_5d"])
        * (1.0 + stock["news_authority_5d"].clip(0, 3) / 3.0)
    )
    stock[FEATURE_COLUMNS] = stock[FEATURE_COLUMNS].replace([np.inf, -np.inf], np.nan)
    return stock


def _mean_cross_sectional_correlation(
    frame: pd.DataFrame, prediction_column: str, *, rank: bool = False
) -> float | None:
    values: list[float] = []
    for _, group in frame.groupby("trade_date"):
        usable = group[[prediction_column, "target_return_pct"]].dropna()
        if len(usable) < 5 or usable[prediction_column].nunique() < 2:
            continue
        method = "spearman" if rank else "pearson"
        correlation = usable[prediction_column].corr(usable["target_return_pct"], method=method)
        if pd.notna(correlation):
            values.append(float(correlation))
    return float(np.mean(values)) if values else None


def _metrics(y_true: pd.Series, y_pred: np.ndarray, dates: pd.Series) -> dict[str, Any]:
    evaluation = pd.DataFrame(
        {"trade_date": dates.astype(str), "target_return_pct": y_true.to_numpy(), "prediction": y_pred}
    )
    error = y_true.to_numpy() - y_pred
    return {
        "mse": float(np.mean(np.square(error))),
        "mae": float(np.mean(np.abs(error))),
        "ic_mean": _mean_cross_sectional_correlation(evaluation, "prediction", rank=False),
        "rank_ic_mean": _mean_cross_sectional_correlation(evaluation, "prediction", rank=True),
    }


def _new_regressor(n_estimators: int) -> lgb.LGBMRegressor:
    return lgb.LGBMRegressor(
        objective="regression_l1",
        n_estimators=max(20, int(n_estimators)),
        learning_rate=0.035,
        num_leaves=31,
        max_depth=-1,
        min_child_samples=80,
        subsample=0.85,
        colsample_bytree=0.82,
        reg_alpha=0.15,
        reg_lambda=0.35,
        random_state=2026,
        n_jobs=-1,
        verbosity=-1,
    )


def train_sentiment_event_fusion(
    market: pd.DataFrame,
    *,
    news: pd.DataFrame | None = None,
    market_sentiment: pd.DataFrame | None = None,
    max_estimators: int = 450,
) -> dict[str, Any]:
    panel = build_sentiment_event_feature_panel(
        market, news=news, market_sentiment=market_sentiment
    )
    labeled = panel.dropna(subset=["target_return_pct", "target_trade_date"]).copy()
    labeled = labeled[labeled["stock_return_20d"].notna()]
    dates = [pd.Timestamp(value) for value in sorted(labeled["trade_date"].drop_duplicates().tolist())]
    if len(dates) < 60:
        raise ValueError("sentiment-event model needs at least 60 labeled trading dates")
    train_end = max(1, int(len(dates) * 0.70))
    validation_end = min(len(dates) - 1, max(train_end + 1, int(len(dates) * 0.85)))
    train_dates = set(dates[:train_end])
    validation_dates = set(dates[train_end:validation_end])
    test_dates = set(dates[validation_end:])
    train = labeled[labeled["trade_date"].isin(train_dates)]
    validation = labeled[labeled["trade_date"].isin(validation_dates)]
    test = labeled[labeled["trade_date"].isin(test_dates)]
    if train.empty or validation.empty or test.empty:
        raise ValueError("chronological train/validation/test split produced an empty partition")

    selector = _new_regressor(max_estimators)
    sample_weight = 1.0 + train["news_event_count_5d"].clip(0, 4) * 0.15
    selector.fit(
        train[FEATURE_COLUMNS],
        train["target_return_pct"],
        sample_weight=sample_weight,
        eval_set=[(validation[FEATURE_COLUMNS], validation["target_return_pct"])],
        callbacks=[lgb.early_stopping(35, verbose=False)],
    )
    best_iteration = int(selector.best_iteration_ or max_estimators)
    test_prediction = selector.predict(test[FEATURE_COLUMNS], num_iteration=best_iteration)
    full_metrics = _metrics(
        test["target_return_pct"], test_prediction, test["trade_date"]
    )

    baseline = _new_regressor(best_iteration)
    baseline.fit(train[STOCK_FEATURES], train["target_return_pct"])
    baseline_prediction = baseline.predict(test[STOCK_FEATURES])
    baseline_metrics = _metrics(
        test["target_return_pct"], baseline_prediction, test["trade_date"]
    )

    final_model = _new_regressor(best_iteration)
    final_weight = 1.0 + labeled["news_event_count_5d"].clip(0, 4) * 0.15
    final_model.fit(
        labeled[FEATURE_COLUMNS], labeled["target_return_pct"], sample_weight=final_weight
    )
    CHECKPOINT_DIR.mkdir(parents=True, exist_ok=True)
    temporary_model = MODEL_PATH.with_name(f".{MODEL_PATH.name}.{uuid4().hex}.tmp")
    try:
        final_model.booster_.save_model(str(temporary_model))
        os.replace(temporary_model, MODEL_PATH)
    finally:
        temporary_model.unlink(missing_ok=True)

    news_frame = news if news is not None else (
        pd.read_parquet(NEWS_PATH) if NEWS_PATH.exists() else pd.DataFrame()
    )
    latest_date = str(panel["trade_date"].max().date())
    latest = panel[panel["trade_date"].eq(panel["trade_date"].max())]
    metadata = {
        "status": "ok",
        "model_id": MODEL_ID,
        "model_family": MODEL_FAMILY,
        "model_family_zh": MODEL_FAMILY_ZH,
        "model_version": f"sentiment-event-lgbm-{latest_date.replace('-', '')}-v001",
        "implementation_scope": "CAMEF/CARAG-inspired daily model; not an exact reproduction",
        "paper_references": [
            "https://doi.org/10.1145/3711896.3736872",
            "https://aclanthology.org/2026.eacl-long.141/",
        ],
        "feature_columns": FEATURE_COLUMNS,
        "feature_groups": {
            "stock_time_series": STOCK_FEATURES,
            "market_sentiment_proxy": MARKET_FEATURES,
            "optional_real_news": NEWS_FEATURES,
            "multimodal_interactions": FUSION_FEATURES,
        },
        "availability_policy": "News is assigned to the latest feature date only when available before the next trading-day 09:25 cutoff.",
        "causal_claim_boundary": "Interaction gates and event-type features are causal-inspired proxies, not identified causal effects.",
        "sentiment_method": "deterministic Chinese financial lexicon plus source-authority weighting",
        "news_event_rows": int(len(news_frame)),
        "news_symbol_coverage": int(news_frame["symbol"].nunique()) if not news_frame.empty else 0,
        "latest_news_coverage_count": int(latest["news_coverage_5d"].sum()),
        "latest_market_sentiment_proxy": float(latest["market_sentiment_proxy"].iloc[0]),
        "latest_risk_appetite_proxy": float(latest["risk_appetite_proxy"].iloc[0]),
        "latest_input_date": latest_date,
        "prediction_target_date": _next_weekday(latest_date),
        "prediction_target_date_is_estimated": True,
        "training_sample_count": int(len(labeled)),
        "training_date_count": int(len(dates)),
        "chronological_split": {
            "train_rows": int(len(train)),
            "train_end_date": str(max(train_dates).date()),
            "validation_rows": int(len(validation)),
            "validation_start_date": str(min(validation_dates).date()),
            "validation_end_date": str(max(validation_dates).date()),
            "test_rows": int(len(test)),
            "test_start_date": str(min(test_dates).date()),
            "test_end_date": str(max(test_dates).date()),
        },
        "best_iteration": best_iteration,
        "test_metrics": full_metrics,
        "price_only_ablation_metrics": baseline_metrics,
        "research_boundary": RESEARCH_BOUNDARY,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    _write_json_atomic(METADATA_PATH, metadata)
    return metadata


def predict_sentiment_event_fusion(
    market: pd.DataFrame,
    *,
    news: pd.DataFrame | None = None,
    market_sentiment: pd.DataFrame | None = None,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    if not MODEL_PATH.exists() or not METADATA_PATH.exists():
        raise FileNotFoundError(
            "sentiment-event checkpoint is missing; run scripts/train_sentiment_event_fusion.py"
        )
    metadata = json.loads(METADATA_PATH.read_text(encoding="utf-8"))
    panel = build_sentiment_event_feature_panel(
        market, news=news, market_sentiment=market_sentiment
    )
    date_counts = panel.groupby("trade_date")["symbol"].nunique().sort_index()
    expected = int(date_counts.max())
    complete_dates = date_counts[date_counts >= expected]
    latest_date = complete_dates.index[-1] if not complete_dates.empty else date_counts.index[-1]
    latest = panel[panel["trade_date"].eq(latest_date)].copy()
    booster = lgb.Booster(model_file=str(MODEL_PATH))
    latest["predicted_relative_change_pct"] = booster.predict(latest[FEATURE_COLUMNS])
    latest["predicted_relative_change"] = latest["predicted_relative_change_pct"] / 100.0
    latest["score"] = latest["predicted_relative_change_pct"]
    latest = latest.sort_values(
        ["predicted_relative_change_pct", "symbol"], ascending=[False, True]
    ).reset_index(drop=True)
    latest["rank"] = np.arange(1, len(latest) + 1)
    latest["percentile"] = 1.0 - (latest["rank"] - 1) / max(1, len(latest))
    latest_date_text = pd.Timestamp(latest_date).strftime("%Y-%m-%d")
    prediction_target_date = _next_weekday(latest_date_text)
    latest["trade_date"] = latest_date_text
    latest["prediction_target_date"] = prediction_target_date
    latest["horizon"] = "1d"
    latest["model_name"] = MODEL_FAMILY
    latest["model_family"] = MODEL_FAMILY
    latest["model_version"] = metadata["model_version"]
    latest["probability_up"] = np.nan
    latest["probability_down"] = np.nan
    latest["confidence"] = np.nan
    latest["signal_direction"] = np.where(
        latest["predicted_relative_change_pct"].ge(0), "up", "down"
    )
    latest["sentiment_score"] = (
        0.65 * latest["market_sentiment_proxy"] + 0.35 * latest["news_sentiment_5d"]
    )
    latest["sentiment_source"] = np.where(
        latest["news_coverage_5d"].gt(0),
        "market_proxy_plus_real_news",
        "market_proxy_only",
    )
    latest["sentiment_coverage"] = latest["news_coverage_5d"]
    latest["information_source"] = "daily_market_proxy_and_optional_time_aligned_real_news"
    latest["sentiment_polarity_used"] = True
    latest["leakage_check_status"] = "chronological_split_and_next_open_availability_cutoff"
    latest["research_boundary"] = RESEARCH_BOUNDARY
    columns = [
        "trade_date", "prediction_target_date", "symbol", "stock_name", "industry_name",
        "score", "predicted_relative_change", "predicted_relative_change_pct", "rank",
        "percentile", "horizon", "model_name", "model_family", "model_version",
        "probability_up", "probability_down", "confidence", "signal_direction",
        "sentiment_score", "sentiment_source", "sentiment_coverage", "news_sentiment_5d",
        "news_event_count_5d", "market_sentiment_proxy", "risk_appetite_proxy",
        "market_event_shock", "information_source", "sentiment_polarity_used",
        "leakage_check_status", "research_boundary",
    ]
    return latest[[column for column in columns if column in latest.columns]], metadata


def build_sentiment_event_scores() -> dict[str, Any]:
    if not CURRENT_DAILY.exists():
        raise FileNotFoundError(f"daily market data not found: {CURRENT_DAILY}")
    market = pd.read_parquet(CURRENT_DAILY)
    predictions, metadata = predict_sentiment_event_fusion(market)
    _write_parquet_atomic(PREDICTIONS_PATH, predictions)
    latest_date = str(predictions["trade_date"].max())
    news_covered = int(predictions["sentiment_coverage"].fillna(0).gt(0).sum())
    report = {
        "status": "ok",
        "run_id": "sentiment_event_fusion_inference_v001",
        "experiment_id": "exp_sentiment_event_fusion_lgbm_v001",
        "model_id": MODEL_ID,
        "model_family": MODEL_FAMILY,
        "model_version": metadata["model_version"],
        "model_methodology": metadata,
        "model_description": "融合股票时序、市场情绪代理和按可用时间对齐的可选真实新闻情绪。",
        "latest_trade_date": latest_date,
        "prediction_target_date": str(predictions["prediction_target_date"].iloc[0]),
        "prediction_target_date_is_estimated": True,
        "horizon": "1d",
        "prediction_rows": int(len(predictions)),
        "model_output_rows": int(len(predictions)),
        "display_overlap_rows": int(len(predictions)),
        "probability_calibration": "none; raw next-day relative-return regression output",
        "sentiment_status": (
            "market_proxy_plus_optional_real_news"
            if news_covered > 0
            else "market_proxy_only_no_recent_stock_news"
        ),
        "text_sentiment_coverage": news_covered,
        "news_event_rows": metadata.get("news_event_rows", 0),
        "news_symbol_coverage": metadata.get("news_symbol_coverage", 0),
        "market_sentiment_proxy": metadata.get("latest_market_sentiment_proxy"),
        "risk_appetite_proxy": metadata.get("latest_risk_appetite_proxy"),
        "training_sample_count": metadata.get("training_sample_count"),
        "latest_training_label_date": metadata.get("chronological_split", {}).get("test_end_date"),
        "test_metrics": metadata.get("test_metrics"),
        "price_only_ablation_metrics": metadata.get("price_only_ablation_metrics"),
        "implementation_scope": metadata.get("implementation_scope"),
        "paper_references": metadata.get("paper_references"),
        "artifact": str(PREDICTIONS_PATH.relative_to(ROOT)).replace("\\", "/"),
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "research_boundary": RESEARCH_BOUNDARY,
    }
    _write_json_atomic(PREDICTIONS_REPORT_PATH, report)
    return report
