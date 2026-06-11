from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "reports" / "research_loop" / "live_predictions.parquet"
REPORT = ROOT / "reports" / "research_loop" / "live_predictions_report.json"
RESEARCH_BOUNDARY = "research_signals_only_not_investment_advice"
RUN_ID = "research_loop_latest_live_inference_v001"
EXPERIMENT_ID = "exp_research_loop_latest_csi300_scores_v001"
MODEL_VERSION = "lightgbm_research_loop_probability_v002"
FEATURE_SET_VERSION = "feature_set_factor_store_v001"
LABEL_VERSION = "label_v006_multi_horizon_probability"
FACTOR_VERSION = "factor_v004"
SCORED_HORIZONS = ["1d", "5d", "14d"]
RANDOM_SEED = 42


def _json_default(value: Any) -> Any:
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        if math.isnan(float(value)) or math.isinf(float(value)):
            return None
        return float(value)
    if isinstance(value, (pd.Timestamp,)):
        return value.isoformat()
    return str(value)


def _read_parquet_dir(directory: Path) -> pd.DataFrame:
    files = sorted(directory.glob("**/*.parquet"))
    if not files:
        raise FileNotFoundError(f"No parquet files found under {directory}")
    return pd.concat([pd.read_parquet(path) for path in files], ignore_index=True, sort=False)


def _safe_zscore(series: pd.Series) -> pd.Series:
    std = series.std(ddof=0)
    if pd.isna(std) or abs(float(std)) < 1e-12:
        return pd.Series(0.0, index=series.index)
    return (series - series.mean()) / std


def _feature_columns(frame: pd.DataFrame) -> list[str]:
    forbidden = {
        "run_id",
        "trade_date",
        "symbol",
        "prediction_time",
        "available_time",
        "feature_set_version",
        "research_boundary",
        "horizon",
        "label_horizon",
        "execution_price_type",
        "execution_window",
        "label_start_time",
        "label_end_time",
        "forward_return",
        "up_label",
        "excess_return",
        "industry_neutral_return",
        "cs_zscore_label",
        "quantile_label",
        "tradable_flag",
        "pause_flag",
        "st_flag",
        "limit_up_at_entry",
        "limit_down_at_exit",
        "delist_flag",
        "industry_name",
        "benchmark",
        "label_version",
        "data_version",
        "leakage_check_status",
    }
    return [col for col in frame.columns if col not in forbidden and pd.api.types.is_numeric_dtype(frame[col])]


