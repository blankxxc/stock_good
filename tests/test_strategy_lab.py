from __future__ import annotations

import copy

import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient

from backend.app.services.strategy_lab import ExperimentRequest, run_experiment


def market_frame(days=35):
    dates = pd.bdate_range("2024-01-01", periods=days)
    rows = []
    for symbol, rate in [("000001.SZ", 0.01), ("600001.SH", -0.002), ("600002.SH", 0.001)]:
        for i, day in enumerate(dates):
            close = 10 * (1 + rate) ** i
            rows.append({"trade_date": day, "symbol": symbol, "stock_name": symbol,
                         "open": close / (1 + rate), "close": close, "volume": 1000,
                         "st_flag": False, "tradable_flag": True, "can_buy": True, "can_sell": True})
    return pd.DataFrame(rows)


def params(frame, **overrides):
    dates = sorted(frame.trade_date.unique())
    return ExperimentRequest(**{
        "start_date": pd.Timestamp(dates[8]).date(), "end_date": pd.Timestamp(dates[-1]).date(),
        "strategies": ["momentum", "reversal", "low_volatility", "trend"], "lookback": 5,
        "top_k": 1, "rebalance_days": 5, "fee_bps": 0, "slippage_bps": 0, **overrides,
    })


def test_next_open_execution_has_no_same_day_signal_leakage():
    frame = market_frame()
    config = params(frame)
    base = run_experiment(config, frame)
    changed = frame.copy()
    day = pd.Timestamp(config.start_date)
    changed.loc[(changed.symbol == "600001.SH") & (changed.trade_date == day), "close"] *= 100
    altered = run_experiment(config, changed)
    first = base["results"][0]["curve"][0]
    other = altered["results"][0]["curve"][0]
    assert first["holdings"][0]["symbol"] == other["holdings"][0]["symbol"] == "000001.SZ"
    assert first["nav"] == pytest.approx(1.01)
    assert first["signal_date"] < first["trade_date"]
    assert base["results"][1]["curve"][0]["holdings"][0]["symbol"] == "600001.SH"


def test_costs_cash_accounting_and_initial_drawdown():
    frame = market_frame()
    # Constant prices make the first buy's exact cost independently checkable.
    frame[["open", "close"]] = 10.0
    config = params(frame, strategies=["momentum"], fee_bps=10, slippage_bps=10, rebalance_days=60)
    result = run_experiment(config, frame)["results"][0]
    first = result["curve"][0]
    assert first["equity"] == pytest.approx(config.initial_capital / 1.002)
    assert first["cost"] == pytest.approx(config.initial_capital - first["equity"])
    assert result["metrics"]["max_drawdown"] == pytest.approx(1 / 1.002 - 1)
    assert result["metrics"]["trade_count"] == 1
    for point in result["curve"]:
        assert point["cash"] >= 0
        assert sum(h["market_value"] for h in point["holdings"]) + point["cash"] == pytest.approx(point["equity"])


def test_future_append_cannot_change_history_and_rebalance_cadence():
    frame = market_frame()
    config = params(frame, end_date="2024-02-01")
    original = run_experiment(config, frame)
    changed = frame.copy()
    changed.loc[changed.trade_date > pd.Timestamp(config.end_date), ["open", "close"]] *= 25
    replayed = run_experiment(config, changed)
    assert original["results"] == replayed["results"]
    for result in original["results"]:
        assert [i for i, point in enumerate(result["curve"]) if point["rebalance"]] == list(range(0, len(result["curve"]), 5))


def test_suspension_blocks_selling_and_preserves_position():
    frame = market_frame()
    config = params(frame, rebalance_days=1, strategies=["momentum"])
    dates = sorted(frame.trade_date.unique())
    # Force another winner after entry, then block sale of the original holding.
    frame.loc[(frame.symbol == "600001.SH") & (frame.trade_date >= dates[8]), ["open", "close"]] = 50.0
    frame.loc[(frame.symbol == "000001.SZ") & (frame.trade_date == dates[9]), "volume"] = 0
    result = run_experiment(config, frame)["results"][0]
    second = result["curve"][1]
    assert second["blocked_orders"] >= 1
    assert any(h["symbol"] == "000001.SZ" for h in second["holdings"])
    assert second["cash"] >= 0


def test_empty_trend_st_filter_and_unknown_abnormal_factors_hold_cash():
    frame = market_frame()
    frame.loc[frame.symbol != "600001.SH", "st_flag"] = True
    result = run_experiment(params(frame, strategies=["trend"]), frame)["results"][0]
    assert all(p["holding_count"] == 0 and p["nav"] == 1 for p in result["curve"])
    result = run_experiment(params(frame, exclude_abnormal=True), frame, benchmark_daily=pd.DataFrame())
    assert all(p["holding_count"] == 0 for s in result["results"] for p in s["curve"])


