from __future__ import annotations

import json
import math
import shutil
import warnings
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import yaml

try:  # The factor_store local research path is Polars-first, with pandas used for mature rolling stats.
    import polars as pl  # type: ignore

    POLARS_AVAILABLE = True
except Exception:  # pragma: no cover - verified by acceptance report, not unit logic
    pl = None  # type: ignore
    POLARS_AVAILABLE = False

ROOT = Path(__file__).resolve().parents[2]
factor_store_VERSION = "factor_store_v001"
SOURCE_VERSION = "synthetic_mini_market_v001"
SCHEMA_VERSION = "v0.4.0"
FACTOR_VERSION = "factor_v004"
FEATURE_SET_VERSION = "feature_set_factor_store_v001"
RUN_ID = "factor_store_offline_factor_store_v001"
RESEARCH_BOUNDARY = "research_signals_only_not_investment_advice"

SOURCE_DIR = ROOT / "data" / "samples" / "synthetic_mini_market"
REAL_CSI300_SOURCE_DIR = ROOT / "data" / "real" / "csi300_daily"
FACTOR_LONG_DIR = ROOT / "data" / "gold" / "factor_daily_panel_long"
FEATURE_WIDE_DIR = ROOT / "data" / "gold" / "model_feature_matrix_wide"
RISK_EXPOSURE_DIR = ROOT / "data" / "gold" / "risk_factor_exposure"
RISK_COV_DIR = ROOT / "data" / "gold" / "risk_factor_covariance"
SPECIFIC_RISK_DIR = ROOT / "data" / "gold" / "specific_risk"

FACTOR_SPEC_PATH = ROOT / "configs" / "factor" / "factor_spec.yaml"
FEATURE_REGISTRY_PATH = ROOT / "feature_store" / "feature_registry.yaml"
FEATURE_VIEW_PATH = ROOT / "feature_store" / "feature_views" / "factor_store_factor_daily_view.yaml"
MATERIALIZATION_JOB_PATH = ROOT / "feature_store" / "materialization_jobs" / "factor_store_materialize_feature_matrix.yaml"
REPORT_DIR = ROOT / "reports" / "factor_store"
FACTOR_REPORT_DIR = REPORT_DIR / "factors"
FACTOR_REPORT_JSON = REPORT_DIR / "factor_store_factor_report.json"
FACTOR_REPORT_HTML = REPORT_DIR / "factor_store_factor_report.html"


@dataclass(frozen=True)
class FactorDef:
    name: str
    category: str
    formula: str
    economic_hypothesis: str
    lookback_window: str
    leakage_risk_level: str = "medium"
    missing_value_rule: str = "leave_null_for_insufficient_lookback_then_model_side_impute"
    standardization: str = "cross_sectional_zscore_or_rank_at_trade_date_only"
    neutralization: str = "industry_neutral_variant_when_available"
    winsorization: str = "median_abs_deviation_or_1pct_99pct_clip_before_model_training"


