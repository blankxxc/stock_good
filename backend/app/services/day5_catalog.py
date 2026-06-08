from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd
import yaml


def project_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _read_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def _read_parquet(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    return pd.read_parquet(path)


def day5_report() -> dict[str, Any]:
    return _read_json(project_root() / "reports" / "day5" / "day5_research_loop_report.json")


def scores_payload(research_boundary: str) -> dict[str, Any]:
    root = project_root()
    report = day5_report()
    predictions = _read_parquet(root / "reports" / "day5" / "predictions.parquet")
    if report.get("status") != "ok" or predictions.empty:
        return {
            "module": "scores",
            "status": "day5_scores_pending",
            "maturity": "L1-route-stub",
            "research_boundary": research_boundary,
        }
    latest_date = str(predictions["trade_date"].max())
    latest = predictions[predictions["trade_date"].astype(str) == latest_date].sort_values("rank").head(20)
    rows = latest[
        ["trade_date", "symbol", "industry_name", "score", "rank", "percentile", "horizon", "model_version", "confidence", "leakage_check_status"]
    ].to_dict(orient="records")
    return {
        "module": "scores",
        "status": "day5_scores_ready",
        "maturity": "L2-lightgbm-cross-sectional-scores",
        "research_boundary": research_boundary,
        "run_id": report.get("run_id"),
        "experiment_id": report.get("experiment_id"),
        "latest_trade_date": latest_date,
        "prediction_rows": report.get("prediction_rows"),
        "model_version": report.get("model_version"),
        "label_version": report.get("label_version"),
        "factor_version": report.get("factor_version"),
        "horizon": "5d",
        "top_scores": rows,
        "api_note": "research ranking only; not investment advice or trading instruction",
    }


def backtests_payload(research_boundary: str) -> dict[str, Any]:
    root = project_root()
    report = day5_report()
    curve = _read_parquet(root / "data" / "gold" / "portfolio_backtest_result" / "part-000.parquet")
    risk = _read_parquet(root / "reports" / "day5" / "risk_report.parquet")
    if report.get("status") != "ok" or curve.empty:
        return {
            "module": "backtests",
            "status": "day5_backtest_pending",
            "maturity": "L1-route-stub",
            "research_boundary": research_boundary,
        }
    metrics = report.get("metrics", {})
    return {
        "module": "backtests",
        "status": "day5_backtest_ready",
        "maturity": "L2-tradable-topk-cost-risk-capacity-backtest",
        "research_boundary": research_boundary,
        "run_id": report.get("run_id"),
        "experiment_id": report.get("experiment_id"),
        "portfolio_id": "top5_equal_weight",
        "benchmark": "CSI300_DEMO",
        "equity_curve_rows": int(len(curve)),
        "risk_report_rows": int(len(risk)),
        "metrics": {k: v for k, v in metrics.items() if k != "baseline_metrics"},
        "baseline_metrics": metrics.get("baseline_metrics", {}),
        "curve_tail": curve.tail(10).to_dict(orient="records"),
        "artifacts": report.get("artifacts", {}),
    }


def experiments_payload(research_boundary: str) -> dict[str, Any]:
    root = project_root()
    report = day5_report()
    manifest = _read_json(root / "reports" / "day5" / "experiment_recorder" / str(report.get("run_id", "")) / "artifact_manifest.json")
    config = _read_yaml(root / "reports" / "day5" / "experiment_recorder" / str(report.get("run_id", "")) / "resolved_config.yaml")
    if report.get("status") != "ok":
        return {
            "module": "experiments",
            "status": "day5_experiment_pending",
            "maturity": "L1-route-stub",
            "research_boundary": research_boundary,
        }
    return {
        "module": "experiments",
        "status": "day5_experiment_recorder_ready",
        "maturity": "L2-file-based-mlflow-qlib-compatible-recorder",
        "research_boundary": research_boundary,
        "run_id": report.get("run_id"),
        "experiment_id": report.get("experiment_id"),
        "config_hash": report.get("config_hash"),
        "data_version": report.get("data_version"),
        "factor_version": report.get("factor_version"),
        "label_version": report.get("label_version"),
        "model_version": report.get("model_version"),
        "feature_count": report.get("feature_count"),
        "split_count": report.get("split_count"),
        "lightgbm_status": report.get("lightgbm_status"),
        "qlib_status": report.get("qlib_status"),
        "resolved_config": config,
        "artifact_manifest": manifest,
    }


def dashboard_day5_payload(research_boundary: str) -> dict[str, Any]:
    report = day5_report()
    if report.get("status") != "ok":
        return {
            "module": "overview",
            "status": "day4_ready_day5_pending",
            "research_boundary": research_boundary,
        }
    metrics = report.get("metrics", {})
    return {
        "module": "overview",
        "status": "day5_research_loop_ready",
        "maturity": "L2-offline-research-loop-dashboard-summary",
        "research_boundary": research_boundary,
        "run_id": report.get("run_id"),
        "model_version": report.get("model_version"),
        "label_version": report.get("label_version"),
        "leakage_check_status": report.get("leakage_check_status"),
        "prediction_rows": report.get("prediction_rows"),
        "equity_curve_rows": report.get("equity_curve_rows"),
        "risk_report_rows": report.get("risk_report_rows"),
        "core_metrics": {
            "IC": metrics.get("IC"),
            "RankIC": metrics.get("RankIC"),
            "TopK_return": metrics.get("TopK_return"),
            "Turnover": metrics.get("Turnover"),
            "Cost_adjusted_return": metrics.get("Cost_adjusted_return"),
            "Capacity": metrics.get("Capacity"),
        },
    }
