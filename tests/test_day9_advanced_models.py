from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
from fastapi.testclient import TestClient

PROJECT_ROOT = Path(__file__).resolve().parents[1]
RESEARCH_BOUNDARY = "research_signals_only_not_investment_advice"
REQUIRED_MODELS = {"MASTER", "StockMixer", "HIST", "TRSR"}


def _ensure_day9() -> dict:
    from models.day9_advanced_models import run_day9_advanced_model_pipeline

    return run_day9_advanced_model_pipeline(write_outputs=True)


def test_day9_all_advanced_model_adapters_have_small_sample_runs_and_candidate_gate():
    report = _ensure_day9()
    assert report["status"] == "ok"
    assert set(report["models"].keys()) == REQUIRED_MODELS
    assert report["approval_status"] == "research_candidate_only_not_approved"
    assert report["maturity"] == "L1-research-candidate-small-sample"
    assert report["leakage_check_status"] == "passed"

    for model_name, summary in report["models"].items():
        model_dir = PROJECT_ROOT / "models" / summary["model_slug"]
        assert (model_dir / "adapter.py").is_file(), model_name
        assert (model_dir / "run_small_sample.py").is_file(), model_name
        assert (model_dir / "README.md").is_file(), model_name
        assert (model_dir / "environment.lock").is_file(), model_name
        assert summary["run_id"] or summary["blocked_run_id"], model_name
        assert summary["status"] in {"small_sample_trained", "blocked_with_reason"}, model_name
        assert summary["admission_status"] == "candidate", model_name
        assert summary["approval_status"] == "not_approved_research_candidate_only", model_name
        assert summary["research_boundary"] == RESEARCH_BOUNDARY


def test_day9_predictions_comparison_and_experiment_artifacts_are_written():
    report = _ensure_day9()
    predictions_path = PROJECT_ROOT / report["artifacts"]["advanced_model_predictions"]
    comparison_path = PROJECT_ROOT / report["artifacts"]["model_comparison_report"]
    recorder_root = PROJECT_ROOT / report["artifacts"]["experiment_recorder"]
    predictions = pd.read_parquet(predictions_path)
    comparison = json.loads(comparison_path.read_text(encoding="utf-8"))

    assert not predictions.empty
    assert REQUIRED_MODELS.issubset(set(predictions["model_name"].astype(str)))
    assert {"LightGBM", "MASTER", "StockMixer", "HIST", "TRSR"}.issubset(set(comparison["models"].keys()))
    assert comparison["baseline_model"] == "LightGBM"
    assert comparison["approval_status"] == "research_candidate_only_not_approved"
    assert comparison["leakage_check_status"] == "passed"
    assert {
        "IC",
        "RankIC",
        "TopK_return",
        "MaxDrawdown",
        "Turnover",
        "RuntimeSeconds",
        "ParameterCount",
        "TrainingCostTier",
        "WorstSeedRankIC",
        "BlockedReason",
    }.issubset(comparison["metric_columns"])
    assert pd.to_datetime(predictions["available_time"], utc=True).le(pd.to_datetime(predictions["prediction_time"], utc=True)).all()
    assert predictions["maturity"].eq("L1-research-candidate-small-sample").all()
    assert predictions["research_boundary"].eq(RESEARCH_BOUNDARY).all()

    for model_name in REQUIRED_MODELS:
        run_id = report["models"][model_name]["run_id"] or report["models"][model_name]["blocked_run_id"]
        run_dir = recorder_root / run_id
        assert (run_dir / "metrics.json").is_file(), model_name
        assert (run_dir / "artifact_manifest.json").is_file(), model_name
        assert (run_dir / "model_card.json").is_file(), model_name
        assert (run_dir / "feature_dependency.json").is_file(), model_name


def test_day9_backend_frontend_and_acceptance_are_ready():
    report = _ensure_day9()
    from backend.app.main import app

    client = TestClient(app)
    models = client.get("/api/models")
    experiments = client.get("/api/experiments")
    health = client.get("/health")
    assert models.status_code == 200
    payload = models.json()
    assert payload["status"] == "day9_advanced_models_ready"
    assert set(payload["models"].keys()) == REQUIRED_MODELS
    assert payload["approval_status"] == "research_candidate_only_not_approved"
    assert experiments.status_code == 200
    assert experiments.json()["advanced_models"]["status"] == "day9_advanced_models_ready"
    assert health.status_code == 200
    assert health.json()["modules"]["advanced_models"] == "day9_research_candidate_adapters_ready"

    page = (PROJECT_ROOT / "frontend" / "src" / "app" / "models" / "page.tsx").read_text(encoding="utf-8")
    assert "Day 9" in page
    assert "/api/models" in page
    assert "MASTER" in page and "StockMixer" in page and "HIST" in page and "TRSR" in page
    assert "research candidate" in page

    from scripts.check_day9_acceptance import run_acceptance

    acceptance = run_acceptance()
    assert acceptance["status"] == "ok"
    assert acceptance["checks"] >= 15
    assert acceptance["failed"] == []