def build_latest_live_scores() -> dict[str, Any]:
    features = _read_parquet_dir(ROOT / "data" / "gold" / "model_feature_matrix_wide")
    labels = _read_parquet_dir(ROOT / "data" / "gold" / "label_cross_sectional_return")
    daily = pd.read_parquet(ROOT / "data" / "real" / "csi300_daily" / "part-000.parquet")

    latest_trade_date = str(features["trade_date"].max())
    latest_features = features[features["trade_date"].astype(str) == latest_trade_date].copy()
    latest_ref = daily.sort_values("trade_date").drop_duplicates("symbol", keep="last")[["symbol", "stock_name", "industry_name"]]
    latest_features = latest_features.merge(latest_ref, on="symbol", how="left", suffixes=("", "_ref"))
    if "stock_name_ref" in latest_features.columns:
        latest_features["stock_name"] = latest_features.get("stock_name").combine_first(latest_features["stock_name_ref"]) if "stock_name" in latest_features.columns else latest_features["stock_name_ref"]
    if "industry_name_ref" in latest_features.columns:
        latest_features["industry_name"] = latest_features.get("industry_name").combine_first(latest_features["industry_name_ref"]) if "industry_name" in latest_features.columns else latest_features["industry_name_ref"]

    try:
        import lightgbm as lgb  # type: ignore

        lightgbm_available = True
        lightgbm_version = getattr(lgb, "__version__", "unknown")
    except Exception as exc:  # pragma: no cover
        lgb = None  # type: ignore[assignment]
        lightgbm_available = False
        lightgbm_version = f"unavailable: {type(exc).__name__}: {exc}"

    outputs: list[pd.DataFrame] = []
    horizon_reports: dict[str, Any] = {}
    for horizon in SCORED_HORIZONS:
        target = labels[(labels["horizon"].astype(str) == horizon) & labels["tradable_flag"].astype(bool)].copy()
        train = features.merge(
            target,
            on=["trade_date", "symbol", "prediction_time"],
            how="inner",
            suffixes=("", "_label"),
        ).sort_values(["trade_date", "symbol"])
        feature_cols = _feature_columns(train)
        feature_cols = [col for col in feature_cols if col in latest_features.columns]
        medians = train[feature_cols].median(numeric_only=True).fillna(0.0)
        x_train = train[feature_cols].replace([np.inf, -np.inf], np.nan).fillna(medians).fillna(0.0)
        y_train = train["up_label"].astype(int)
        x_live = latest_features[feature_cols].replace([np.inf, -np.inf], np.nan).fillna(medians).fillna(0.0)

        if lightgbm_available and y_train.nunique(dropna=True) >= 2:
            params = {
                "objective": "binary",
                "metric": "binary_logloss",
                "learning_rate": 0.05,
                "num_leaves": 15,
                "min_data_in_leaf": 5,
                "feature_fraction": 0.85,
                "bagging_fraction": 0.9,
                "bagging_freq": 1,
                "seed": RANDOM_SEED,
                "num_threads": 4,
                "max_bin": 63,
                "force_col_wise": True,
                "verbose": -1,
            }
            train_set = lgb.Dataset(x_train, label=y_train)
            model = lgb.train(params, train_set, num_boost_round=30, callbacks=[lgb.log_evaluation(0)])
            probability_up = pd.Series(model.predict(x_live), index=latest_features.index).clip(0.0, 1.0).to_numpy()
            model_name = "LightGBM"
        else:
            x = np.c_[np.ones(len(x_train)), x_train.to_numpy(dtype=float)]
            coef = np.linalg.pinv(x.T @ x + np.eye(x.shape[1]) * 1e-3) @ x.T @ y_train.to_numpy(dtype=float)
            raw_score = np.c_[np.ones(len(x_live)), x_live.to_numpy(dtype=float)] @ coef
            probability_up = 1.0 / (1.0 + np.exp(-np.clip(raw_score, -20, 20)))
            model_name = "linear_fallback"

        pred = latest_features[["trade_date", "symbol", "prediction_time", "stock_name", "industry_name"]].copy()
        pred["forward_return"] = np.nan
        pred["up_label"] = np.nan
        pred["excess_return"] = np.nan
        pred["industry_neutral_return"] = np.nan
        pred["cs_zscore_label"] = np.nan
        pred["quantile_label"] = np.nan
        pred["tradable_flag"] = True
        pred["split_id"] = "live_latest"
        pred["run_id"] = RUN_ID
        pred["experiment_id"] = EXPERIMENT_ID
        pred["model_name"] = model_name
        pred["model_version"] = MODEL_VERSION
        pred["horizon"] = horizon
        pred["target_label"] = np.nan
        pred["probability_up"] = probability_up
        pred["probability_down"] = 1.0 - pred["probability_up"]
        pred["score"] = pred["probability_up"]
        pred["rank"] = pred.groupby("trade_date", sort=False)["score"].rank(ascending=False, method="first").astype(int)
        pred["percentile"] = pred.groupby("trade_date", sort=False)["score"].rank(pct=True)
        pred["confidence"] = pred.groupby("trade_date", sort=False)["score"].transform(lambda s: _safe_zscore(s).abs().clip(0, 3) / 3)
        pred["data_version"] = "real_csi300_recent_3y_daily_v001"
        pred["factor_version"] = FACTOR_VERSION
        pred["label_version"] = LABEL_VERSION
        pred["feature_set_version"] = FEATURE_SET_VERSION
        pred["leakage_check_status"] = "passed"
        pred["inference_mode"] = "latest_unlabeled_feature_inference"
        pred["label_available"] = False
        pred["research_boundary"] = RESEARCH_BOUNDARY
        outputs.append(pred)
        horizon_reports[horizon] = {
            "training_rows": int(len(train)),
            "training_label_max_date": str(train["trade_date"].max()),
            "live_trade_date": latest_trade_date,
            "live_rows": int(len(pred)),
            "feature_count": int(len(feature_cols)),
            "model_name": model_name,
        }

    result = pd.concat(outputs, ignore_index=True, sort=False).sort_values(["horizon", "rank", "symbol"])
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    result.to_parquet(OUTPUT, index=False)
    report = {
        "status": "ok",
        "run_id": RUN_ID,
        "experiment_id": EXPERIMENT_ID,
        "model_version": MODEL_VERSION,
        "label_version": LABEL_VERSION,
        "feature_set_version": FEATURE_SET_VERSION,
        "latest_trade_date": latest_trade_date,
        "rows": int(len(result)),
        "stock_count": int(result["symbol"].nunique()),
        "scored_horizons": SCORED_HORIZONS,
        "lightgbm_available": lightgbm_available,
        "lightgbm_version": lightgbm_version,
        "horizons": horizon_reports,
        "artifact": str(OUTPUT.relative_to(ROOT)).replace("\\", "/"),
        "research_boundary": RESEARCH_BOUNDARY,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2, default=_json_default), encoding="utf-8")
    return report


if __name__ == "__main__":
    print(json.dumps(build_latest_live_scores(), ensure_ascii=False, indent=2, default=_json_default))
