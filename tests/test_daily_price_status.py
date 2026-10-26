from __future__ import annotations

import pandas as pd
import pytest
import sys
import types

from data.adapters import real_csi300_akshare as adapter
from scripts.backfill_daily_price_status import enrich_existing_daily


def fixture_frames():
    raw = pd.DataFrame({
        "symbol": ["000001.SZ"] * 3, "trade_date": ["2024-01-02", "2024-01-03", "2024-01-04"],
        "open": [10., 11., 12.], "high": [11., 12., 13.], "low": [9., 10., 11.],
        "close": [10.5, 11.5, 12.5], "volume": [100., 200., 300.], "amount": [1050., 2300., 3750.],
        "tradestatus": ["1"] * 3, "isST": ["0", "1", "0"],
    })
    adjusted = raw.drop(columns="isST").copy()
    adjusted[["open", "high", "low", "close"]] *= 100
    return adapter.normalize_real_daily_frame(adjusted), raw


def test_backfill_joins_dates_preserves_market_values_and_uses_daily_status():
    existing, raw = fixture_frames()
    result = enrich_existing_daily(existing, raw.iloc[::-1])
    assert result.raw_close.tolist() == [10.5, 11.5, 12.5]
    assert result.st_flag.tolist() == [False, True, False]
    assert result.adj_factor.eq(100).all()
    assert result.st_status_source.eq("baostock_daily_isST").all()
    for column in ["close", "volume", "amount", "trade_date", "symbol"]:
        pd.testing.assert_series_equal(result[column], existing[column])


@pytest.mark.parametrize("problem", ["missing_day", "duplicate_day", "missing_status", "bad_status", "volume_units", "invalid_price"])
def test_backfill_refuses_incomplete_or_inconsistent_sources(problem):
    existing, raw = fixture_frames()
    if problem == "missing_day":
        raw = raw.iloc[:2]
    elif problem == "duplicate_day":
        raw = pd.concat([raw, raw.iloc[:1]])
    elif problem == "missing_status":
        raw.loc[0, "isST"] = ""
    elif problem == "bad_status":
        raw.loc[0, "isST"] = "2"
    elif problem == "volume_units":
        raw.loc[0, "volume"] /= 100
    else:
        raw.loc[0, "close"] = 1000
    with pytest.raises((ValueError, RuntimeError)):
        enrich_existing_daily(existing, raw)


def test_normalization_does_not_infer_unknown_st_or_raw_price_from_current_name():
    existing, _ = fixture_frames()
    assert existing.st_flag.isna().all()
    assert existing.adj_factor.isna().all()
    assert existing.raw_close.isna().all()
    assert existing.st_status_source.eq("unknown").all()


def test_incremental_fallback_preserves_verified_st_and_detects_nullable_changes():
    existing, raw = fixture_frames()
    known = enrich_existing_daily(existing, raw)
    fallback = known.copy()
    fallback["st_flag"] = pd.Series(pd.NA, index=fallback.index, dtype="boolean")
    fallback["st_status_source"] = "unknown"
    result = adapter._merge_incremental_daily(known, fallback)
    assert result.st_flag.tolist() == [False, True, False]
    assert result.st_status_source.eq("baostock_daily_isST").all()
    assert adapter._dataset_change_summary(fallback, known)["revised_row_count"] == 3
    assert adapter._dataset_change_summary(known, known.copy())["data_changed"] is False


@pytest.mark.parametrize("corrupt", [False, True])
def test_publish_backs_up_original_and_never_publishes_incomplete_data(monkeypatch, tmp_path, corrupt):
    from scripts import backfill_daily_price_status as repair, update_daily_market_data as update

    monkeypatch.setattr(repair, "ROOT", tmp_path)
    monkeypatch.setattr(repair, "CACHE", tmp_path / "cache")
    monkeypatch.setattr(repair, "REPORT", tmp_path / "report.json")
    monkeypatch.setattr(adapter, "OUTPUT_DIR", tmp_path / "daily")
    monkeypatch.setattr(update, "PIPELINE_LOCK", tmp_path / "pipeline.lock")
    monkeypatch.setitem(sys.modules, "baostock", types.SimpleNamespace(
        login=lambda: types.SimpleNamespace(error_code="0"), logout=lambda: None,
    ))
    existing, raw = fixture_frames()
    adapter._atomic_write_parquet(existing, adapter._existing_daily_parquet_path())
    original = adapter._existing_daily_parquet_path().read_bytes()
    if corrupt:
        raw = raw.iloc[:2]
    adapter._atomic_write_parquet(raw, repair.CACHE / "000001.SZ_2024-01-02_2024-01-04.parquet")
    result = repair.run_backfill(publish=True)
    if corrupt:
        assert result["status"] == "failed" and result["published"] is False
        assert adapter._existing_daily_parquet_path().read_bytes() == original
    else:
        assert result["status"] == "ok" and result["published"] is True
        assert (tmp_path / result["backup"]).read_bytes() == original
        written = pd.read_parquet(adapter._existing_daily_parquet_path())
        assert written.st_flag.tolist() == [False, True, False]
        assert written.raw_close.tolist() == [10.5, 11.5, 12.5]
