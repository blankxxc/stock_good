from __future__ import annotations

import json

import pandas as pd
import pytest


@pytest.fixture
def materialized_features(monkeypatch, tmp_path):
    import feature_store.point_in_time_join.build_model_feature_matrix as pit

    monkeypatch.setattr(pit, "ROOT", tmp_path)
    monkeypatch.setattr(pit, "FEATURE_WIDE_DIR", tmp_path / "wide")
    monkeypatch.setattr(pit, "FACTOR_LONG_DIR", tmp_path / "long")
    monkeypatch.setattr(pit, "FEATURE_REGISTRY_PATH", tmp_path / "registry.yaml")
    monkeypatch.setattr(pit, "REPORT_PATH", tmp_path / "report.json")
    monkeypatch.setattr(pit, "_read_factor_long", lambda: pytest.fail("validation must not load the long panel"))
    pit.FEATURE_WIDE_DIR.mkdir()
    pit.FACTOR_LONG_DIR.mkdir()
    pit.FEATURE_REGISTRY_PATH.write_text("features:\n- feature_name: return_1d\n", encoding="utf-8")
    wide = pd.DataFrame({
        "trade_date": ["2024-01-02", "2024-01-03"],
        "symbol": ["600000.SH", "600000.SH"],
        "available_time": ["2024-01-02T15:30:00+08:00", "2024-01-03T15:30:00+08:00"],
        "prediction_time": ["2024-01-02T16:00:00+08:00", "2024-01-03T16:00:00+08:00"],
        "return_1d": [None, 0.02],
        "source_version": ["real_source_v2", "real_source_v2"],
        "data_version": ["real_data_v2", "real_data_v2"],
        "industry_name": ["bank", "bank"],
    })
    path = pit.FEATURE_WIDE_DIR / "part-000.parquet"
    wide.to_parquet(path, index=False)
    pd.DataFrame({"factor_value": [0.02]}).to_parquet(pit.FACTOR_LONG_DIR / "part-000.parquet", index=False)
    return pit, path, wide


def test_refresh_pit_report_preserves_materialized_matrix(materialized_features):
    pit, path, wide = materialized_features
    original_bytes = path.read_bytes()

    report = pit.build_model_feature_matrix(validate_existing=True)

    assert report["status"] == "ok"
    assert report["input_rows"] == 1
    assert report["output_rows"] == 2
    assert report["feature_count"] == 1
    assert report["latest_trade_date"] == "2024-01-03"
    assert report["point_in_time_violations"] == 0
    assert json.loads(pit.REPORT_PATH.read_text(encoding="utf-8")) == report
    assert path.read_bytes() == original_bytes
    pd.testing.assert_frame_equal(pd.read_parquet(path), wide)


@pytest.mark.parametrize("column,value", [
    ("available_time", None),
    ("available_time", "invalid"),
    ("prediction_time", ""),
    ("available_time", "2024-01-04T15:30:00+08:00"),
])
def test_refresh_pit_rejects_invalid_or_future_times(materialized_features, column, value):
    pit, path, wide = materialized_features
    wide.loc[1, column] = value
    wide.to_parquet(path, index=False)

    with pytest.raises(AssertionError, match="Point-in-time"):
        pit.build_model_feature_matrix(validate_existing=True)

    assert not pit.REPORT_PATH.exists()


def test_refresh_pit_rejects_missing_registered_feature(materialized_features):
    pit, path, wide = materialized_features
    wide.drop(columns="return_1d").to_parquet(path, index=False)

    with pytest.raises(AssertionError, match="missing columns.*return_1d"):
        pit.build_model_feature_matrix(validate_existing=True)


@pytest.mark.parametrize("engine_runtime,source_version,source_path", [
    ("real_csi300_recent_3y_daily_parquet", "baostock_daily_test", "data/real/csi300_daily"),
    ("pandas_pyarrow", "synthetic_mini_market_v001", "data/samples/synthetic_mini_market"),
])
def test_factor_report_identifies_actual_source(monkeypatch, tmp_path, engine_runtime, source_version, source_path):
    from data.adapters import benchmark_daily
    from data.adapters.real_csi300_akshare import normalize_real_daily_frame
    import factors.offline.polars_factor_engine as factors

    dates = pd.bdate_range("2024-01-02", periods=25).strftime("%Y-%m-%d")
    raw = normalize_real_daily_frame(pd.DataFrame({
        "trade_date": dates,
        "symbol": "600000.SH",
        "open": 10.0, "high": 11.0, "low": 9.0, "close": 10.0,
        "volume": 1000.0, "amount": 10_000.0,
    }))
    raw["source_version"] = source_version
    monkeypatch.setattr(factors, "_read_source", lambda: (raw, engine_runtime))
    monkeypatch.setattr(benchmark_daily, "read_benchmark_daily", pd.DataFrame)
    monkeypatch.setattr(factors, "REPORT_DIR", tmp_path)
    monkeypatch.setattr(factors, "FACTOR_REPORT_JSON", tmp_path / "factors.json")
    monkeypatch.setattr(factors, "_factor_reports", lambda _: ([], []))
    monkeypatch.setattr(factors, "_risk_outputs", lambda _: (pd.DataFrame(), pd.DataFrame(), pd.DataFrame()))
    monkeypatch.setattr(factors, "_write_summary_html", lambda _: None)

    report = factors.materialize_factor_store(write_outputs=False)

    assert report["source"] == source_path
    assert report["source_version"] == source_version
    assert report["source_versions"] == [source_version]
    assert report["latest_trade_date"] == dates[-1]
    assert report["source_row_count"] == len(raw)
