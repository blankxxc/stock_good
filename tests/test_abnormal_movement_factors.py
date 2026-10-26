from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from factors.offline.abnormal_movement import (
    FLAG_NAMES, MOVEMENT_FLAG, RETURN_FLAG, compute_abnormal_movement_factors,
)


def _daily(closes, symbol="600000.SH"):
    dates = pd.bdate_range("2024-01-02", periods=len(closes)).strftime("%Y-%m-%d")
    return pd.DataFrame({
        "symbol": symbol, "trade_date": dates, "close": closes,
        "available_time": dates + "T15:30:00+08:00", "prediction_time": dates + "T16:00:00+08:00",
    })


def _benchmark(daily, closes=None, symbol="000001.SH"):
    return pd.DataFrame({
        "trade_date": daily.trade_date, "index_symbol": symbol,
        "close": 100.0 if closes is None else closes,
        "available_time": daily.available_time,
    })


@pytest.mark.parametrize("last,expected", [(19.99, 0), (20.0, 0), (20.01, 1)])
def test_ten_day_gain_strict_threshold_and_warmup(last, expected):
    daily = _daily([10.0] * 10 + [last])
    flags = compute_abnormal_movement_factors(daily, _benchmark(daily, [100.0] * 10 + [300.0]))
    assert flags[RETURN_FLAG].iloc[:10].isna().all()
    assert flags[RETURN_FLAG].iloc[10] == expected  # Index gain never reduces this flag.


@pytest.mark.parametrize("multiplier,expected", [(1.2, 0), (1.2001, 1), (0.75, 0)])
def test_one_day_events_strict_twenty_percent_and_no_downward_events(multiplier, expected):
    daily = _daily(10 * np.power(multiplier, np.arange(11)))
    flags = compute_abnormal_movement_factors(daily, _benchmark(daily))
    # At exactly +20%, two days can still form an event: use isolated moves.
    if multiplier == 1.2:
        daily = _daily([10, 12, 10, 12, 10, 12, 10, 12, 10, 12, 10])
        flags = compute_abnormal_movement_factors(daily, _benchmark(daily))
    assert flags[MOVEMENT_FLAG].iloc[-1] == expected


def test_two_day_events_reset_and_expire_from_ten_day_window():
    # Two +10% days compound to +21%, yielding events on days 2,4,6,8,10.
    closes = list(10 * np.power(1.1, np.arange(11))) + [10 * 1.1**10] * 5
    daily = _daily(closes)
    flags = compute_abnormal_movement_factors(daily, _benchmark(daily))
    assert flags[MOVEMENT_FLAG].iloc[:10].isna().all()
    assert flags[MOVEMENT_FLAG].iloc[10:14].eq(1).all()
    assert flags[MOVEMENT_FLAG].iloc[14] == 0  # Event on day 4 is now outside [5,14].


def test_three_day_events_are_not_double_counted_in_overlapping_windows():
    daily = _daily(10 * np.power(1.07, np.arange(22)))
    flags = compute_abnormal_movement_factors(daily, _benchmark(daily))
    # +7% per day exceeds 20% only after 3 days. Events: 3,6,9,12,...
    assert flags[MOVEMENT_FLAG].iloc[10] == 0
    assert flags[MOVEMENT_FLAG].iloc[12] == 1  # 3,6,9,12 all in [3,12].
    assert flags[MOVEMENT_FLAG].iloc[13] == 0


def test_exchange_mapping_subtracts_compound_index_return():
    sh = _daily(10 * np.power(1.11, np.arange(11)))
    sz = sh.assign(symbol="000001.SZ")
    benchmarks = pd.concat([
        _benchmark(sh, 100 * np.power(1.02, np.arange(11))),
        _benchmark(sz, symbol="399001.SZ"),
    ], ignore_index=True)
    flags = compute_abnormal_movement_factors(pd.concat([sh, sz], ignore_index=True), benchmarks)
    assert flags[MOVEMENT_FLAG].iloc[10] == 0  # 23.21%-4.04%=19.17%, requires 3 days.
    assert flags[MOVEMENT_FLAG].iloc[21] == 1  # Shenzhen flat: +23.21% in 2 days.


