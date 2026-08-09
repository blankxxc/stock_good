from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_finmamba_official_source_is_pinned_and_unmodified() -> None:
    upstream = PROJECT_ROOT / "third_party" / "FinMamba"
    if not upstream.exists():
        pytest.skip("FinMamba source has not been initialized")
    from models.finmamba_official_adapter import (
        MODEL_VERSION,
        UPSTREAM_COMMIT,
        upstream_source_status,
    )

    status = upstream_source_status()
    assert UPSTREAM_COMMIT == "e4f8ce33e4ddbc4a46b738de9265771aec2c4d16"
    assert MODEL_VERSION == "finmamba-official-e4f8ce33e4dd"
    assert status["source_present"] is True
    assert status["license"] == "Apache-2.0"
    assert status["architecture_modified"] is False


def test_finmamba_adapter_writes_author_input_contract(tmp_path: Path) -> None:
    from models.finmamba_official_adapter import FEATURE_COLUMNS, write_official_inputs

    dates = pd.bdate_range("2025-01-02", periods=90).strftime("%Y-%m-%d")
    rows = []
    for date_index, date in enumerate(dates):
        for symbol_index, symbol in enumerate(("000001.SZ", "600000.SH", "600519.SH")):
            close = 10.0 + symbol_index + date_index * 0.01
            rows.append(
                {
                    "trade_date": date,
                    "symbol": symbol,
                    "stock_name": symbol,
                    "industry_name": "银行" if symbol_index < 2 else "食品饮料",
                    "open": close - 0.02,
                    "high": close + 0.05,
                    "low": close - 0.05,
                    "close": close,
                    "volume": 1_000_000 + date_index * 100 + symbol_index,
                    "turnover_rate": 1.0 + symbol_index * 0.1,
                }
            )
    report = write_official_inputs(pd.DataFrame(rows), output_dir=tmp_path)

    features = pd.read_pickle(tmp_path / "csi300fea.pkl").reset_index()
    labels = pd.read_pickle(tmp_path / "csi300lab.pkl").reset_index()
    all_features = pd.read_pickle(tmp_path / "csi300_allfea.pkl").reset_index()
    relation = np.load(tmp_path / "csi300_industry_relationship.npy")
    assert list(features.columns[2:]) == list(FEATURE_COLUMNS)
    assert len(all_features) == 90 * 3
    assert len(features) == 89 * 3
    assert len(labels) == 89 * 3
    assert labels["label"].notna().all()
    assert relation.shape == (3, 3)
    assert relation[0, 1] == pytest.approx(1.0)
    assert relation[0, 2] == pytest.approx(0.1)
    assert report["architecture_modified"] is False
    assert report["algorithm_modified"] is False
    assert report["data_pipeline_adapted"] is True


def test_finmamba_is_exposed_by_scores_catalog() -> None:
    from backend.app.services.research_loop_catalog import scores_payload

    payload = scores_payload("research_signals_only_not_investment_advice", model="finmamba")
    assert payload["selected_model"] == "finmamba"
    assert any(option["id"] == "finmamba" for option in payload["available_models"])
    if payload["status"] != "research_loop_scores_ready":
        assert payload["integration_status"]
        assert payload["runtime_requirements"]