def test_extreme_return_filter_uses_existing_factor_definition():
    frame = market_frame()
    frame.loc[frame.symbol == "000001.SZ", "close"] = 10 * 1.1 ** np.arange(35)
    config = params(frame, start_date="2024-01-22", strategies=["momentum"], exclude_extreme=True)
    result = run_experiment(config, frame, benchmark_daily=pd.DataFrame())["results"][0]
    assert all(h["symbol"] != "000001.SZ" for p in result["curve"] for h in p["holdings"])


def test_unknown_st_is_excluded_and_coverage_uses_signal_dates():
    frame = market_frame()
    frame["st_flag"] = frame.st_flag.astype("boolean")
    frame.loc[frame.symbol == "000001.SZ", "st_flag"] = pd.NA
    frame.loc[frame.symbol == "600001.SH", "st_flag"] = True
    config = params(frame, strategies=["momentum"])
    result = run_experiment(config, frame)
    assert all(h["symbol"] == "600002.SH" for p in result["results"][0]["curve"] for h in p["holdings"])
    rebalance_count = sum(p["rebalance"] for p in result["results"][0]["curve"])
    assert result["st_coverage"] == {
        "scope": "rebalance_signal_stock_days", "observation_count": 3 * rebalance_count,
        "known_st_count": rebalance_count, "known_non_st_count": rebalance_count,
        "unknown_count": rebalance_count, "known_fraction": 2 / 3, "exclude_unknown": True,
    }
    unfiltered = run_experiment(params(frame, strategies=["momentum"], exclude_st=False), frame)
    assert unfiltered["results"][0]["curve"][0]["holdings"][0]["symbol"] == "000001.SZ"
    assert unfiltered["st_coverage"]["exclude_unknown"] is False


@pytest.mark.parametrize("missing_status", ["column", "invalid"])
def test_absent_or_invalid_st_status_is_unknown_not_non_st(missing_status):
    frame = market_frame()
    if missing_status == "column":
        frame = frame.drop(columns="st_flag")
    else:
        frame["st_flag"] = "unavailable"
    result = run_experiment(params(frame, strategies=["momentum"]), frame)
    assert all(p["holding_count"] == 0 and p["nav"] == 1 for p in result["results"][0]["curve"])
    assert result["st_coverage"]["unknown_count"] == result["st_coverage"]["observation_count"]
    assert result["st_coverage"]["known_fraction"] == 0


def test_st_filter_uses_previous_signal_day_and_not_execution_day():
    frame = market_frame()
    config = params(frame, strategies=["momentum"], rebalance_days=1)
    frame["st_flag"] = frame.st_flag.astype("boolean")
    frame.loc[(frame.symbol == "000001.SZ") & (frame.trade_date == pd.Timestamp(config.start_date)), "st_flag"] = pd.NA
    result = run_experiment(config, frame)["results"][0]
    assert result["curve"][0]["holdings"][0]["symbol"] == "000001.SZ"
    assert all(h["symbol"] != "000001.SZ" for h in result["curve"][1]["holdings"])


def test_metadata_reports_unknown_st_history(monkeypatch):
    import backend.app.services.strategy_lab as service

    frame = market_frame().drop(columns="st_flag")
    monkeypatch.setattr(service, "load_market", lambda: (frame, "fixture"))
    coverage = service.lab_metadata()["st_coverage"]
    assert coverage["scope"] == "available_history_rows"
    assert coverage["observation_count"] == coverage["unknown_count"] == len(frame)
    assert coverage["known_fraction"] == 0


@pytest.mark.parametrize("overrides", [
    {"start_date": "2025-01-01"}, {"end_date": "2025-01-01"},
    {"start_date": "2024-01-01"}, {"strategies": ["momentum", "momentum"]},
])
def test_invalid_ranges_and_duplicate_strategies_rejected(overrides):
    frame = market_frame()
    with pytest.raises(ValueError):
        run_experiment(params(frame, **overrides), frame)


def test_api_validation_metadata_and_run(monkeypatch):
    import backend.app.services.strategy_lab as service
    from backend.app.main import app

    frame = market_frame()
    monkeypatch.setattr(service, "load_market", lambda: (frame, "fixture-sha256"))
    client = TestClient(app)
    metadata = client.get("/api/strategy-lab")
    assert metadata.status_code == 200
    assert len(metadata.json()["strategies"]) == 4
    config = params(frame).model_dump(mode="json")
    response = client.post("/api/strategy-lab/run", json=config)
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    payload = response.json()
    assert payload["data_fingerprint"] == "fixture-sha256"
    assert len(payload["results"]) == 4
    assert payload["results"][0]["metrics"]["total_return"] > payload["results"][1]["metrics"]["total_return"]
    invalid = copy.deepcopy(config)
    invalid["top_k"] = 0
    assert client.post("/api/strategy-lab/run", json=invalid).status_code == 422
    invalid = {**config, "strategies": ["retired_model"]}
    assert client.post("/api/strategy-lab/run", json=invalid).status_code == 422
    invalid = {**config, "start_date": "2025-01-01"}
    assert client.post("/api/strategy-lab/run", json=invalid).status_code == 422
