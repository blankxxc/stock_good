from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
from fastapi.testclient import TestClient

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _ensure_research_loop() -> dict:
    from models.research_loop_research_loop import run_research_loop_research_loop

    return run_research_loop_research_loop(write_outputs=True)


def test_research_loop_label_table_has_point_in_time_tradeability_and_versions():
    report = _ensure_research_loop()
    assert report["status"] == "ok"
    assert report["leakage_check_status"] == "passed"
    assert report["label_rows"] > 0

    label_files = list((PROJECT_ROOT / "data" / "gold" / "label_cross_sectional_return").glob("**/*.parquet"))
    assert label_files
    labels = pd.concat([pd.read_parquet(path) for path in label_files], ignore_index=True)
    required = {
        "trade_date",
        "symbol",
        "horizon",
        "prediction_time",
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
        "label_version",
    }
    assert required.issubset(labels.columns)
    assert set(labels["horizon"].astype(str).unique()) >= {"1d", "5d", "10d", "14d"}
    assert "up_label" in labels.columns
    assert set(labels["up_label"].dropna().astype(int).unique()).issubset({0, 1})
    assert labels["execution_price_type"].eq("t_plus_1_open").all()

    assert labels["leakage_check_status"].eq("passed").all()


def test_research_loop_lightgbm_walk_forward_backtest_and_risk_artifacts_are_ready():
    report = _ensure_research_loop()
    assert report["lightgbm_status"] == "trained"
    assert report["split_count"] >= 3
    assert report["prediction_rows"] > 0
    assert set(report["scored_horizons"]) >= {"1d", "5d", "14d"}
    assert report["holding_rows"] > 0

    predictions = pd.read_parquet(PROJECT_ROOT / "reports" / "research_loop" / "predictions.parquet")
    assert set(predictions["horizon"].astype(str).unique()) >= {"1d", "5d", "14d"}
    assert {"probability_up", "probability_down", "target_label"}.issubset(predictions.columns)
    assert predictions["probability_up"].between(0, 1).all()
    assert predictions["probability_down"].between(0, 1).all()
    assert report["holding_rows"] > 0
    assert report["equity_curve_rows"] > 0


    for artifact in ["predictions.parquet", "holdings.parquet", "equity_curve.csv", "risk_report.parquet", "backtest_report.html"]:
        assert (PROJECT_ROOT / "reports" / "research_loop" / artifact).is_file()

    metrics = report["metrics"]
    for name in ["IC", "RankIC", "ICIR", "TopK_return", "Turnover", "Cost_adjusted_return", "MaxDrawdown", "Sharpe", "Calmar", "HitRate", "Capacity"]:
        assert name in metrics
    assert {"equal_weight", "random_industry_neutral", "momentum_baseline", "reversal_baseline", "qlib_alpha158_proxy"}.issubset(metrics["baseline_metrics"].keys())

    risk = pd.read_parquet(PROJECT_ROOT / "reports" / "research_loop" / "risk_report.parquet")
    assert {"industry_attribution", "style_attribution", "stock_selection_attribution", "transaction_cost_attribution", "capacity_curve", "risk_model_version"}.issubset(risk.columns)
    assert not risk.empty


def test_research_loop_experiment_recorder_and_backend_frontend_are_ready():
    report = _ensure_research_loop()
    run_id = report["run_id"]
    recorder = PROJECT_ROOT / "reports" / "research_loop" / "experiment_recorder" / run_id
    assert (recorder / "resolved_config.yaml").is_file()
    assert (recorder / "metrics.json").is_file()
    assert (recorder / "artifact_manifest.json").is_file()
    manifest = json.loads((recorder / "artifact_manifest.json").read_text(encoding="utf-8"))
    assert manifest["run_id"] == run_id
    assert manifest["config_hash"] == report["config_hash"]
    assert report["qlib_status"] in {"minimal_qlib_recorder_available", "qlib_workflow_blocked_minimal_recorder_used"}

    from backend.app.main import app
    from tests.auth_helpers import authenticated_admin_client

    client = authenticated_admin_client(app)
    dashboard = client.get("/api/dashboard")
    scores = client.get("/api/scores")
    backtests = client.get("/api/backtests")
    experiments = client.get("/api/experiments")
    assert dashboard.status_code == 200 and dashboard.json()["status"] == "research_loop_research_loop_ready"
    assert scores.status_code == 200 and scores.json()["status"] == "research_loop_scores_ready"
    scores_payload = scores.json()
    assert scores_payload["available_horizons"] == ["1d"]
    assert set(scores_payload["horizon_rankings"]) == {"1d"}
    assert len(scores_payload["horizon_rankings"]["1d"]) > 0
    assert "predicted_relative_change_pct" in scores_payload["horizon_rankings"]["1d"][0]
    assert scores_payload["model_family"] == "COGRASP current CSI300 retrained"
    assert scores_payload["prediction_target_date"] > scores_payload["latest_trade_date"]
    assert scores_payload["algorithm_modified"] is False
    sentiment_scores = client.get("/api/scores?model=sentiment_event")
    assert sentiment_scores.status_code == 200
    sentiment_payload = sentiment_scores.json()
    assert sentiment_payload["status"] == "research_loop_scores_ready"
    assert sentiment_payload["selected_model"] == "sentiment_event"
    assert sentiment_payload["model_family"] == "Sentiment Event Fusion LightGBM"
    assert sentiment_payload["text_sentiment_coverage"] >= 0
    assert {item["id"] for item in sentiment_payload["available_models"]} == {"cograsp", "sentiment_event"}
    assert backtests.status_code == 200 and backtests.json()["status"] == "research_loop_backtest_ready"
    assert experiments.status_code == 200 and experiments.json()["status"] == "research_loop_experiment_recorder_ready"

    for page, marker in [
        ("dashboard", "getConsolePage('dashboard')"),
        ("scores", "/api/scores"),
        ("backtests", "/api/backtests"),
    ]:
        text = (PROJECT_ROOT / "frontend" / "src" / "app" / page / "page.tsx").read_text(encoding="utf-8")
        assert marker in text


def test_research_loop_acceptance_script_reports_ok():
    from scripts.check_research_loop_acceptance import run_acceptance

    result = run_acceptance()
    assert result["status"] == "ok"
    assert result["checks"] == 19
    assert result["failed"] == []
    assert result["lightgbm_status"] == "trained"
    assert result["leakage_check_status"] == "passed"
    assert result["split_count"] >= 3