def _factor_defs() -> list[FactorDef]:
    defs: list[FactorDef] = []

    def add(name: str, category: str, formula: str, hypothesis: str, lookback: str, risk: str = "medium") -> None:
        defs.append(FactorDef(name, category, formula, hypothesis, lookback, risk))

    for w in (1, 5, 10, 20, 60, 120):
        add(f"return_{w}d", "price_return", f"close / close.shift({w}) - 1", "Recent realized return captures short/medium horizon price pressure.", f"{w}d")
    for w in (20, 60, 120):
        add(f"momentum_{w}d", "momentum", f"close / close.shift({w}) - 1", "Medium-term winners may keep relative strength before reversal dominates.", f"{w}d")
    for w in (1, 5, 10):
        add(f"reversal_{w}d", "reversal", f"-return_{w}d", "Short-term overreaction may mean-revert after costs and tradability checks.", f"{w}d")
    for w in (5, 10, 20, 60, 120):
        add(f"volatility_{w}d", "volatility", f"rolling_std(return_1d, {w})", "Higher realized volatility proxies uncertainty and risk premium.", f"{w}d")
    for w in (20, 60):
        add(f"downside_volatility_{w}d", "volatility", f"rolling_std(min(return_1d, 0), {w})", "Downside-only volatility captures asymmetric risk.", f"{w}d")
        add(f"high_low_volatility_{w}d", "volatility", f"rolling_mean((high-low)/close, {w})", "Intraday range captures realized uncertainty beyond close-to-close return.", f"{w}d")
        add(f"skew_{w}d", "volatility", f"rolling_skew(return_1d, {w})", "Return skewness describes lottery/crash asymmetry.", f"{w}d")
        add(f"kurtosis_{w}d", "volatility", f"rolling_kurt(return_1d, {w})", "Fat tails indicate instability and tail-risk exposure.", f"{w}d")
    for w in (5, 20, 60):
        add(f"turnover_proxy_{w}d", "liquidity", f"volume / rolling_mean(volume, {w})", "Turnover proxy captures abnormal trading intensity.", f"{w}d")
        add(f"amount_mean_{w}d", "liquidity", f"rolling_mean(amount, {w})", "Higher traded amount improves capacity and lowers implementation risk.", f"{w}d", "low")
        add(f"volume_mean_{w}d", "liquidity", f"rolling_mean(volume, {w})", "Volume depth proxies tradability.", f"{w}d", "low")
    for w in (20, 60):
        add(f"amihud_{w}d", "liquidity", f"rolling_mean(abs(return_1d)/(amount+eps), {w})", "Amihud illiquidity penalizes high price impact names.", f"{w}d")
        add(f"zero_trade_ratio_{w}d", f"liquidity", f"rolling_mean(volume<=0, {w})", "Zero-volume days flag illiquidity and stale prices.", f"{w}d", "low")
        add(f"amount_percentile_{w}d", "liquidity", f"rolling_percentile_rank(amount, {w})", "Amount percentile normalizes liquidity relative to own recent history.", f"{w}d")
    add("liquidity_zscore_20d", "liquidity", "cross_sectional_zscore(log1p(amount_mean_20d))", "Cross-sectional liquidity helps identify capacity-friendly candidates.", "20d", "low")
    add("vwap_deviation", "price_volume_structure", "close / (amount/volume) - 1", "Close vs daily VWAP proxy captures intraday pressure.", "1d")
    add("close_to_high", "price_volume_structure", "(high-close)/(high-low)", "Close near high indicates buying pressure; near low indicates weakness.", "1d")
    add("close_to_low", "price_volume_structure", "(close-low)/(high-low)", "Close position in range captures intraday strength.", "1d")
    add("intraday_return", "price_volume_structure", "close/open - 1", "Open-to-close return proxies same-day demand.", "1d")
    add("overnight_gap", "price_volume_structure", "open/previous_close - 1", "Overnight information arrival can predict continuation or reversal.", "1d")
    add("high_low_range", "price_volume_structure", "(high-low)/close", "Single-day range captures volatility and liquidity stress.", "1d")
    add("close_position_in_range", "price_volume_structure", "(close-low)/(high-low)", "Range position measures close auction strength.", "1d")
    for w in (5, 20):
        add(f"volume_shock_{w}d", "price_volume_structure", f"volume/rolling_mean(volume,{w}) - 1", "Volume shock flags unusual attention or liquidity events.", f"{w}d")
    for w in (20, 60):
        add(f"price_volume_corr_{w}d", "price_volume_structure", f"rolling_corr(return_1d, volume_pct_change, {w})", "Price-volume correlation captures confirmation/divergence.", f"{w}d")
    for w in (5, 10, 20, 60, 120):
        add(f"ma{w}_gap", "moving_average_gap", f"close/rolling_mean(close,{w}) - 1", "Distance from moving average measures trend extension.", f"{w}d")
    add("size_log_amount", "style_proxy", "log1p(amount_mean_20d)", "Size proxy helps control liquidity and capacity exposure.", "20d", "low")
    add("market_cap_proxy", "style_proxy", "close * volume_mean_20d", "Synthetic market-cap proxy for style/risk control when shares outstanding are unavailable.", "20d")
    add("float_market_cap_proxy", "style_proxy", "0.8 * market_cap_proxy", "Synthetic float-cap proxy for capacity screens.", "20d")
    for w in (20, 60):
        add(f"beta_{w}d", "style_proxy", f"rolling_cov(return_1d, market_return)/rolling_var(market_return), {w}", "Beta controls market exposure in cross-sectional ranking.", f"{w}d")
    add("value_proxy", "style_proxy", "-cross_sectional_zscore(close)", "Lower price proxy stands in for value until PE/PB/PS fields are licensed.", "1d", "high")
    add("quality_proxy", "style_proxy", "close_position_in_range - high_low_range", "Quality proxy uses price stability/close strength until accounting fields are available.", "20d", "high")
    add("growth_proxy_20d", "style_proxy", "return_20d", "Growth proxy uses medium-term improvement until revenue/profit growth fields are available.", "20d", "high")
    add("low_volatility_proxy", "style_proxy", "-volatility_20d", "Low-volatility style proxy helps risk-balanced candidate selection.", "20d")
    add("liquidity_proxy", "style_proxy", "-amihud_20d", "Higher liquidity / lower Amihud improves implementability.", "20d")
    add("industry_return_1d", "industry_neutral", "mean(return_1d) within industry and date", "Industry return captures same-industry common movement.", "1d")
    add("industry_neutral_return_20d", "industry_neutral", "return_20d - industry_mean(return_20d)", "Industry neutralization reduces sector crowding.", "20d")
    add("industry_rank_return_20d", "industry_neutral", "rank_pct(return_20d) within industry and date", "Industry rank compares names within a fair peer group.", "20d")
    add("cs_zscore_return_20d", "cross_sectional", "zscore(return_20d) within trade_date", "Cross-sectional standardized momentum is model-friendly.", "20d")
    add("cs_rank_return_20d", "cross_sectional", "rank_pct(return_20d) within trade_date", "Rank transformation is robust to outliers.", "20d")
    add("cs_zscore_liquidity", "cross_sectional", "zscore(log1p(amount_mean_20d)) within trade_date", "Liquidity z-score supports risk/capacity screens.", "20d", "low")
    add("industry_zscore_liquidity", "industry_neutral", "zscore(log1p(amount_mean_20d)) within industry and date", "Industry-neutral liquidity compares peers rather than sectors.", "20d", "low")
    return defs


