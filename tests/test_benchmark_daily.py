from __future__ import annotations

import sys
from types import SimpleNamespace

import pandas as pd
import pytest

from data.adapters import benchmark_daily as adapter


def _sample():
    return pd.DataFrame([
        {"trade_date": date, "index_symbol": symbol, "close": price}
        for symbol in adapter.INDEX_CODES
        for date, price in [("2024-01-02", 100), ("2024-01-03", 101)]
    ])


def test_update_is_idempotent_and_failed_refresh_preserves_cache(monkeypatch, tmp_path):
    monkeypatch.setattr(adapter, "BENCHMARK_PATH", tmp_path / "benchmark.parquet")
    monkeypatch.setattr(adapter, "fetch_benchmark_daily", lambda *_: _sample())
    report = adapter.update_benchmark_daily("2024-01-02", "2024-01-03")
    assert report["status"] == "ok" and report["rows"] == 4
    assert adapter.update_benchmark_daily("2024-01-02", "2024-01-03")["status"] == "no_change"
    before = adapter.BENCHMARK_PATH.read_bytes()
    monkeypatch.setattr(adapter, "fetch_benchmark_daily", lambda *_: _sample().iloc[:2])
    with pytest.raises(ValueError, match="does not cover"):
        adapter.update_benchmark_daily("2024-01-02", "2024-01-03")
    assert adapter.BENCHMARK_PATH.read_bytes() == before


def test_index_provider_requests_daily_unadjusted_prices_and_logs_out(monkeypatch):
    calls = []
    class Query:
        error_code, error_msg = "0", ""
        fields = ["date", "code", "close"]
        def __init__(self, code):
            self.code, self.remaining = code, 1
        def next(self):
            self.remaining -= 1
            return self.remaining >= 0
        def get_row_data(self):
            return ["2024-01-02", self.code, "100"]
    def query(code, fields, **kwargs):
        calls.append((code, fields, kwargs))
        return Query(code)
    logout = []
    monkeypatch.setitem(sys.modules, "baostock", SimpleNamespace(
        login=lambda: SimpleNamespace(error_code="0"), logout=lambda: logout.append(True),
        query_history_k_data_plus=query,
    ))
    frame = adapter.fetch_benchmark_daily("2024-01-02", "2024-01-02")
    assert set(frame.index_symbol) == set(adapter.INDEX_CODES)
    assert [c[0] for c in calls] == ["sh.000001", "sz.399001"]
    assert all(c[2]["frequency"] == "d" and c[2]["adjustflag"] == "3" for c in calls)
    assert logout == [True]
