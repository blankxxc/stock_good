from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

RESEARCH_BOUNDARY = "research_signals_only_not_investment_advice"
DAY9_DIR = ROOT / "reports" / "day9"
REQUIRED_MODELS = {"MASTER", "StockMixer", "HIST", "TRSR"}


def _json_default(value: Any) -> Any:
    try:
        if pd.isna(value):
            return None
    except Exception:
        pass
    return str(value)


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def run_acceptance() -> dict[str, Any]:
    from backend.app.main import app
    from fastapi.testclient import TestClient
    from models.day9_advanced_models import run_day9_advanced_model_pipeline

    report = run_day9_advanced_model_pipeline(write_outputs=True)
    comparison = _read_json(DAY9_DIR / "model_comparison_report.json")
    predictions_path = ROOT / "data" / "gold" / "advanced_model_predictions" / "part-000.parquet"
    predictions = pd.read_parquet(predictions_path) if predictions_path.exists() else pd.DataFrame()
    client = TestClient(app)
    api_models = client.get("/api/models")
    api_experiments = client.get("/api/experiments")
    health = client.get("/health")

    failed: list[str] = []

    def check(name: str, condition: bool) -> None:
        if not condition:
            failed.append(name)

    check("day9_report_ok", report.get("status") == "ok")
    check("required_models_present", set(report.get("models", {}).keys()) == REQUIRED_MODELS)
    check("all_models_have_run_or_blocked_id", all(item.get("run_id") or item.get("blocked_run_id") for item in report.get("models", {}).values()))
    check("all_model_files_present", all((ROOT / "models" / item.get("model_slug", "") / name).is_file() for item in report.get("models", {}).values() for name in ["adapter.py", "run_small_sample.py", "README.md", "environment.lock"]))
    check("candidate_not_approved", report.get("approval_status") == "research_candidate_only_not_approved" and all(item.get("approval_status") == "not_approved_research_candidate_only" for item in report.get("models", {}).values()))
    check("leakage_check_passed", report.get("leakage_check_status") == "passed" and comparison.get("leakage_check_status") == "passed")
    check("predictions_written", not predictions.empty and REQUIRED_MODELS.issubset(set(predictions.get("model_name", pd.Series(dtype=str)).astype(str))))
    check("prediction_time_semantics", not predictions.empty and pd.to_datetime(predictions["available_time"], utc=True).le(pd.to_datetime(predictions["prediction_time"], utc=True)).all())
    check("research_boundary_enforced", not predictions.empty and predictions["research_boundary"].eq(RESEARCH_BOUNDARY).all())
    check("comparison_report_written", comparison.get("status") == "ok" and {"LightGBM", "MASTER", "StockMixer", "HIST", "TRSR"}.issubset(set(comparison.get("models", {}).keys())))
    check("comparison_has_required_metrics", {"IC", "RankIC", "TopK_return", "MaxDrawdown", "Turnover", "RuntimeSeconds", "ParameterCount", "TrainingCostTier", "WorstSeedRankIC", "BlockedReason"}.issubset(set(comparison.get("metric_columns", []))))
    check("experiment_artifacts_written", all((ROOT / "reports" / "day9" / "experiment_recorder" / (item.get("run_id") or item.get("blocked_run_id", "")) / name).is_file() for item in report.get("models", {}).values() for name in ["metrics.json", "artifact_manifest.json", "model_card.json", "feature_dependency.json"]))
    check("backend_models_api_ready", api_models.status_code == 200 and api_models.json().get("status") == "day9_advanced_models_ready")
    check("backend_experiments_api_links_day9", api_experiments.status_code == 200 and api_experiments.json().get("advanced_models", {}).get("status") == "day9_advanced_models_ready")
    check("health_module_ready", health.status_code == 200 and health.json().get("modules", {}).get("advanced_models") == "day9_research_candidate_adapters_ready")
    page = (ROOT / "frontend" / "src" / "app" / "models" / "page.tsx").read_text(encoding="utf-8")
    check("frontend_models_page_day9_ready", "Day 9" in page and "/api/models" in page and "research candidate" in page and all(name in page for name in REQUIRED_MODELS))

    result = {
        "status": "ok" if not failed else "failed",
        "checks": 16,
        "failed": failed,
        "model_count": len(report.get("models", {})),
        "prediction_rows": int(len(predictions)) if not predictions.empty else 0,
        "approval_status": report.get("approval_status"),
        "leakage_check_status": report.get("leakage_check_status"),
        "artifacts": report.get("artifacts", {}),
    }
    DAY9_DIR.mkdir(parents=True, exist_ok=True)
    (DAY9_DIR / "acceptance_report.json").write_text(json.dumps(result, ensure_ascii=False, indent=2, default=_json_default), encoding="utf-8")
    return result


if __name__ == "__main__":
    print(json.dumps(run_acceptance(), ensure_ascii=False, indent=2, default=_json_default))