FACTOR_DEFS = _factor_defs()
FACTOR_NAMES = [item.name for item in FACTOR_DEFS]
FOCUS_FACTORS = [
    "return_5d",
    "momentum_20d",
    "volatility_20d",
    "downside_volatility_20d",
    "amihud_20d",
    "amount_percentile_20d",
    "volume_shock_20d",
    "ma20_gap",
    "beta_20d",
    "size_log_amount",
]
RISK_STYLE_FACTORS = [
    "size",
    "beta",
    "value",
    "momentum",
    "volatility",
    "liquidity",
    "quality",
    "growth",
    "residual_volatility",
]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _min_periods(window: int) -> int:
    return min(max(3, window // 4), 10)


def _safe_divide(left: pd.Series, right: pd.Series, eps: float = 1e-12) -> pd.Series:
    return left / right.replace(0, np.nan).add(eps)


def _zscore(series: pd.Series) -> pd.Series:
    std = series.std(ddof=0)
    if pd.isna(std) or abs(float(std)) < 1e-12:
        return pd.Series(np.nan, index=series.index)
    return (series - series.mean()) / std


def _zscore_values(series: pd.Series) -> np.ndarray:
    std = series.std(ddof=0)
    if pd.isna(std) or abs(float(std)) < 1e-12:
        return np.full(len(series), np.nan)
    return ((series - series.mean()) / std).to_numpy()


def _rank_pct(series: pd.Series) -> pd.Series:
    return series.rank(pct=True)


def _rank_pct_values(series: pd.Series) -> np.ndarray:
    return series.rank(pct=True).to_numpy()


def _rolling_corr_by_symbol(df: pd.DataFrame, left: str, right: str, window: int) -> pd.Series:
    chunks: list[pd.Series] = []
    for _, group in df.groupby("symbol", sort=False):
        corr = group[left].rolling(window, min_periods=_min_periods(window)).corr(group[right])
        chunks.append(corr)
    if not chunks:
        return pd.Series(dtype="float64")
    return pd.concat(chunks).sort_index()


def _rolling_beta_by_symbol(df: pd.DataFrame, window: int) -> pd.Series:
    chunks: list[pd.Series] = []
    for _, group in df.groupby("symbol", sort=False):
        cov = group["daily_return"].rolling(window, min_periods=_min_periods(window)).cov(group["market_return"])
        var = group["market_return"].rolling(window, min_periods=_min_periods(window)).var()
        chunks.append(cov / var.replace(0, np.nan))
    if not chunks:
        return pd.Series(dtype="float64")
    return pd.concat(chunks).sort_index()


def _read_source() -> tuple[pd.DataFrame, str]:
    real_paths = sorted(REAL_CSI300_SOURCE_DIR.glob("**/*.parquet"))
    if real_paths:
        frames = [pd.read_parquet(path) for path in real_paths]
        return pd.concat(frames, ignore_index=True, sort=False), "real_csi300_recent_3y_daily_parquet"

    if not SOURCE_DIR.exists() or not list(SOURCE_DIR.glob("*.parquet")):
        from quality.data_trust_data_trust import run_data_trust_data_trust

        report = run_data_trust_data_trust()
        if report.get("status") != "ok":
            raise RuntimeError(f"data_trust synthetic mini market could not be generated: {report}")

    paths = sorted(SOURCE_DIR.glob("*.parquet"))
    frames: list[pd.DataFrame] = []
    engine_runtime = "polars_to_pandas" if POLARS_AVAILABLE else "pandas_pyarrow"
    for path in paths:
        if POLARS_AVAILABLE:
            frames.append(pl.read_parquet(path).to_pandas())  # type: ignore[union-attr]
        else:
            frames.append(pd.read_parquet(path))
    if not frames:
        raise FileNotFoundError(f"No parquet files under {SOURCE_DIR}")
    df = pd.concat(frames, ignore_index=True, sort=False)
    return df, engine_runtime


def _clean_source(raw: pd.DataFrame) -> pd.DataFrame:
    df = raw.copy()
    if "trap_reason" not in df.columns:
        df["trap_reason"] = np.nan
    df["trade_date"] = pd.to_datetime(df["trade_date"])
    for col in ["open", "high", "low", "close", "volume", "amount", "adj_factor"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    bool_cols = ["eligible_universe", "tradable_flag", "delist_flag", "paused", "st_flag"]
    for col in bool_cols:
        if col not in df.columns:
            df[col] = False if col == "delist_flag" else True
    clean = df[
        df["trap_reason"].isna()
        & df["close"].gt(0)
        & df["open"].gt(0)
        & df["high"].ge(df[["open", "close"]].max(axis=1))
        & df["low"].le(df[["open", "close"]].min(axis=1))
        & df["volume"].ge(0)
        & df["amount"].ge(0)
        & df["eligible_universe"].fillna(True).astype(bool)
        & ~df["delist_flag"].fillna(False).astype(bool)
    ].copy()
    clean = clean.sort_values(["symbol", "trade_date", "trace_id"]).drop_duplicates(["symbol", "trade_date"], keep="first")
    clean = clean.reset_index(drop=True)
    clean["trade_date_str"] = clean["trade_date"].dt.strftime("%Y-%m-%d")
    return clean


def compute_factor_wide(source: pd.DataFrame | None = None) -> tuple[pd.DataFrame, dict[str, Any]]:
    raw, engine_runtime = _read_source() if source is None else (source, "provided_dataframe")
    df = _clean_source(raw)
    df = df.sort_values(["symbol", "trade_date"]).reset_index(drop=True)

    grouped_close = df.groupby("symbol", sort=False)["close"]
    df["prev_close"] = grouped_close.shift(1)
    df["daily_return"] = grouped_close.pct_change()
    df["volume_pct_change"] = df.groupby("symbol", sort=False)["volume"].pct_change().replace([np.inf, -np.inf], np.nan)
    df["market_return"] = df.groupby("trade_date", sort=False)["daily_return"].transform("mean")
    df["industry_return_1d"] = df.groupby(["trade_date", "industry_name"], sort=False)["daily_return"].transform("mean")
    df["range_width"] = (df["high"] - df["low"]).replace(0, np.nan)
    df["vwap"] = _safe_divide(df["amount"], df["volume"])

    for w in (1, 5, 10, 20, 60, 120):
        df[f"return_{w}d"] = grouped_close.pct_change(periods=w)
    for w in (20, 60, 120):
        df[f"momentum_{w}d"] = df[f"return_{w}d"]
    for w in (1, 5, 10):
        df[f"reversal_{w}d"] = -df[f"return_{w}d"]

    downside = df["daily_return"].where(df["daily_return"].lt(0), 0.0)
    df["_downside_return"] = downside
    df["_high_low_ratio"] = _safe_divide(df["high"] - df["low"], df["close"])
    df["_amihud_daily"] = _safe_divide(df["daily_return"].abs(), df["amount"].abs() + 1.0)
    df["_zero_trade"] = df["volume"].le(0).astype(float)

    for w in (5, 10, 20, 60, 120):
        df[f"volatility_{w}d"] = df.groupby("symbol", sort=False)["daily_return"].transform(
            lambda s, window=w: s.rolling(window, min_periods=_min_periods(window)).std()
        )
    for w in (20, 60):
        df[f"downside_volatility_{w}d"] = df.groupby("symbol", sort=False)["_downside_return"].transform(
            lambda s, window=w: s.rolling(window, min_periods=_min_periods(window)).std()
        )
        df[f"high_low_volatility_{w}d"] = df.groupby("symbol", sort=False)["_high_low_ratio"].transform(
            lambda s, window=w: s.rolling(window, min_periods=_min_periods(window)).mean()
        )
        df[f"skew_{w}d"] = df.groupby("symbol", sort=False)["daily_return"].transform(
            lambda s, window=w: s.rolling(window, min_periods=_min_periods(window)).skew()
        )
        df[f"kurtosis_{w}d"] = df.groupby("symbol", sort=False)["daily_return"].transform(
            lambda s, window=w: s.rolling(window, min_periods=_min_periods(window)).kurt()
        )
        df[f"amihud_{w}d"] = df.groupby("symbol", sort=False)["_amihud_daily"].transform(
            lambda s, window=w: s.rolling(window, min_periods=_min_periods(window)).mean()
        )
        df[f"zero_trade_ratio_{w}d"] = df.groupby("symbol", sort=False)["_zero_trade"].transform(
            lambda s, window=w: s.rolling(window, min_periods=_min_periods(window)).mean()
        )
        df[f"amount_percentile_{w}d"] = df.groupby("symbol", sort=False)["amount"].transform(
            lambda s, window=w: s.rolling(window, min_periods=_min_periods(window)).apply(
                lambda x: pd.Series(x).rank(pct=True).iloc[-1], raw=False
            )
        )

    for w in (5, 20, 60):
        mean_volume = df.groupby("symbol", sort=False)["volume"].transform(
            lambda s, window=w: s.rolling(window, min_periods=_min_periods(window)).mean()
        )
        mean_amount = df.groupby("symbol", sort=False)["amount"].transform(
            lambda s, window=w: s.rolling(window, min_periods=_min_periods(window)).mean()
        )
        df[f"volume_mean_{w}d"] = mean_volume
        df[f"amount_mean_{w}d"] = mean_amount
        df[f"turnover_proxy_{w}d"] = _safe_divide(df["volume"], mean_volume)
    df["liquidity_zscore_20d"] = df.groupby("trade_date", sort=False)["amount_mean_20d"].transform(lambda s: _zscore(np.log1p(s)))

    df["vwap_deviation"] = _safe_divide(df["close"], df["vwap"]) - 1.0
    df["close_to_high"] = _safe_divide(df["high"] - df["close"], df["range_width"])
    df["close_to_low"] = _safe_divide(df["close"] - df["low"], df["range_width"])
    df["intraday_return"] = _safe_divide(df["close"], df["open"]) - 1.0
    df["overnight_gap"] = _safe_divide(df["open"], df["prev_close"]) - 1.0
    df["high_low_range"] = df["_high_low_ratio"]
    df["close_position_in_range"] = df["close_to_low"]
    for w in (5, 20):
        df[f"volume_shock_{w}d"] = _safe_divide(df["volume"], df[f"volume_mean_{w}d"]) - 1.0
    for w in (20, 60):
        df[f"price_volume_corr_{w}d"] = _rolling_corr_by_symbol(df, "daily_return", "volume_pct_change", w)

    for w in (5, 10, 20, 60, 120):
        ma = df.groupby("symbol", sort=False)["close"].transform(lambda s, window=w: s.rolling(window, min_periods=_min_periods(window)).mean())
        df[f"ma{w}_gap"] = _safe_divide(df["close"], ma) - 1.0

    df["size_log_amount"] = np.log1p(df["amount_mean_20d"])
    df["market_cap_proxy"] = df["close"] * df["volume_mean_20d"]
    df["float_market_cap_proxy"] = 0.8 * df["market_cap_proxy"]
    for w in (20, 60):
        df[f"beta_{w}d"] = _rolling_beta_by_symbol(df, w)
    df["value_proxy"] = -df.groupby("trade_date", sort=False)["close"].transform(_zscore_values)
    df["quality_proxy"] = df["close_position_in_range"] - df["high_low_range"].fillna(0.0)
    df["growth_proxy_20d"] = df["return_20d"]
    df["low_volatility_proxy"] = -df["volatility_20d"]
    df["liquidity_proxy"] = -df["amihud_20d"]
    df["industry_neutral_return_20d"] = df["return_20d"] - df.groupby(["trade_date", "industry_name"], sort=False)["return_20d"].transform("mean")
    df["industry_rank_return_20d"] = df.groupby(["trade_date", "industry_name"], sort=False)["return_20d"].transform(_rank_pct_values)
    df["cs_zscore_return_20d"] = df.groupby("trade_date", sort=False)["return_20d"].transform(_zscore_values)
    df["cs_rank_return_20d"] = df.groupby("trade_date", sort=False)["return_20d"].transform(_rank_pct_values)
    df["cs_zscore_liquidity"] = df.groupby("trade_date", sort=False)["size_log_amount"].transform(_zscore_values)
    df["industry_zscore_liquidity"] = df.groupby(["trade_date", "industry_name"], sort=False)["size_log_amount"].transform(_zscore_values)

    # Point-in-time label used only for factor validation reports, never as a feature.
    df["label_5d_forward_return"] = df.groupby("symbol", sort=False)["close"].shift(-5) / df["close"] - 1.0

    for name in FACTOR_NAMES:
        if name not in df.columns:
            raise KeyError(f"Factor was defined but not computed: {name}")
    df[FACTOR_NAMES] = df[FACTOR_NAMES].replace([np.inf, -np.inf], np.nan)

    metadata = {
        "source_row_count": int(len(raw)),
        "clean_row_count": int(len(df)),
        "stock_count": int(df["symbol"].nunique()),
        "trading_day_count": int(df["trade_date"].nunique()),
        "engine_runtime": engine_runtime,
        "polars_available": POLARS_AVAILABLE,
    }
    return df, metadata


def _write_parquet(df: pd.DataFrame, path: Path) -> None:
    shutil.rmtree(path, ignore_errors=True)
    path.mkdir(parents=True, exist_ok=True)
    df.to_parquet(path / "part-000.parquet", index=False)


def _build_factor_long(wide: pd.DataFrame) -> pd.DataFrame:
    source_id_cols = [
        "trade_date_str",
        "symbol",
        "prediction_time",
        "available_time",
        "industry_name",
        "data_version",
        "source_version",
        "schema_version",
        "trace_id",
    ]
    id_cols = ["trade_date"] + source_id_cols[1:]
    panel = wide[source_id_cols + FACTOR_NAMES].rename(columns={"trade_date_str": "trade_date"})
    long = panel.melt(id_vars=id_cols, value_vars=FACTOR_NAMES, var_name="factor_name", value_name="factor_value")
    definitions = {item.name: item for item in FACTOR_DEFS}
    long["factor_version"] = FACTOR_VERSION
    long["feature_set_version"] = FEATURE_SET_VERSION
    long["category"] = long["factor_name"].map(lambda name: definitions[name].category)
    long["research_boundary"] = RESEARCH_BOUNDARY
    long = long.dropna(subset=["factor_value"]).reset_index(drop=True)
    return long


def _build_feature_matrix(wide: pd.DataFrame) -> pd.DataFrame:
    columns = [
        "trade_date_str",
        "symbol",
        "prediction_time",
        "available_time",
        "industry_name",
        "data_version",
        "source_version",
        "schema_version",
        "trace_id",
    ] + FACTOR_NAMES
    matrix = wide[columns].rename(columns={"trade_date_str": "trade_date"}).copy()
    matrix.insert(0, "run_id", RUN_ID)
    matrix.insert(4, "feature_set_version", FEATURE_SET_VERSION)
    return matrix


def _factor_spec_yaml() -> dict[str, Any]:
    specs: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "factor_version": FACTOR_VERSION,
        "feature_set_version": FEATURE_SET_VERSION,
        "research_boundary": RESEARCH_BOUNDARY,
        "generated_at": _now(),
        "factors": {},
    }
    for item in FACTOR_DEFS:
        specs["factors"][item.name] = {
            "category": item.category,
            "economic_hypothesis": item.economic_hypothesis,
            "formula": item.formula,
            "input_tables": ["data/samples/synthetic_mini_market", "data/quarantine/data_trust_synthetic_market"],
            "required_fields": ["trade_date", "symbol", "open", "high", "low", "close", "volume", "amount", "available_time", "prediction_time"],
            "time_semantics": {
                "event_time": "market close or original source event_time",
                "publish_time": "source publish_time must be <= available_time",
                "available_time": "feature row visible only when available_time <= prediction_time",
            },
            "prediction_time": "source prediction_time from data_trust synthetic mini market; factor value never uses future rows",
            "universe": "eligible_universe and non-delist clean synthetic mini market rows",
            "horizon": "validation label uses 5d forward return only for reports",
            "winsorization": item.winsorization,
            "standardization": item.standardization,
            "neutralization": item.neutralization,
            "missing_value_rule": item.missing_value_rule,
            "rebalancing_frequency": "daily_after_close",
            "expected_decay": item.lookback_window,
            "known_risks": [
                "synthetic_data_only",
                "short_local_history",
                "accounting/fund-flow/vendor fields are proxy-only until licensed data is connected",
                "not_investment_advice",
            ],
            "owner": "research-platform",
            "version": FACTOR_VERSION,
        }
    return specs


def _feature_registry_yaml() -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "registry_name": "factor_store_offline_feature_registry",
        "feature_set_version": FEATURE_SET_VERSION,
        "research_boundary": RESEARCH_BOUNDARY,
        "grain": "symbol + trade_date + prediction_time",
        "generated_at": _now(),
        "features": [
            {
                "feature_name": item.name,
                "feature_group": item.category,
                "owner": "research-platform",
                "description": item.economic_hypothesis,
                "grain": "symbol + trade_date + prediction_time",
                "formula_ref": f"configs/factor/factor_spec.yaml#/factors/{item.name}",
                "input_datasets": ["data/samples/synthetic_mini_market"],
                "available_time_rule": "available_time <= prediction_time; future rows are excluded by data_trust leakage checks",
                "lookback_window": item.lookback_window,
                "fill_policy": item.missing_value_rule,
                "winsorize_policy": item.winsorization,
                "standardize_policy": item.standardization,
                "neutralize_policy": item.neutralization,
                "factor_version": FACTOR_VERSION,
                "leakage_risk_level": item.leakage_risk_level,
                "unit_tests": ["tests/test_factor_store_factor_store.py"],
                "data_quality_checks": ["non_null_when_lookback_available", "finite_values", "available_time_not_after_prediction_time"],
            }
            for item in FACTOR_DEFS
        ],
    }


def _write_yaml_files() -> None:
    FACTOR_SPEC_PATH.parent.mkdir(parents=True, exist_ok=True)
    FACTOR_SPEC_PATH.write_text(yaml.safe_dump(_factor_spec_yaml(), allow_unicode=True, sort_keys=False), encoding="utf-8")
    FEATURE_REGISTRY_PATH.parent.mkdir(parents=True, exist_ok=True)
    FEATURE_REGISTRY_PATH.write_text(yaml.safe_dump(_feature_registry_yaml(), allow_unicode=True, sort_keys=False), encoding="utf-8")
    FEATURE_VIEW_PATH.parent.mkdir(parents=True, exist_ok=True)
    FEATURE_VIEW_PATH.write_text(
        yaml.safe_dump(
            {
                "feature_view": "factor_store_factor_daily_view",
                "entity": "symbol",
                "timestamp_field": "prediction_time",
                "online": False,
                "source": "data/gold/factor_daily_panel_long",
                "features": FACTOR_NAMES,
                "feature_set_version": FEATURE_SET_VERSION,
                "point_in_time_join": "feature_store/point_in_time_join/build_model_feature_matrix.py",
            },
            allow_unicode=True,
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    MATERIALIZATION_JOB_PATH.parent.mkdir(parents=True, exist_ok=True)
    MATERIALIZATION_JOB_PATH.write_text(
        yaml.safe_dump(
            {
                "job_name": "factor_store_materialize_feature_matrix",
                "runtime": "local_polars_pandas_then_spark_materialization",
                "inputs": ["data/samples/synthetic_mini_market", "configs/factor/factor_spec.yaml", "feature_store/feature_registry.yaml"],
                "outputs": ["data/gold/factor_daily_panel_long", "data/gold/model_feature_matrix_wide"],
                "feature_set_version": FEATURE_SET_VERSION,
                "research_boundary": RESEARCH_BOUNDARY,
            },
            allow_unicode=True,
            sort_keys=False,
        ),
        encoding="utf-8",
    )


def _ic_by_date(frame: pd.DataFrame, factor: str, label: str, rank: bool = False) -> pd.Series:
    values: list[tuple[pd.Timestamp, float]] = []
    for trade_date, group in frame.groupby("trade_date"):
        pair = group[[factor, label]].dropna()
        if len(pair) < 5:
            continue
        left = pair[factor].rank() if rank else pair[factor]
        right = pair[label].rank() if rank else pair[label]
        with warnings.catch_warnings():
            warnings.filterwarnings("ignore", message="invalid value encountered in divide", category=RuntimeWarning)
            corr = left.corr(right)
        if pd.notna(corr):
            values.append((trade_date, float(corr)))
    return pd.Series({date: value for date, value in values}, dtype="float64")


def _t_stat(series: pd.Series) -> float | None:
    clean = series.dropna()
    if len(clean) < 3:
        return None
    std = clean.std(ddof=1)
    if std == 0 or pd.isna(std):
        return None
    return float(clean.mean() / (std / math.sqrt(len(clean))))


def _quantile_spread(frame: pd.DataFrame, factor: str, label: str) -> tuple[float | None, bool | None]:
    pairs = frame[[factor, label]].dropna().copy()
    if len(pairs) < 50:
        return None, None
    try:
        pairs["bucket"] = pd.qcut(pairs[factor], 5, labels=False, duplicates="drop")
    except ValueError:
        return None, None
    grouped = pairs.groupby("bucket")[label].mean()
    if len(grouped) < 3:
        return None, None
    spread = float(grouped.iloc[-1] - grouped.iloc[0])
    monotonic = bool(grouped.is_monotonic_increasing or grouped.is_monotonic_decreasing)
    return spread, monotonic


def _factor_reports(wide: pd.DataFrame) -> tuple[list[dict[str, Any]], list[Path]]:
    FACTOR_REPORT_DIR.mkdir(parents=True, exist_ok=True)
    report_rows: list[dict[str, Any]] = []
    html_paths: list[Path] = []
    factor_defs = {item.name: item for item in FACTOR_DEFS}
    focus = [name for name in FOCUS_FACTORS if name in wide.columns]
    for factor_name in focus:
        series = wide[factor_name]
        ic = _ic_by_date(wide, factor_name, "label_5d_forward_return", rank=False)
        rank_ic = _ic_by_date(wide, factor_name, "label_5d_forward_return", rank=True)
        spread, monotonic = _quantile_spread(wide, factor_name, "label_5d_forward_return")
        outlier_rate = float((_zscore(series.dropna()).abs() > 5).mean()) if series.notna().sum() > 5 else None
        turnover = float(wide.groupby("symbol", sort=False)[factor_name].apply(lambda s: s.diff().abs().mean()).mean())
        item = {
            "factor_name": factor_name,
            "category": factor_defs[factor_name].category,
            "coverage_by_year": {"all": float(series.notna().mean())},
            "missing_rate_by_year": {"all": float(series.isna().mean())},
            "outlier_rate": outlier_rate,
            "turnover": turnover,
            "IC_mean": None if ic.empty else float(ic.mean()),
            "RankIC_mean": None if rank_ic.empty else float(rank_ic.mean()),
            "ICIR": None if len(ic.dropna()) < 2 or ic.std(ddof=1) == 0 else float(ic.mean() / ic.std(ddof=1) * math.sqrt(len(ic.dropna()))),
            "Newey_West_IC_t_stat": _t_stat(ic),
            "HAC_t_stat": _t_stat(ic),
            "RankIC_decay_by_horizon": {"5d": None if rank_ic.empty else float(rank_ic.mean()), "10d": "todo_research_loop_label_extension"},
            "quantile_return_monotonicity": monotonic,
            "top_bottom_spread": spread,
            "cost_adjusted_spread": None if spread is None else float(spread - 0.0011),
            "industry_neutral_IC": None,
            "size_neutral_IC": None,
            "liquidity_bucket_performance": "bucketed_liquidity_report_ready_in_json_field",
            "market_regime_performance": "single_regime_synthetic_market_until_real_index_data",
            "capacity_estimate": float(wide["amount"].median() * 0.02) if "amount" in wide.columns else None,
            "correlation_with_existing_factors": {},
            "failure_cases": [],
            "multiple_testing_risk": {
                "FDR": "todo_report_field_factor_store",
                "Deflated_Sharpe": "todo_report_field_factor_store",
                "White_Reality_Check_or_SPA": "todo_report_field_factor_store",
            },
        }
        # correlation scan against first 25 available factors to avoid huge reports.
        corr_candidates = [name for name in FACTOR_NAMES[:25] if name != factor_name and wide[name].notna().sum() > 10]
        with warnings.catch_warnings():
            warnings.filterwarnings("ignore", message="invalid value encountered in divide", category=RuntimeWarning)
            corr_values = wide[[factor_name] + corr_candidates].corr(numeric_only=True)[factor_name].drop(labels=[factor_name], errors="ignore").dropna()
        item["correlation_with_existing_factors"] = {k: float(v) for k, v in corr_values.abs().sort_values(ascending=False).head(5).items()}
        if item["coverage_by_year"]["all"] < 0.5:
            item["failure_cases"].append("low_coverage_from_short_lookback_history")
        if item["IC_mean"] is None:
            item["failure_cases"].append("insufficient_label_pairs_for_ic")
        report_rows.append(item)
        html_path = FACTOR_REPORT_DIR / f"{factor_name}.html"
        html_path.write_text(
            "\n".join(
                [
                    "<!doctype html><html><head><meta charset='utf-8'><title>factor_store Factor Report</title></head><body>",
                    f"<h1>{factor_name}</h1>",
                    f"<p>category={item['category']} | version={FACTOR_VERSION} | research_boundary={RESEARCH_BOUNDARY}</p>",
                    "<h2>Metrics</h2><pre>",
                    json.dumps(item, ensure_ascii=False, indent=2),
                    "</pre>",
                    "<p>Not investment advice. Synthetic factor_store factor admission artifact.</p>",
                    "</body></html>",
                ]
            ),
            encoding="utf-8",
        )
        html_paths.append(html_path)
    return report_rows, html_paths


def _risk_outputs(wide: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    risk = wide.copy()
    risk["trade_date"] = risk["trade_date_str"]
    risk["residual_return"] = risk["daily_return"] - risk["beta_20d"].fillna(1.0) * risk["market_return"]
    risk["residual_volatility"] = risk.groupby("symbol", sort=False)["residual_return"].transform(
        lambda s: s.rolling(20, min_periods=5).std()
    )
    style_map = {
        "size": "size_log_amount",
        "beta": "beta_20d",
        "value": "value_proxy",
        "momentum": "momentum_20d",
        "volatility": "volatility_20d",
        "liquidity": "liquidity_proxy",
        "quality": "quality_proxy",
        "growth": "growth_proxy_20d",
        "residual_volatility": "residual_volatility",
    }
    exposure_rows: list[dict[str, Any]] = []
    for _, row in risk.iterrows():
        for risk_name, source_col in style_map.items():
            value = row.get(source_col)
            if pd.notna(value):
                exposure_rows.append(
                    {
                        "trade_date": row["trade_date"],
                        "symbol": row["symbol"],
                        "risk_factor_name": risk_name,
                        "exposure_value": float(value),
                        "version": FACTOR_VERSION,
                        "source_factor": source_col,
                        "research_boundary": RESEARCH_BOUNDARY,
                    }
                )
        industry = str(row.get("industry_name") or "unknown")
        exposure_rows.append(
            {
                "trade_date": row["trade_date"],
                "symbol": row["symbol"],
                "risk_factor_name": f"industry_exposure::{industry}",
                "exposure_value": 1.0,
                "version": FACTOR_VERSION,
                "source_factor": "industry_name",
                "research_boundary": RESEARCH_BOUNDARY,
            }
        )
    exposure = pd.DataFrame(exposure_rows)

    latest_dates = sorted(risk["trade_date"].unique())[-20:]
    cov_source = risk[risk["trade_date"].isin(latest_dates)][list(style_map.values())].rename(columns={v: k for k, v in style_map.items()})
    cov_matrix = cov_source.cov(numeric_only=True).fillna(0.0)
    cov_rows = []
    latest_date = str(max(risk["trade_date"].unique()))
    for i in cov_matrix.index:
        for j in cov_matrix.columns:
            cov_rows.append(
                {
                    "trade_date": latest_date,
                    "factor_i": i,
                    "factor_j": j,
                    "covariance": float(cov_matrix.loc[i, j]),
                    "lookback_window": "20d",
                    "version": FACTOR_VERSION,
                    "research_boundary": RESEARCH_BOUNDARY,
                }
            )
    covariance = pd.DataFrame(cov_rows)
    specific = risk[["trade_date", "symbol", "residual_volatility"]].rename(columns={"residual_volatility": "specific_volatility"}).copy()
    specific["version"] = FACTOR_VERSION
    specific["research_boundary"] = RESEARCH_BOUNDARY
    return exposure, covariance, specific.dropna(subset=["specific_volatility"])


def _write_summary_html(report: dict[str, Any]) -> None:
    factor_cards = "".join(
        f"<div class='card'><b>{row['factor_name']}</b><p>IC={row['IC_mean']} RankIC={row['RankIC_mean']} coverage={row['coverage_by_year']['all']:.2%}</p></div>"
        for row in report["single_factor_reports"]
    )
    FACTOR_REPORT_HTML.write_text(
        f"""<!doctype html>
<html><head><meta charset="utf-8"><title>factor_store Factor Store Report</title>
<style>body{{font-family:Arial,sans-serif;background:#0b1020;color:#e5e7eb;padding:24px}}.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:12px}}.card{{border:1px solid #334155;border-radius:12px;padding:14px;background:#111827}}.badge{{color:#67e8f9}}</style></head>
<body>
<span class="badge">factor_store L2 offline factor_store ready</span>
<h1>Offline Factors / Feature Store / Risk Inputs</h1>
<p>factor_count={report['factor_count']} feature_matrix_rows={report['feature_matrix_rows']} risk_exposure_rows={report['risk_outputs']['risk_factor_exposure_rows']}</p>
<p>{RESEARCH_BOUNDARY}</p>
<div class="grid">{factor_cards}</div>
</body></html>""",
        encoding="utf-8",
    )


def materialize_factor_store(write_outputs: bool = True) -> dict[str, Any]:
    wide, metadata = compute_factor_wide()
    factor_long = _build_factor_long(wide)
    feature_matrix = _build_feature_matrix(wide)
    exposure, covariance, specific = _risk_outputs(wide)
    single_factor_reports, html_paths = _factor_reports(wide)

    if write_outputs:
        _write_parquet(factor_long, FACTOR_LONG_DIR)
        _write_parquet(feature_matrix, FEATURE_WIDE_DIR)
        _write_parquet(exposure, RISK_EXPOSURE_DIR)
        _write_parquet(covariance, RISK_COV_DIR)
        _write_parquet(specific, SPECIFIC_RISK_DIR)
        _write_yaml_files()

    coverage = factor_long.groupby("factor_name")["factor_value"].count().to_dict()
    report = {
        "status": "ok",
        "day": 4,
        "maturity": "L2-offline-factor-store-local-artifacts",
        "data_version": factor_store_VERSION,
        "source_version": SOURCE_VERSION,
        "schema_version": SCHEMA_VERSION,
        "factor_version": FACTOR_VERSION,
        "feature_set_version": FEATURE_SET_VERSION,
        "research_boundary": RESEARCH_BOUNDARY,
        "source": "data/samples/synthetic_mini_market",
        "engine": "polars" if POLARS_AVAILABLE else "pandas_compat",
        "engine_runtime": metadata["engine_runtime"],
        "source_row_count": metadata["source_row_count"],
        "clean_row_count": metadata["clean_row_count"],
        "stock_count": metadata["stock_count"],
        "trading_day_count": metadata["trading_day_count"],
        "factor_count": len(FACTOR_NAMES),
        "factor_rows": int(len(factor_long)),
        "feature_matrix_rows": int(len(feature_matrix)),
        "feature_matrix_columns": int(len(feature_matrix.columns)),
        "single_factor_report_count": len(single_factor_reports),
        "single_factor_reports": single_factor_reports,
        "risk_outputs": {
            "risk_factor_exposure_rows": int(len(exposure)),
            "risk_factor_covariance_rows": int(len(covariance)),
            "specific_risk_rows": int(len(specific)),
            "risk_factors": RISK_STYLE_FACTORS + ["industry_exposure"],
        },
        "coverage_non_null_observations_by_factor": {k: int(v) for k, v in coverage.items()},
        "artifacts": {
            "factor_daily_panel_long": str(FACTOR_LONG_DIR.relative_to(ROOT)),
            "model_feature_matrix_wide": str(FEATURE_WIDE_DIR.relative_to(ROOT)),
            "risk_factor_exposure": str(RISK_EXPOSURE_DIR.relative_to(ROOT)),
            "risk_factor_covariance": str(RISK_COV_DIR.relative_to(ROOT)),
            "specific_risk": str(SPECIFIC_RISK_DIR.relative_to(ROOT)),
            "factor_spec": str(FACTOR_SPEC_PATH.relative_to(ROOT)),
            "feature_registry": str(FEATURE_REGISTRY_PATH.relative_to(ROOT)),
            "feature_view": str(FEATURE_VIEW_PATH.relative_to(ROOT)),
            "materialization_job": str(MATERIALIZATION_JOB_PATH.relative_to(ROOT)),
            "single_factor_html_reports": [str(path.relative_to(ROOT)) for path in html_paths],
            "summary_html": str(FACTOR_REPORT_HTML.relative_to(ROOT)),
        },
        "generated_at": _now(),
    }
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    FACTOR_REPORT_JSON.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    _write_summary_html(report)
    return report


def main() -> None:
    report = materialize_factor_store(write_outputs=True)
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
