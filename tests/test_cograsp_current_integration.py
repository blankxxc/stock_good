from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_cograsp_submodule_provenance() -> None:
    upstream = PROJECT_ROOT / "third_party" / "COGRASP"
    if not upstream.exists():
        pytest.skip("COGRASP submodule has not been initialized")
    from models.cograsp_current import UPSTREAM_COMMIT

    assert UPSTREAM_COMMIT == "34e31f856ac396fa5ecea1f4410fe6c7d0bd5851"
    assert (upstream / "LICENSE").read_text(encoding="utf-8").startswith("MIT License")

def test_current_cograsp_dataset_and_published_score_artifact() -> None:
    market_path = PROJECT_ROOT / "data" / "real" / "csi300_daily" / "part-000.parquet"
    output_path = PROJECT_ROOT / "reports" / "research_loop" / "live_predictions.parquet"
    report_path = PROJECT_ROOT / "reports" / "research_loop" / "live_predictions_report.json"
    checkpoint_path = PROJECT_ROOT / "models" / "checkpoints" / "cograsp_current_csi300" / "model.pt"
    if not all(path.exists() for path in [market_path, output_path, report_path, checkpoint_path]):
        pytest.skip("Current COGRASP runtime artifacts have not been prepared")
    from models.cograsp_current import FEATURE_COLUMNS, prepare_current_dataset

    market = pd.read_parquet(market_path)
    latest_trade_date = pd.to_datetime(market["trade_date"]).max().strftime("%Y-%m-%d")
    prediction_target_date = (
        pd.Timestamp(latest_trade_date) + pd.offsets.BDay(1)
    ).strftime("%Y-%m-%d")
    dataset = prepare_current_dataset(market)
    assert dataset.features.shape[1:] == (300, 15, 10)
    assert dataset.targets.shape[1:] == (300,)
    assert dataset.target_dates[-1] == latest_trade_date
    assert list(FEATURE_COLUMNS) == [
        "open", "close", "high", "low", "amount", "volume", "amplitude", "momentum",
        "momentum_volume", "turnover",
    ]

    predictions = pd.read_parquet(output_path)
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert predictions["horizon"].eq("1d").all()
    assert predictions["model_family"].eq("COGRASP current CSI300 retrained").all()
    assert predictions["trade_date"].eq(latest_trade_date).all()
    assert predictions["prediction_target_date"].eq(prediction_target_date).all()
    assert predictions["predicted_relative_change_pct"].notna().all()
    assert predictions["probability_up"].isna().all()
    assert report["algorithm_modified"] is False
    assert report["architecture_modified"] is False
    assert report["data_pipeline_adapted"] is True
    assert report["model_output_rows"] == 300
    assert report["training_sample_count"] >= 100


def test_scores_payload_prefers_current_cograsp_artifact() -> None:
    report_path = PROJECT_ROOT / "reports" / "research_loop" / "live_predictions_report.json"
    if not report_path.exists():
        pytest.skip("COGRASP runtime artifacts have not been prepared")
    from backend.app.services.research_loop_catalog import scores_payload

    payload = scores_payload("research_signals_only_not_investment_advice")
    assert payload["model_family"] == "COGRASP current CSI300 retrained"
    assert payload["available_horizons"] == ["1d"]
    assert payload["algorithm_modified"] is False
    latest_trade_date = pd.to_datetime(
        pd.read_parquet(
            PROJECT_ROOT / "data" / "real" / "csi300_daily" / "part-000.parquet",
            columns=["trade_date"],
        )["trade_date"]
    ).max()
    expected_target_date = (latest_trade_date + pd.offsets.BDay(1)).strftime("%Y-%m-%d")
    assert payload["prediction_target_date"] == expected_target_date
    assert payload["display_score_rows"] == 300
    assert "predicted_relative_change_pct" in payload["horizon_rankings"]["1d"][0]