def test_missing_benchmarks_remain_unknown_and_do_not_change_raw_gain():
    daily = _daily(10 * np.power(1.1, np.arange(21)))
    missing = compute_abnormal_movement_factors(daily, pd.DataFrame())
    assert missing[MOVEMENT_FLAG].isna().all()
    assert missing[RETURN_FLAG].iloc[10] == 1
    unknown_exchange = compute_abnormal_movement_factors(daily.assign(symbol="430001.BJ"), _benchmark(daily))
    assert unknown_exchange[MOVEMENT_FLAG].isna().all()
    benchmark = _benchmark(daily).drop(index=10)
    gap = compute_abnormal_movement_factors(daily, benchmark)
    assert gap[MOVEMENT_FLAG].iloc[10:21].isna().all()


def test_missing_stock_session_and_late_index_are_not_filled():
    daily = _daily(10 * np.power(1.1, np.arange(23)))
    benchmark = _benchmark(daily)
    missing_session = compute_abnormal_movement_factors(daily.drop(index=10), benchmark)
    assert missing_session.loc[11:20, FLAG_NAMES].isna().all().all()
    benchmark.loc[10, "available_time"] = "2024-12-31T15:30:00+08:00"
    late = compute_abnormal_movement_factors(daily, benchmark)
    assert late[MOVEMENT_FLAG].iloc[10:21].isna().all()
    assert late[MOVEMENT_FLAG].iloc[21] == 1


def test_order_independence_and_future_rows_do_not_rewrite_past():
    daily = _daily(10 * np.power(1.1, np.arange(30)))
    benchmark = _benchmark(daily)
    full = compute_abnormal_movement_factors(daily, benchmark)
    prefix = compute_abnormal_movement_factors(daily.iloc[:15], benchmark.iloc[:15])
    pd.testing.assert_frame_equal(full.iloc[:15], prefix)
    shuffled = compute_abnormal_movement_factors(daily.sample(frac=1, random_state=4), benchmark)
    pd.testing.assert_frame_equal(full, shuffled.sort_index())


def test_registered_flags_materialize_and_keep_missing_values():
    from data.adapters.real_csi300_akshare import normalize_real_daily_frame
    from factors.offline.polars_factor_engine import (
        FACTOR_NAMES, _build_factor_long, _build_feature_matrix, _factor_spec_yaml,
        _feature_registry_yaml, compute_factor_wide,
    )
    daily = _daily(10 * np.power(1.1, np.arange(25)))
    raw = daily.assign(open=daily.close, high=daily.close, low=daily.close, volume=1000, amount=daily.close * 1000)
    source = normalize_real_daily_frame(raw)
    wide, _ = compute_factor_wide(source, _benchmark(daily))
    assert len(FACTOR_NAMES) == 76
    assert wide[FLAG_NAMES].iloc[10].eq(1).all()
    assert set(FLAG_NAMES).issubset(_build_factor_long(wide).factor_name)
    assert _build_feature_matrix(wide)[FLAG_NAMES].iloc[:10].isna().all().all()
    specs = _factor_spec_yaml()["factors"]
    assert specs[MOVEMENT_FLAG]["benchmark_mapping"] == {"SH": "000001.SH", "SZ": "399001.SZ"}
    assert set(FLAG_NAMES).issubset({x["feature_name"] for x in _feature_registry_yaml()["features"]})


def test_screening_keeps_unknown_flags_and_ignores_stale_materialized_values(monkeypatch):
    import backend.app.services.research_loop_catalog as catalog
    from data.adapters.real_csi300_akshare import normalize_real_daily_frame
    from data.adapters import benchmark_daily

    daily = _daily(10 * np.power(1.1, np.arange(25)))
    daily = normalize_real_daily_frame(daily.assign(open=daily.close, high=daily.close, low=daily.close,
                                                  volume=1000, amount=daily.close * 1000, turnover_rate=1))
    monkeypatch.setattr(catalog, "_real_csi300_daily", lambda: daily)
    monkeypatch.setattr(benchmark_daily, "read_benchmark_daily", pd.DataFrame)
    monkeypatch.setattr(catalog, "_factor_daily_panel_wide", lambda date: (
        pd.DataFrame({"symbol": ["600000.SH"], "trade_date": [date], RETURN_FLAG: [0], MOVEMENT_FLAG: [1]}),
        FLAG_NAMES, {},
    ))
    payload = catalog.condition_screen_payload("test")
    row = payload["rows"][0]
    assert row[RETURN_FLAG] is True
    assert row[MOVEMENT_FLAG] is None
    for name in FLAG_NAMES:
        assert name in payload["available_factor_columns"]
        assert payload["column_schema"][name]["type"] == "boolean"
