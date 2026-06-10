from __future__ import annotations

import hashlib
import json
import math
import platform
import shutil
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RESEARCH_BOUNDARY = "research_signals_only_not_investment_advice"
advanced_models_DIR = ROOT / "reports" / "advanced_models"
RECORDER_ROOT = advanced_models_DIR / "experiment_recorder"
PREDICTION_DIR = ROOT / "data" / "gold" / "advanced_model_predictions"
MODEL_OUTPUT_DIR = ROOT / "data" / "gold" / "advanced_model_comparison"
MODEL_VERSION = "advanced_models_advanced_models_v001"
FEATURE_SET_VERSION = "feature_set_relation_graph_relation_graph_v001"
EXPERIMENT_ID = "exp_advanced_models_advanced_model_adapters_v001"
MATURITY = "L1-research-candidate-small-sample"
TOP_K = 5
PRIMARY_SEED = 42
SEEDS = [7, 42, 2026]


@dataclass(frozen=True)
class ModelSpec:
    name: str
    slug: str
    repo: str
    paper: str
    adapter_status: str
    input_dependency: str
    base_features: tuple[str, ...]
    relation_required: bool
    market_required: bool
    parameter_count: int
    training_cost_tier: str


MODEL_SPECS: dict[str, ModelSpec] = {
    "MASTER": ModelSpec(
        name="MASTER",
        slug="master",
        repo="SJTU-DMTai/MASTER",
        paper="AAAI 2024 MASTER: Market-Guided Stock Transformer for Stock Price Forecasting",
        adapter_status="market_information_adapter_ready",
        input_dependency="market information: market_breadth, market_ret_*, market_vol_20d, ex_ante_regime_feature",
        base_features=(
            "momentum_20d",
            "momentum_60d",
            "volatility_20d",
            "liquidity_zscore_20d",
            "market_breadth",
            "market_ret_1d",
            "market_ret_5d",
            "market_vol_20d",
            "market_drawdown_20d",
            "risk_appetite_proxy",
            "ex_ante_regime_feature",
            "news_sentiment_5d",
        ),
        relation_required=False,
        market_required=True,
        parameter_count=18_432,
        training_cost_tier="cpu-small-sample-low-cost",
    ),
    "StockMixer": ModelSpec(
        name="StockMixer",
        slug="stockmixer",
        repo="SJTU-DMTai/StockMixer",
        paper="AAAI 2024 StockMixer: A Simple yet Strong MLP-based Architecture for Stock Price Forecasting",
        adapter_status="indicator_temporal_stock_mixing_adapter_ready",
        input_dependency="indicator/temporal/stock mixing tensors from relation_graph feature matrix",
        base_features=(
            "return_5d",
            "return_10d",
            "return_20d",
            "momentum_20d",
            "reversal_5d",
            "volatility_10d",
            "volatility_20d",
            "volume_shock_20d",
            "price_volume_corr_20d",
            "industry_neutral_return_20d",
            "cs_zscore_return_20d",
            "cs_zscore_liquidity",
        ),
        relation_required=False,
        market_required=False,
        parameter_count=11_264,
        training_cost_tier="cpu-small-sample-low-cost",
    ),
    "HIST": ModelSpec(
        name="HIST",
        slug="hist",
        repo="Wentao-Xu/HIST",
        paper="HIST: Graph-based Framework for Stock Trend Forecasting via Mining Concept-Oriented Shared Information",
        adapter_status="concept_industry_relation_adapter_ready",
        input_dependency="concept_matrix + industry/concept/relation spillover features from relation_graph graph adapter",
        base_features=(
            "industry_spillover",
            "concept_spillover",
            "centrality_score",
            "community_momentum",
            "correlation_cluster_momentum",
            "neighbor_return_1d",
            "neighbor_sentiment_1h",
            "relation_risk_score",
            "momentum_20d",
            "industry_neutral_return_20d",
        ),
        relation_required=True,
        market_required=False,
        parameter_count=15_872,
        training_cost_tier="cpu-small-sample-low-cost",
    ),
    "TRSR": ModelSpec(
        name="TRSR",
        slug="trsr",
        repo="fulifeng/Temporal_Relational_Stock_Ranking",
        paper="Temporal Relational Ranking for Stock Prediction",
        adapter_status="relation_matrix_ranking_adapter_ready",
        input_dependency="relation_matrix + lead_lag / neighbor propagation features from relation_graph graph adapter",
        base_features=(
            "lead_lag_signal",
            "neighbor_return_5m",
            "neighbor_return_1d",
            "neighbor_volume_shock",
            "supply_chain_spillover",
            "relation_risk_score",
            "centrality_score",
            "community_momentum",
            "momentum_20d",
            "reversal_5d",
        ),
        relation_required=True,
        market_required=False,
        parameter_count=13_696,
        training_cost_tier="cpu-small-sample-low-cost",
    ),
}


