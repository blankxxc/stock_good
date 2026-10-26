from concurrent.futures import ThreadPoolExecutor
from threading import Event

import pytest

from backend.app.services.file_payload_cache import file_payload_cache


def test_updates_creation_removal_and_nested_results_are_not_stale(tmp_path):
    source = tmp_path / "daily.json"
    calls = []

    @file_payload_cache(lambda: [source])
    def read():
        calls.append(1)
        return {"rows": [source.read_text() if source.exists() else None]}

    assert read() == {"rows": [None]}
    source.write_text("first")
    read()["rows"].append("caller mutation")
    assert read() == {"rows": ["first"]}
    replacement = tmp_path / "new.json"
    replacement.write_text("revised data")
    replacement.replace(source)
    assert read() == {"rows": ["revised data"]}
    source.unlink()
    assert read() == {"rows": [None]}
    assert len(calls) == 4


def test_partition_changes_invalidate_and_cache_is_bounded(tmp_path):
    source = tmp_path / "panel"
    source.mkdir()
    calls = []

    @file_payload_cache(lambda: [source], maxsize=2)
    def read(symbol):
        calls.append(symbol)
        return len(list(source.rglob("*.parquet")))

    assert read("a") == read("a") == 0
    nested = source / "trade_date=2026-10-16"
    nested.mkdir()
    (nested / "part.parquet").write_bytes(b"updated")
    assert read("a") == 1
    read("b")
    read("c")
    read("a")
    assert calls == ["a", "a", "b", "c", "a"]


def test_concurrent_readers_share_work_and_errors_can_retry(tmp_path):
    started, release = Event(), Event()
    calls = []

    @file_payload_cache(lambda: [tmp_path / "missing.json"])
    def read():
        calls.append(1)
        started.set()
        assert release.wait(5)
        return {"value": [1]}

    with ThreadPoolExecutor(max_workers=6) as pool:
        tasks = [pool.submit(read) for _ in range(6)]
        assert started.wait(5)
        release.set()
        results = [task.result(timeout=5) for task in tasks]
    assert len(calls) == 1
    results[0]["value"].append(2)
    assert all(result == {"value": [1]} for result in results[1:])

    attempts = []

    @file_payload_cache(lambda: [])
    def flaky():
        attempts.append(1)
        if len(attempts) == 1:
            raise ValueError("unfinished write")
        return "ok"

    with pytest.raises(ValueError, match="unfinished write"):
        flaky()
    assert flaky() == flaky() == "ok"
    assert len(attempts) == 2


def test_source_changed_during_computation_is_not_retained(tmp_path):
    source = tmp_path / "report.json"
    source.write_text("old")
    calls = []

    @file_payload_cache(lambda: [source])
    def read():
        calls.append(1)
        result = source.read_text()
        if len(calls) == 1:
            source.write_text("new revision")
        return result

    assert read() == "old"
    assert read() == read() == "new revision"
    assert len(calls) == 2


def test_factor_library_does_not_build_an_unused_network(monkeypatch):
    from backend.app.services import factor_store_catalog, relation_graph_catalog

    def unexpected(*args, **kwargs):
        raise AssertionError("Factor library should not load network nodes and edges")

    monkeypatch.setattr(relation_graph_catalog, "relation_network_payload", unexpected)
    payload = factor_store_catalog.factor_payload.__wrapped__("test")
    assert "network" not in payload.get("relation_graph", {})


def test_screening_refreshes_after_daily_index_and_factor_updates(tmp_path, monkeypatch):
    import numpy as np
    import pandas as pd
    from backend.app.services import research_loop_catalog as catalog
    from data.adapters import benchmark_daily
    from data.adapters.real_csi300_akshare import normalize_real_daily_frame
    from factors.offline.abnormal_movement import MOVEMENT_FLAG, RETURN_FLAG

    dates = pd.bdate_range("2026-09-01", periods=12).strftime("%Y-%m-%d")
    close = 10 * np.power(1.1, np.arange(12))
    raw = pd.DataFrame({"symbol": "600000.SH", "trade_date": dates, "close": close,
                        "open": close, "high": close, "low": close, "volume": 1000,
                        "amount": close * 1000, "turnover_rate": 1})
    daily = normalize_real_daily_frame(raw)
    daily_path = tmp_path / "data/real/csi300_daily/part-000.parquet"
    index_path = tmp_path / "data/real/benchmark_daily/part-000.parquet"
    factor_path = tmp_path / "data/gold/factor_daily_panel_long/part-000.parquet"
    for path in (daily_path, index_path, factor_path):
        path.parent.mkdir(parents=True, exist_ok=True)
    daily.to_parquet(daily_path, index=False)
    index = pd.DataFrame({"index_symbol": "000001.SH", "trade_date": dates, "close": 100.0})
    index.to_parquet(index_path, index=False)
    factors = pd.DataFrame({"symbol": ["600000.SH"], "trade_date": [dates[-1]],
                            "factor_name": ["momentum_20d"], "factor_value": [0.1], "category": ["test"]})
    factors.to_parquet(factor_path, index=False)
    monkeypatch.setattr(catalog, "project_root", lambda: tmp_path)
    monkeypatch.setattr(benchmark_daily, "BENCHMARK_PATH", index_path)

    def latest():
        return catalog.condition_screen_payload("test")["rows"][0]

    assert latest()[MOVEMENT_FLAG] is True
    index["close"] = close * 10
    index.to_parquet(index_path, index=False)
    assert latest()[MOVEMENT_FLAG] is False
    assert latest()[RETURN_FLAG] is True
    factors["factor_value"] = 0.25
    factors.to_parquet(factor_path, index=False)
    assert latest()["momentum_20d"] == 0.25
    daily.loc[daily.index[-1], "close"] = 10.0
    daily.to_parquet(daily_path, index=False)
    assert latest()[RETURN_FLAG] is False
