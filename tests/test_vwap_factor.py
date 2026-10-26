from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from factors.offline.polars_factor_engine import (
    _build_factor_long, _build_feature_matrix, _factor_spec_yaml,
    _feature_registry_yaml, compute_factor_wide,
)


def source_frame() -> pd.DataFrame:
    dates = pd.bdate_range("2024-01-02", periods=16).strftime("%Y-%m-%d")
    return pd.DataFrame({
        "symbol": "600000.SH", "trade_date": dates, "stock_name": "sample",
        "open": 1020.0, "high": 1020.0, "low": 1020.0, "close": 1020.0,
        "volume": 1000.0, "amount": 10000.0, "adj_factor": 1.0,
        "industry_name": "sample", "eligible_universe": True, "tradable_flag": True,
        "delist_flag": False, "paused": False, "st_flag": False,
        "prediction_time": dates + "T16:00:00+08:00",
        "available_time": dates + "T15:30:00+08:00",
        "data_version": "test", "source_version": "test", "schema_version": "test",
        "trace_id": [f"test-{i}" for i in range(len(dates))],
    })


@pytest.mark.parametrize("mode", ["hfq", "qfq"])
def test_vwap_compares_unadjusted_close_even_with_large_adjustment(mode):
    source = source_frame().assign(adjustment_mode=mode, raw_close="10.2")
    wide, _ = compute_factor_wide(source)
    assert wide.vwap_deviation.to_numpy() == pytest.approx(np.full(len(wide), 0.02))
    assert wide.close.eq(1020).all()  # Price-return factors retain adjusted OHLC.
    assert wide.return_1d.dropna().eq(0).all()
    long = _build_factor_long(wide, ["vwap_deviation"])
    assert long.factor_value.to_numpy() == pytest.approx(np.full(len(wide), 0.02))


@pytest.mark.parametrize("mode", ["hfq", "qfq", None, "unknown"])
@pytest.mark.parametrize("raw_close", [None, np.nan, 0.0, -10.0, np.inf, "invalid"])
def test_vwap_does_not_fall_back_to_adjusted_or_unknown_price_basis(mode, raw_close):
    source = source_frame().assign(adjustment_mode=mode)
    if raw_close is not None:
        source["raw_close"] = raw_close
    wide, _ = compute_factor_wide(source)
    assert wide.vwap_deviation.isna().all()
    assert _build_feature_matrix(wide).vwap_deviation.isna().all()
    assert _build_factor_long(wide, ["vwap_deviation"]).empty


@pytest.mark.parametrize("mode", [None, "none", "raw", "unadjusted", "bfq", "3"])
def test_vwap_legacy_synthetic_or_explicit_unadjusted_close_remains_supported(mode):
    source = source_frame()
    source[["open", "high", "low", "close"]] = 10.2
    if mode is not None:
        source["adjustment_mode"] = mode
    wide, _ = compute_factor_wide(source)
    assert wide.vwap_deviation.to_numpy() == pytest.approx(np.full(len(wide), 0.02))


def test_vwap_price_basis_is_resolved_per_row_and_invalid_trade_values_remain_missing():
    source = source_frame().assign(adjustment_mode="hfq", raw_close=10.2)
    source.loc[1, "raw_close"] = np.nan
    source.loc[2, "volume"] = 0.0
    source.loc[3, "amount"] = 0.0
    source.loc[4, "volume"] = np.inf
    source.loc[5, "amount"] = np.inf
    source.loc[6, "adjustment_mode"] = "raw"
    source.loc[6, "raw_close"] = np.nan
    source.loc[6, ["open", "high", "low", "close"]] = 10.2
    wide, _ = compute_factor_wide(source)
    assert wide.vwap_deviation.iloc[[0, 6]].to_numpy() == pytest.approx([0.02, 0.02])
    assert wide.vwap_deviation.iloc[1:6].isna().all()


def test_vwap_definition_explains_basis_and_missing_value_rule():
    spec = _factor_spec_yaml()["factors"]["vwap_deviation"]
    registry = next(item for item in _feature_registry_yaml()["features"] if item["feature_name"] == "vwap_deviation")
    assert spec["formula"] == "raw_close / (amount/volume) - 1"
    assert "raw_close" in spec["required_fields"]
    assert "hfq/qfq" in spec["compatibility_rule"]
    assert "raw_close" in spec["missing_value_rule"]
    assert registry["fill_policy"] == spec["missing_value_rule"]
