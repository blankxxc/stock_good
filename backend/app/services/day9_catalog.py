from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd


def project_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _read_parquet(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    return pd.read_parquet(path)


def advanced_models_report() -> dict[str, Any]:
    return _read_json(project_root() / "reports" / "day9" / "advanced_model_integration_report.json")


def model_comparison_report() -> dict[str, Any]:
    return _read_json(project_root() / "reports" / "day9" / "model_comparison_report.json")


def advanced_models_payload(research_boundary: str) -> dict[str, Any]:
    root = project_root()
    report = advanced_models_report()
    comparison = model_comparison_report()
    predictions = _read_parquet(root / "data" / "gold" / "advanced_model_predictions" / "part-000.parquet")
    if report.get("status") != "ok":
        return {
            "module": "models",
            "status": "day9_advanced_models_pending",
            "maturity": "L1-route-stub",
            "research_boundary": research_boundary,
        }
    latest_rows: list[dict[str, Any]] = []
    if not predictions.empty:
        latest_date = str(predictions["trade_date"].max())
        latest = predictions[predictions["trade_date"].astype(str) == latest_date].sort_values(["model_name", "rank"]).groupby("model_name", sort=False).head(5)
        latest_rows = latest[["trade_date", "model_name", "symbol", "industry_name", "score", "rank", "confidence", "admission_status", "approval_status"]].to_dict(orient="records")
    return {
        "module": "models",
        "status": "day9_advanced_models_ready",
        "maturity": report.get("maturity"),
        "research_boundary": research_boundary,
        "run_id": report.get("run_id"),
        "experiment_id": report.get("experiment_id"),
        "model_version": report.get("model_version"),
        "feature_set_version": report.get("feature_set_version"),
        "approval_status": report.get("approval_status"),
        "leakage_check_status": report.get("leakage_check_status"),
        "prediction_rows": report.get("prediction_rows"),
        "models": report.get("models", {}),
        "comparison": {
            "baseline_model": comparison.get("baseline_model"),
            "metric_columns": comparison.get("metric_columns", []),
            "models": comparison.get("models", {}),
        },
        "latest_candidate_scores": latest_rows,
        "artifacts": report.get("artifacts", {}),
        "api_note": "advanced model outputs are research candidates only; not approved trading signals",
    }


def advanced_models_experiment_summary(research_boundary: str) -> dict[str, Any]:
    payload = advanced_models_payload(research_boundary)
    if payload.get("status") != "day9_advanced_models_ready":
        return payload
    return {
        "status": "day9_advanced_models_ready",
        "maturity": payload.get("maturity"),
        "run_id": payload.get("run_id"),
        "experiment_id": payload.get("experiment_id"),
        "approval_status": payload.get("approval_status"),
        "leakage_check_status": payload.get("leakage_check_status"),
        "model_count": len(payload.get("models", {})),
        "models": {
            name: {
                "run_id": item.get("run_id"),
                "status": item.get("status"),
                "adapter_status": item.get("adapter_status"),
                "admission_status": item.get("admission_status"),
                "approval_status": item.get("approval_status"),
                "runtime_seconds": item.get("runtime_seconds"),
                "parameter_count": item.get("parameter_count"),
                "training_cost_tier": item.get("training_cost_tier"),
            }
            for name, item in payload.get("models", {}).items()
        },
        "artifacts": payload.get("artifacts", {}),
        "research_boundary": research_boundary,
    }