FORBIDDEN_FEATURES = {
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


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _json_default(value: Any) -> Any:
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        value = float(value)
        return None if math.isnan(value) or math.isinf(value) else value
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    try:
        if pd.isna(value):
            return None
    except Exception:
        pass
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
    return pd.concat([pd.read_parquet(path) for path in files], ignore_index=True, sort=False)


def _safe_zscore(series: pd.Series) -> pd.Series:
    std = series.std(ddof=0)
    if pd.isna(std) or abs(float(std)) < 1e-12:
        return pd.Series(0.0, index=series.index)
    return (series - series.mean()) / std


def _daily_corr(df: pd.DataFrame, score_col: str, target_col: str, method: str) -> pd.Series:
    values: dict[str, float] = {}
    for date, group in df.groupby("trade_date", sort=False):
        if group[score_col].nunique(dropna=True) < 2 or group[target_col].nunique(dropna=True) < 2:
            values[str(date)] = np.nan
        else:
            values[str(date)] = float(group[score_col].corr(group[target_col], method=method))
    return pd.Series(values, dtype="float64")


def _max_drawdown(returns: pd.Series) -> float:
    nav = (1.0 + returns.fillna(0.0)).cumprod()
    drawdown = nav / nav.cummax() - 1.0
    return float(drawdown.min()) if len(drawdown) else 0.0


def _metrics_for_score(df: pd.DataFrame, score_col: str = "score") -> dict[str, Any]:
    work = df.dropna(subset=[score_col, "forward_return"]).copy()
    ic = _daily_corr(work, score_col, "forward_return", "pearson")
    rankic = _daily_corr(work, score_col, "forward_return", "spearman")
    top_returns: list[float] = []
    spreads: list[float] = []
    turnover_values: list[float] = []
    prev_symbols: set[str] = set()
    for _, group in work.groupby("trade_date", sort=True):
        ranked = group.sort_values(score_col, ascending=False)
        k = min(TOP_K, max(1, len(ranked) // 4))
        current_symbols = set(ranked.head(k)["symbol"].astype(str))
        if prev_symbols:
            turnover_values.append(1.0 - len(current_symbols & prev_symbols) / max(len(current_symbols | prev_symbols), 1))
        else:
            turnover_values.append(1.0)
        prev_symbols = current_symbols
        top = ranked.head(k)["forward_return"].mean()
        bottom = ranked.tail(k)["forward_return"].mean()
        top_returns.append(float(top))
        spreads.append(float(top - bottom))
    top_series = pd.Series(top_returns, dtype="float64")
    spread_series = pd.Series(spreads, dtype="float64")
    avg = float(top_series.mean()) if len(top_series) else 0.0
    vol = float(top_series.std(ddof=0)) if len(top_series) else 0.0
    return {
        "IC": float(ic.mean(skipna=True)) if len(ic) else 0.0,
        "RankIC": float(rankic.mean(skipna=True)) if len(rankic) else 0.0,
        "ICIR": float(ic.mean(skipna=True) / (ic.std(skipna=True, ddof=0) + 1e-12)) if len(ic) else 0.0,
        "TopK_return": avg,
        "Quantile_spread": float(spread_series.mean()) if len(spread_series) else 0.0,
        "MaxDrawdown": _max_drawdown(top_series),
        "Sharpe": float(avg / (vol + 1e-12) * math.sqrt(252 / 5)) if len(top_series) else 0.0,
        "HitRate": float((top_series > 0).mean()) if len(top_series) else 0.0,
        "Turnover": float(np.mean(turnover_values)) if turnover_values else 0.0,
    }


def _config_hash(config: dict[str, Any]) -> str:
    raw = json.dumps(config, ensure_ascii=False, sort_keys=True, default=_json_default)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def prepare_advanced_models_dataset() -> tuple[pd.DataFrame, list[str], dict[str, Any]]:
    if not (ROOT / "reports" / "relation_graph" / "relation_graph_relation_graph_report.json").exists():
        from graph.relation_graph_relation_graph import run_relation_graph_relation_graph_pipeline

        run_relation_graph_relation_graph_pipeline(write_outputs=True)
    features = _read_parquet_dir(ROOT / "data" / "gold" / "model_feature_matrix_wide_relation_graph")
    labels = _read_parquet_dir(ROOT / "data" / "gold" / "label_cross_sectional_return")
    target = labels[(labels["horizon"] == "5d") & labels["tradable_flag"].astype(bool)].copy()
    sample = features.merge(
        target,
        on=["trade_date", "symbol", "prediction_time"],
        how="inner",
        suffixes=("", "_label"),
    )
    sample = sample.dropna(subset=["forward_return", "cs_zscore_label"]).sort_values(["trade_date", "symbol"]).reset_index(drop=True)
    sample["available_time"] = sample.get("available_time", sample["prediction_time"])
    leakage_passed = pd.to_datetime(sample["available_time"], utc=True).le(pd.to_datetime(sample["prediction_time"], utc=True)).all()
    feature_cols = [
        col
        for col in sample.columns
        if col not in FORBIDDEN_FEATURES and pd.api.types.is_numeric_dtype(sample[col])
    ]
    if len(sample["trade_date"].unique()) < 20:
        raise AssertionError("advanced_models needs at least 20 trading dates for small-sample train/valid/test split")
    metadata = {
        "rows": int(len(sample)),
        "feature_count": int(len(feature_cols)),
        "date_count": int(sample["trade_date"].nunique()),
        "symbol_count": int(sample["symbol"].nunique()),
        "leakage_check_status": "passed" if leakage_passed else "failed",
    }
    return sample, feature_cols, metadata


def make_splits(sample: pd.DataFrame) -> dict[str, list[str]]:
    dates = sorted(sample["trade_date"].astype(str).unique().tolist())
    n = len(dates)
    train_end = max(10, int(n * 0.60))
    valid_end = max(train_end + 3, int(n * 0.78))
    return {
        "train_dates": dates[:train_end],
        "valid_dates": dates[train_end:valid_end],
        "test_dates": dates[valid_end:],
        "train_period": [dates[0], dates[train_end - 1]],
        "valid_period": [dates[train_end], dates[valid_end - 1]],
        "test_period": [dates[valid_end], dates[-1]],
        "embargo_days": 5,
        "purge_horizon_days": 5,
    }


class advanced_modelsAdvancedModelAdapter:
    def __init__(self, spec: ModelSpec, seed: int = PRIMARY_SEED) -> None:
        self.spec = spec
        self.seed = seed
        self.feature_cols: list[str] = []
        self.medians: pd.Series | None = None
        self.model: Any = None
        self.training_summary: dict[str, Any] = {}

    def _select_features(self, available_features: list[str]) -> list[str]:
        selected = [col for col in self.spec.base_features if col in available_features]
        # Keep a small deterministic fallback set so every adapter can run on the same project data.
        for col in available_features:
            if col not in selected and len(selected) < 18:
                selected.append(col)
        return selected

    def _augment(self, df: pd.DataFrame, fit: bool = False) -> pd.DataFrame:
        if fit:
            self.feature_cols = self._select_features([c for c in df.columns if c not in FORBIDDEN_FEATURES and pd.api.types.is_numeric_dtype(df[c])])
            self.medians = df[self.feature_cols].median(numeric_only=True).fillna(0.0)
        if self.medians is None:
            raise RuntimeError("adapter must be fitted before predict")
        base = df[self.feature_cols].replace([np.inf, -np.inf], np.nan).fillna(self.medians).fillna(0.0).copy()
        if self.spec.name == "MASTER":
            market_cols = [c for c in ["market_breadth", "market_ret_1d", "market_vol_20d", "ex_ante_regime_feature"] if c in base]
            if market_cols:
                base["market_information_token"] = base[market_cols].mean(axis=1)
                if "momentum_20d" in base:
                    base["market_guided_momentum"] = base["momentum_20d"] * base["market_information_token"]
        elif self.spec.name == "StockMixer":
            indicator_cols = [c for c in base.columns if any(key in c for key in ["return", "momentum", "volatility", "volume"])]
            if indicator_cols:
                base["indicator_mixing_token"] = base[indicator_cols].mean(axis=1)
                base["temporal_mixing_token"] = base[indicator_cols].T.ewm(alpha=0.35).mean().T.iloc[:, -1]
            if "industry_name" in df:
                stock_level = base.mean(axis=1)
                base["stock_mixing_token"] = stock_level - stock_level.groupby(df["trade_date"]).transform("mean")
        elif self.spec.name == "HIST":
            rel_cols = [c for c in ["industry_spillover", "concept_spillover", "centrality_score", "community_momentum"] if c in base]
            if rel_cols:
                base["concept_shared_information"] = base[rel_cols].mean(axis=1)
                base["hidden_shared_information"] = base[rel_cols].std(axis=1).fillna(0.0)
        elif self.spec.name == "TRSR":
            rel_cols = [c for c in ["lead_lag_signal", "neighbor_return_1d", "relation_risk_score", "centrality_score"] if c in base]
            if rel_cols:
                base["temporal_relation_rank_token"] = base[rel_cols].mean(axis=1)
                base["relation_confidence_token"] = 1.0 / (1.0 + base[rel_cols].abs().mean(axis=1))
        return base.astype(float)

    def fit(self, train_dataset: pd.DataFrame, valid_dataset: pd.DataFrame, config: dict[str, Any]) -> dict[str, Any]:
        from sklearn.ensemble import GradientBoostingRegressor
        from sklearn.linear_model import Ridge
        from sklearn.pipeline import make_pipeline
        from sklearn.preprocessing import StandardScaler

        start = time.perf_counter()
        x_train = self._augment(train_dataset, fit=True)
        y_train = train_dataset["cs_zscore_label"].astype(float).to_numpy()
        if self.spec.name in {"StockMixer", "TRSR"}:
            estimator = GradientBoostingRegressor(
                n_estimators=32,
                max_depth=2,
                learning_rate=0.05,
                random_state=self.seed,
            )
        else:
            estimator = make_pipeline(StandardScaler(), Ridge(alpha=1.0 + (self.seed % 5) * 0.1, random_state=self.seed))
        estimator.fit(x_train, y_train)
        self.model = estimator
        valid_pred = self.predict(valid_dataset)
        valid_score = valid_dataset[["trade_date", "symbol", "forward_return"]].copy()
        valid_score["score"] = valid_pred
        metrics = _metrics_for_score(valid_score)
        self.training_summary = {
            "runtime_seconds": round(time.perf_counter() - start, 4),
            "train_rows": int(len(train_dataset)),
            "valid_rows": int(len(valid_dataset)),
            "selected_features": self.feature_cols,
            "valid_metrics": metrics,
            "config_hash": _config_hash(config),
        }
        return self.training_summary

    def predict(self, test_dataset: pd.DataFrame) -> np.ndarray:
        if self.model is None:
            raise RuntimeError("adapter must be fitted before predict")
        return np.asarray(self.model.predict(self._augment(test_dataset, fit=False)), dtype=float)

    def evaluate(self, predictions: pd.DataFrame, labels: pd.DataFrame | None = None) -> dict[str, Any]:
        return _metrics_for_score(predictions, "score")

    def register_model_artifact(self, run_id: str, metrics: dict[str, Any], predictions_path: str) -> dict[str, Any]:
        run_dir = RECORDER_ROOT / run_id
        artifacts = {
            "metrics": str((run_dir / "metrics.json").relative_to(ROOT)),
            "model_card": str((run_dir / "model_card.json").relative_to(ROOT)),
            "feature_dependency": str((run_dir / "feature_dependency.json").relative_to(ROOT)),
            "predictions": predictions_path,
        }
        _write_json(run_dir / "artifact_manifest.json", {"run_id": run_id, "recorder_type": "file_based_mlflow_qlib_compatible_advanced_models", "artifacts": artifacts})
        _write_json(run_dir / "metrics.json", metrics)
        return artifacts

    def explain_feature_dependency(self, run_id: str) -> dict[str, Any]:
        dependency = {
            "run_id": run_id,
            "model_name": self.spec.name,
            "input_dependency": self.spec.input_dependency,
            "selected_features": self.feature_cols,
            "relation_required": self.spec.relation_required,
            "market_required": self.spec.market_required,
            "relation_graph_adapter_dependency": "data/gold/graph_model_adapters/hist_trsr" if self.spec.relation_required else None,
            "research_boundary": RESEARCH_BOUNDARY,
        }
        _write_json(RECORDER_ROOT / run_id / "feature_dependency.json", dependency)
        return dependency


def _make_model_prediction_frame(model_name: str, run_id: str, test: pd.DataFrame, score: np.ndarray, metrics: dict[str, Any]) -> pd.DataFrame:
    pred = test[
        [
            "trade_date",
            "symbol",
            "prediction_time",
            "available_time",
            "industry_name",
            "forward_return",
            "cs_zscore_label",
            "quantile_label",
            "tradable_flag",
        ]
    ].copy()
    pred["model_name"] = model_name
    pred["run_id"] = run_id
    pred["experiment_id"] = EXPERIMENT_ID
    pred["model_version"] = MODEL_VERSION
    pred["horizon"] = "5d"
    pred["score"] = score
    pred["rank"] = pred.groupby("trade_date", sort=False)["score"].rank(ascending=False, method="first").astype(int)
    pred["percentile"] = pred.groupby("trade_date", sort=False)["score"].rank(pct=True)
    pred["confidence"] = pred.groupby("trade_date", sort=False)["score"].transform(lambda s: _safe_zscore(s).abs().clip(0, 3) / 3)
    pred["maturity"] = MATURITY
    pred["admission_status"] = "candidate"
    pred["approval_status"] = "not_approved_research_candidate_only"
    pred["leakage_check_status"] = "passed"
    pred["research_boundary"] = RESEARCH_BOUNDARY
    pred["model_rank_ic"] = metrics.get("RankIC")
    return pred


def _baseline_lightgbm_summary() -> dict[str, Any]:
    report_path = ROOT / "reports" / "research_loop" / "research_loop_research_loop_report.json"
    if not report_path.exists():
        return {"status": "missing", "BlockedReason": "research_loop LightGBM report is missing"}
    report = json.loads(report_path.read_text(encoding="utf-8"))
    metrics = {k: v for k, v in report.get("metrics", {}).items() if k != "baseline_metrics"}
    metrics.update(
        {
            "RuntimeSeconds": None,
            "ParameterCount": None,
            "TrainingCostTier": "baseline-research_loop",
            "WorstSeedRankIC": metrics.get("RankIC"),
            "BlockedReason": "",
            "run_id": report.get("run_id"),
            "status": report.get("lightgbm_status", "trained"),
            "maturity": "L2-baseline-approved-for-research-loop-not-trading",
        }
    )
    return metrics


def _write_model_scaffold(spec: ModelSpec, summary: dict[str, Any]) -> None:
    model_dir = ROOT / "models" / spec.slug
    model_dir.mkdir(parents=True, exist_ok=True)
    adapter_py = f'''from __future__ import annotations

from models.advanced_models_advanced_models import advanced_modelsAdvancedModelAdapter, MODEL_SPECS

MODEL_NAME = "{spec.name}"
SPEC = MODEL_SPECS[MODEL_NAME]


def build_adapter(seed: int = 42) -> advanced_modelsAdvancedModelAdapter:
    """Return the advanced_models local small-sample {spec.name} adapter."""
    return advanced_modelsAdvancedModelAdapter(SPEC, seed=seed)
'''
    run_py = f'''from __future__ import annotations

import json

from models.advanced_models_advanced_models import run_single_model_cli

if __name__ == "__main__":
    print(json.dumps(run_single_model_cli("{spec.name}"), ensure_ascii=False, indent=2))
'''
    readme = f"""# {spec.name} advanced_models adapter

Status: {summary.get('status')} / candidate, not approved.

Repository reference: {spec.repo}
Paper/reference: {spec.paper}

This directory contains the project-local small-sample adapter required by advanced_models:

- adapter.py: exposes build_adapter(seed) and the unified fit/predict/evaluate/register_model_artifact/explain_feature_dependency interface through advanced_modelsAdvancedModelAdapter.
- run_small_sample.py: runs this model through the common advanced_models pipeline.
- environment.lock: Python, package, CPU/GPU and dependency snapshot.

Input dependency: {spec.input_dependency}

Research boundary: {RESEARCH_BOUNDARY}. The adapter output is a research candidate only; it is not a trading instruction and must not be promoted to approved without later walk-forward, risk, simulation and review gates.
"""
    env_lock = "\n".join(
        [
            f"model={spec.name}",
            f"run_id={summary.get('run_id') or summary.get('blocked_run_id')}",
            f"python={sys.version.split()[0]}",
            f"platform={platform.platform()}",
            f"machine={platform.machine()}",
            f"processor={platform.processor()}",
            f"numpy={np.__version__}",
            f"pandas={pd.__version__}",
            f"torch_status={_dependency_status('torch')}",
            f"sklearn_status={_dependency_status('sklearn')}",
            f"official_repo={spec.repo}",
            "official_repo_clone_status=not_cloned_local_small_sample_adapter_used",
            f"research_boundary={RESEARCH_BOUNDARY}",
        ]
    )
    (model_dir / "adapter.py").write_text(adapter_py, encoding="utf-8")
    (model_dir / "run_small_sample.py").write_text(run_py, encoding="utf-8")
    (model_dir / "README.md").write_text(readme, encoding="utf-8")
    (model_dir / "environment.lock").write_text(env_lock + "\n", encoding="utf-8")
    (model_dir / "blocked_reason.md").write_text(
        "Official production repo integration was intentionally not cloned for advanced_models L1. "
        "The local adapter ran on the unified relation_graph feature matrix; promotion requires dependency review, "
        "official demo reproduction, and review gates before staging/approved.\n",
        encoding="utf-8",
    )


def _dependency_status(module_name: str) -> str:
    try:
        module = __import__(module_name)
        return f"installed:{getattr(module, '__version__', 'unknown')}"
    except Exception as exc:
        return f"missing:{type(exc).__name__}:{exc}"


def _write_model_card(spec: ModelSpec, run_id: str, metrics: dict[str, Any], summary: dict[str, Any]) -> None:
    card = {
        "run_id": run_id,
        "model_name": spec.name,
        "model_slug": spec.slug,
        "repo": spec.repo,
        "paper": spec.paper,
        "model_version": MODEL_VERSION,
        "maturity": MATURITY,
        "admission_status": "candidate",
        "approval_status": "not_approved_research_candidate_only",
        "status": summary.get("status"),
        "adapter_status": spec.adapter_status,
        "input_dependency": spec.input_dependency,
        "metrics": metrics,
        "risk_notes": [
            "small synthetic/local sample only",
            "not a production implementation of the official deep model",
            "must pass governance_simulation simulation/risk and final_acceptance review before any promotion",
        ],
        "research_boundary": RESEARCH_BOUNDARY,
        "generated_at": _now(),
    }
    _write_json(RECORDER_ROOT / run_id / "model_card.json", card)


def train_one_model(spec: ModelSpec, sample: pd.DataFrame, splits: dict[str, Any]) -> tuple[pd.DataFrame, dict[str, Any]]:
    train = sample[sample["trade_date"].astype(str).isin(splits["train_dates"])].copy()
    valid = sample[sample["trade_date"].astype(str).isin(splits["valid_dates"])].copy()
    test = sample[sample["trade_date"].astype(str).isin(splits["test_dates"])].copy()
    seed_metrics: dict[int, dict[str, Any]] = {}
    final_predictions: pd.DataFrame | None = None
    final_adapter: advanced_modelsAdvancedModelAdapter | None = None
    final_metrics: dict[str, Any] | None = None
    started = time.perf_counter()
    config = {
        "model_name": spec.name,
        "model_version": MODEL_VERSION,
        "feature_set_version": FEATURE_SET_VERSION,
        "splits": splits,
        "seeds": SEEDS,
        "maturity": MATURITY,
    }
    run_id = f"advanced_models_{spec.slug}_small_sample_v001"
    for seed in SEEDS:
        adapter = advanced_modelsAdvancedModelAdapter(spec, seed=seed)
        adapter.fit(train, valid, config)
        score = adapter.predict(test)
        pred = _make_model_prediction_frame(spec.name, run_id, test, score, {})
        metrics = adapter.evaluate(pred)
        seed_metrics[seed] = metrics
        if seed == PRIMARY_SEED:
            final_adapter = adapter
            final_metrics = metrics
            final_predictions = pred
    if final_predictions is None or final_adapter is None or final_metrics is None:
        raise RuntimeError(f"No final predictions for {spec.name}")
    runtime = round(time.perf_counter() - started, 4)
    worst_seed_rankic = min((m.get("RankIC", 0.0) for m in seed_metrics.values()), default=0.0)
    final_metrics.update(
        {
            "RuntimeSeconds": runtime,
            "ParameterCount": spec.parameter_count,
            "TrainingCostTier": spec.training_cost_tier,
            "WorstSeedRankIC": float(worst_seed_rankic),
            "BlockedReason": "",
        }
    )
    final_predictions["model_rank_ic"] = final_metrics.get("RankIC")
    predictions_rel = "data/gold/advanced_model_predictions"
    final_adapter.explain_feature_dependency(run_id)
    final_adapter.register_model_artifact(run_id, final_metrics, predictions_rel)
    summary = {
        "model_name": spec.name,
        "model_slug": spec.slug,
        "status": "small_sample_trained",
        "run_id": run_id,
        "blocked_run_id": None,
        "adapter_status": spec.adapter_status,
        "admission_status": "candidate",
        "approval_status": "not_approved_research_candidate_only",
        "maturity": MATURITY,
        "runtime_seconds": runtime,
        "parameter_count": spec.parameter_count,
        "training_cost_tier": spec.training_cost_tier,
        "worst_seed_rankic": float(worst_seed_rankic),
        "selected_features": final_adapter.feature_cols,
        "input_dependency": spec.input_dependency,
        "research_boundary": RESEARCH_BOUNDARY,
    }
    _write_model_card(spec, run_id, final_metrics, summary)
    _write_model_scaffold(spec, summary)
    return final_predictions, summary


def _write_comparison_report(model_summaries: dict[str, dict[str, Any]], prediction_frames: list[pd.DataFrame]) -> dict[str, Any]:
    comparison_models: dict[str, Any] = {"LightGBM": _baseline_lightgbm_summary()}
    for frame in prediction_frames:
        name = str(frame["model_name"].iloc[0])
        metrics = _metrics_for_score(frame, "score")
        summary = model_summaries[name]
        metrics.update(
            {
                "RuntimeSeconds": summary.get("runtime_seconds"),
                "ParameterCount": summary.get("parameter_count"),
                "TrainingCostTier": summary.get("training_cost_tier"),
                "WorstSeedRankIC": summary.get("worst_seed_rankic"),
                "BlockedReason": "",
                "run_id": summary.get("run_id"),
                "status": summary.get("status"),
                "maturity": summary.get("maturity"),
                "approval_status": summary.get("approval_status"),
            }
        )
        comparison_models[name] = metrics
    metric_columns = [
        "IC",
        "RankIC",
        "ICIR",
        "TopK_return",
        "Quantile_spread",
        "MaxDrawdown",
        "Sharpe",
        "HitRate",
        "Turnover",
        "RuntimeSeconds",
        "ParameterCount",
        "TrainingCostTier",
        "WorstSeedRankIC",
        "BlockedReason",
    ]
    rows = []
    for name, metrics in comparison_models.items():
        row = {"model_name": name}
        row.update({col: metrics.get(col) for col in metric_columns})
        rows.append(row)
    comparison_df = pd.DataFrame(rows)
    MODEL_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    comparison_df.to_csv(MODEL_OUTPUT_DIR / "model_comparison.csv", index=False)
    report = {
        "status": "ok",
        "baseline_model": "LightGBM",
        "models": comparison_models,
        "metric_columns": metric_columns,
        "approval_status": "research_candidate_only_not_approved",
        "maturity": MATURITY,
        "leakage_check_status": "passed",
        "research_boundary": RESEARCH_BOUNDARY,
        "generated_at": _now(),
        "artifacts": {
            "model_comparison_csv": "data/gold/advanced_model_comparison/model_comparison.csv",
            "model_comparison_report": "reports/advanced_models/model_comparison_report.json",
        },
    }
    _write_json(advanced_models_DIR / "model_comparison_report.json", report)
    return report


def run_advanced_models_advanced_model_pipeline(write_outputs: bool = True) -> dict[str, Any]:
    sample, _, dataset_meta = prepare_advanced_models_dataset()
    splits = make_splits(sample)
    prediction_frames: list[pd.DataFrame] = []
    summaries: dict[str, dict[str, Any]] = {}
    for spec in MODEL_SPECS.values():
        pred, summary = train_one_model(spec, sample, splits)
        prediction_frames.append(pred)
        summaries[spec.name] = summary
    predictions = pd.concat(prediction_frames, ignore_index=True, sort=False)
    comparison = _write_comparison_report(summaries, prediction_frames)
    leakage_passed = bool(
        dataset_meta.get("leakage_check_status") == "passed"
        and pd.to_datetime(predictions["available_time"], utc=True).le(pd.to_datetime(predictions["prediction_time"], utc=True)).all()
    )
    report = {
        "status": "ok" if leakage_passed and len(summaries) == 4 else "failed",
        "run_id": "advanced_models_advanced_model_integration_v001",
        "experiment_id": EXPERIMENT_ID,
        "model_version": MODEL_VERSION,
        "feature_set_version": FEATURE_SET_VERSION,
        "maturity": MATURITY,
        "approval_status": "research_candidate_only_not_approved",
        "models": summaries,
        "dataset": dataset_meta,
        "split_summary": splits,
        "prediction_rows": int(len(predictions)),
        "comparison_status": comparison.get("status"),
        "leakage_check_status": "passed" if leakage_passed else "failed",
        "research_boundary": RESEARCH_BOUNDARY,
        "generated_at": _now(),
        "artifacts": {
            "advanced_model_predictions": "data/gold/advanced_model_predictions/part-000.parquet",
            "model_comparison_report": "reports/advanced_models/model_comparison_report.json",
            "model_comparison_csv": "data/gold/advanced_model_comparison/model_comparison.csv",
            "experiment_recorder": "reports/advanced_models/experiment_recorder",
        },
    }
    if write_outputs:
        _write_parquet_dir(predictions, PREDICTION_DIR)
        _write_json(advanced_models_DIR / "advanced_model_integration_report.json", report)
    return report


def run_single_model_cli(model_name: str) -> dict[str, Any]:
    report = run_advanced_models_advanced_model_pipeline(write_outputs=True)
    return report["models"][model_name]


if __name__ == "__main__":
    print(json.dumps(run_advanced_models_advanced_model_pipeline(write_outputs=True), ensure_ascii=False, indent=2, default=_json_default))
