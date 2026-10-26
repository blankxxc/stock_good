from __future__ import annotations

import json

import pandas as pd
import pytest


def test_model_catalog_only_exposes_current_models_and_actual_metrics(tmp_path):
    from backend.app.services.models_catalog import models_payload

    reports = tmp_path / "reports" / "research_loop"
    reports.mkdir(parents=True)
    for stem in ("live_predictions", "sentiment_event_predictions"):
        (reports / f"{stem}.parquet").touch()
        (reports / f"{stem}_report.json").write_text(json.dumps({
            "status": "ok", "model_version": "current-test-version",
            "latest_trade_date": "2026-10-15", "prediction_target_date": "2026-10-16",
            "prediction_rows": 300, "training_sample_count": 123,
            "test_metrics": {"mae": 1.2, "mse": 2.1, "ic_mean": 0.1, "rank_ic_mean": 0.08},
            "model_methodology": {"chronological_split": {"test_start_date": "2026-08-01", "test_end_date": "2026-10-14"}},
        }), encoding="utf-8")
    (reports / "retired_model_report.json").write_text('{"status":"ok"}', encoding="utf-8")

    payload = models_payload("test", root=tmp_path)

    assert payload["status"] == "daily_models_ready"
    assert payload["model_count"] == 2
    assert {model["id"] for model in payload["models"]} == {"cograsp", "sentiment_event"}
    for model in payload["models"]:
        assert model["latest_trade_date"] == "2026-10-15"
        assert model["prediction_rows"] == 300
        assert model["test_start_date"] == "2026-08-01"
        assert model["test_end_date"] == "2026-10-14"
        assert model["test_metrics"]["mae"] == 1.2


def test_missing_predictions_are_pending_and_nonfinite_metrics_are_null(tmp_path):
    from backend.app.services.models_catalog import models_payload

    reports = tmp_path / "reports" / "research_loop"
    reports.mkdir(parents=True)
    (reports / "live_predictions_report.json").write_text(json.dumps({
        "status": "ok", "test_metrics": {"mae": float("nan"), "mse": float("inf")},
    }), encoding="utf-8")

    payload = models_payload("test", root=tmp_path)

    assert payload["status"] == "daily_models_pending"
    assert all(model["status"] == "pending" for model in payload["models"])
    assert all(value is None for value in payload["models"][0]["test_metrics"].values())
    json.dumps(payload, allow_nan=False)


def test_model_routes_and_daily_pipeline_only_use_retained_models():
    from backend.app.main import route_payload
    from scripts.update_daily_market_data import DERIVED_STEPS

    payload = route_payload("models")
    assert {model["id"] for model in payload["models"]} == {"cograsp", "sentiment_event"}
    assert {step for step in DERIVED_STEPS if step.startswith("train_")} == {
        "train_cograsp_current", "train_sentiment_event_fusion",
    }


def test_file_recorder_does_not_need_a_qlib_runtime(monkeypatch, tmp_path):
    import models.research_loop_research_loop as research

    monkeypatch.setattr(research, "ROOT", tmp_path)
    monkeypatch.setattr(research, "RECORDER_DIR", tmp_path / "recorder")
    manifest = research._write_recorder({"seed": 42}, {"ic": 0.1}, {})
    assert manifest["recorder_status"] == "file_based_recorder"
    assert (tmp_path / manifest["artifacts"]["resolved_config"]).exists()
    assert "blocked_reason" not in manifest


@pytest.mark.parametrize("model", ["cograsp", "sentiment_event"])
def test_missing_current_predictions_never_fall_back_to_legacy_model(monkeypatch, tmp_path, model):
    from backend.app.services import research_loop_catalog as catalog

    reports = tmp_path / "reports" / "research_loop"
    reports.mkdir(parents=True)
    (reports / "research_loop_research_loop_report.json").write_text('{"status":"ok"}', encoding="utf-8")
    pd.DataFrame({"trade_date": ["2024-01-02"], "score": [0.5]}).to_parquet(reports / "predictions.parquet")
    monkeypatch.setattr(catalog, "project_root", lambda: tmp_path)

    payload = catalog.scores_payload("test", model=model)

    assert payload["selected_model"] == model
    assert payload["status"] == "research_loop_scores_pending"
    assert "horizon_rankings" not in payload
