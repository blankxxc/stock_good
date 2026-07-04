from __future__ import annotations

import json
import sys
import types

import pandas as pd


def test_real_csi300_adapter_normalizes_required_research_schema():
    from data.adapters.real_csi300_akshare import normalize_real_daily_frame

    raw = pd.DataFrame(
        {
            "trade_date": ["2024-01-02", "2024-01-03"],
            "symbol": ["000001", "600000"],
            "open": [10.0, 20.0],
            "high": [11.0, 21.0],
            "low": [9.5, 19.5],
            "close": [10.5, 20.5],
            "volume": [1000, 2000],
            "amount": [10500, 41000],
        }
    )

    out = normalize_real_daily_frame(raw, {"000001.SZ": "平安银行", "600000.SH": "浦发银行"})

    required = {
        "trade_date",
        "symbol",
        "stock_name",
        "open",
        "high",
        "low",
        "close",
        "volume",
        "amount",
        "available_time",
        "prediction_time",
        "eligible_universe",
        "tradable_flag",
        "can_buy",
        "can_sell",
        "source_version",
        "data_version",
        "research_boundary",
    }
    assert required.issubset(out.columns)
    assert set(out["symbol"]) == {"000001.SZ", "600000.SH"}
    assert out["tradable_flag"].all()
    assert out["data_version"].eq("real_csi300_recent_3y_daily_v001").all()


def test_akshare_constituent_parser_prefers_stock_code_over_index_code(monkeypatch):
    import data.adapters.real_csi300_akshare as adapter

    fake_akshare = types.SimpleNamespace(
        index_stock_cons_csindex=lambda symbol: pd.DataFrame(
            {
                "日期": ["2026-06-11", "2026-06-11"],
                "指数代码": ["000300", "000300"],
                "指数名称": ["沪深300", "沪深300"],
                "成分券代码": ["000001", "600000"],
                "成分券名称": ["平安银行", "浦发银行"],
                "交易所": ["深圳证券交易所", "上海证券交易所"],
            }
        ),
        index_stock_cons=lambda symbol: pd.DataFrame(),
    )
    monkeypatch.setitem(sys.modules, "akshare", fake_akshare)

    out = adapter.fetch_current_csi300_constituents_akshare()

    assert out.to_dict("records") == [
        {"symbol": "000001.SZ", "name": "平安银行"},
        {"symbol": "600000.SH", "name": "浦发银行"},
    ]


def test_real_csi300_writer_can_materialize_parquet_with_mocked_provider(monkeypatch, tmp_path):
    import data.adapters.real_csi300_akshare as adapter

    monkeypatch.setattr(adapter, "OUTPUT_DIR", tmp_path / "csi300_daily")
    monkeypatch.setattr(adapter, "REPORT_PATH", tmp_path / "report.json")
    monkeypatch.setattr(
        adapter,
        "fetch_current_csi300_constituents",
        lambda: pd.DataFrame({"symbol": ["000001.SZ", "600000.SH"], "name": ["平安银行", "浦发银行"]}),
    )

    def fake_hist(symbol: str, start_date: str, end_date: str) -> pd.DataFrame:
        return pd.DataFrame(
            {
                "trade_date": ["2024-01-02", "2024-01-03", "2024-01-04"],
                "symbol": [symbol, symbol, symbol],
                "open": [10.0, 10.2, 10.3],
                "high": [10.5, 10.6, 10.7],
                "low": [9.8, 10.0, 10.1],
                "close": [10.1, 10.4, 10.6],
                "volume": [1000, 1200, 1300],
                "amount": [10100, 12480, 13780],
            }
        )

    monkeypatch.setattr(adapter, "fetch_symbol_daily", fake_hist)

    report = adapter.write_real_csi300_daily(start_date="20240101", end_date="20240110")
    data = pd.read_parquet(tmp_path / "csi300_daily" / "part-000.parquet")
    saved_report = json.loads((tmp_path / "report.json").read_text(encoding="utf-8"))

    assert report["status"] == "ok"
    assert saved_report["data_source_mode"] == "real_csi300_recent_3y_daily"
    assert report["stock_count"] == 2
    assert len(data) == 6
    assert data["source"].eq("baostock_or_akshare_public_web").all()


def test_real_csi300_writer_incrementally_merges_existing_parquet_and_refreshes_overlap(monkeypatch, tmp_path):
    import data.adapters.real_csi300_akshare as adapter

    output_dir = tmp_path / "csi300_daily"
    monkeypatch.setattr(adapter, "OUTPUT_DIR", output_dir)
    monkeypatch.setattr(adapter, "REPORT_PATH", tmp_path / "report.json")
    monkeypatch.setattr(
        adapter,
        "fetch_current_csi300_constituents",
        lambda: pd.DataFrame({"symbol": ["000001.SZ", "600000.SH"], "name": ["平安银行", "浦发银行"]}),
    )

    names = {"000001.SZ": "平安银行", "600000.SH": "浦发银行"}
    existing = adapter.normalize_real_daily_frame(
        pd.DataFrame(
            {
                "trade_date": ["2024-01-02", "2024-01-03", "2024-01-02", "2024-01-03"],
                "symbol": ["000001.SZ", "000001.SZ", "600000.SH", "600000.SH"],
                "open": [10.0, 10.1, 20.0, 20.1],
                "high": [10.5, 10.6, 20.5, 20.6],
                "low": [9.8, 9.9, 19.8, 19.9],
                "close": [10.2, 10.3, 20.2, 20.3],
                "volume": [1000, 1100, 2000, 2100],
                "amount": [10200, 11330, 40400, 42630],
            }
        ),
        names,
    )
    output_dir.mkdir(parents=True)
    existing.to_parquet(output_dir / "part-000.parquet", index=False)

    calls: list[tuple[str, str, str]] = []

    def fake_hist(symbol: str, start_date: str, end_date: str) -> pd.DataFrame:
        calls.append((symbol, start_date, end_date))
        assert start_date == "20240102"
        assert end_date == "20240105"
        base = 10.0 if symbol == "000001.SZ" else 20.0
        return pd.DataFrame(
            {
                "trade_date": ["2024-01-03", "2024-01-04"],
                "symbol": [symbol, symbol],
                "open": [base + 1.0, base + 2.0],
                "high": [base + 1.5, base + 2.5],
                "low": [base + 0.5, base + 1.5],
                "close": [base + 1.2, base + 2.2],
                "volume": [9000, 9100],
                "amount": [100000, 110000],
            }
        )

    monkeypatch.setattr(adapter, "fetch_symbol_daily", fake_hist)

    report = adapter.write_real_csi300_daily(
        start_date="20240101",
        end_date="20240105",
        incremental=True,
        overlap_days=1,
    )
    data = pd.read_parquet(output_dir / "part-000.parquet")

    assert report["status"] == "ok"
    assert report["data_source_mode"] == "real_csi300_daily_incremental"
    assert report["incremental_update"] is True
    assert report["previous_latest_trade_date"] == "2024-01-03"
    assert report["requested_incremental_start_date"] == "20240102"
    assert {call[0] for call in calls} == {"000001.SZ", "600000.SH"}
    assert len(data) == 6
    assert data.groupby("trade_date")["symbol"].nunique().to_dict() == {
        "2024-01-02": 2,
        "2024-01-03": 2,
        "2024-01-04": 2,
    }
    refreshed = data[(data["symbol"] == "000001.SZ") & (data["trade_date"] == "2024-01-03")].iloc[0]
    assert refreshed["close"] == 11.2


def test_real_csi300_incremental_can_use_quote_snapshot_without_slow_history_provider(monkeypatch, tmp_path):
    import data.adapters.real_csi300_akshare as adapter

    output_dir = tmp_path / "csi300_daily"
    monkeypatch.setattr(adapter, "OUTPUT_DIR", output_dir)
    monkeypatch.setattr(adapter, "REPORT_PATH", tmp_path / "report.json")
    monkeypatch.setattr(
        adapter,
        "fetch_current_csi300_constituents",
        lambda: pd.DataFrame({"symbol": ["000001.SZ", "600000.SH"], "name": ["平安银行", "浦发银行"]}),
    )
    existing = adapter.normalize_real_daily_frame(
        pd.DataFrame(
            {
                "trade_date": ["2024-01-02", "2024-01-02"],
                "symbol": ["000001.SZ", "600000.SH"],
                "open": [10.0, 20.0],
                "high": [10.5, 20.5],
                "low": [9.8, 19.8],
                "close": [10.2, 20.2],
                "volume": [1000, 2000],
                "amount": [10200, 40400],
                "turnover_rate": ["0.1", "0.2"],
            }
        ),
        {"000001.SZ": "平安银行", "600000.SH": "浦发银行"},
    )
    output_dir.mkdir(parents=True)
    existing.to_parquet(output_dir / "part-000.parquet", index=False)

    monkeypatch.setattr(
        adapter,
        "fetch_eastmoney_quote_snapshot",
        lambda symbols: pd.DataFrame(
            {
                "trade_date": ["2024-01-03", "2024-01-03"],
                "symbol": symbols,
                "name": ["平安银行", "浦发银行"],
                "open": [10.3, 20.3],
                "high": [10.8, 20.8],
                "low": [10.1, 20.1],
                "close": [10.6, 20.6],
                "volume": [3000, 4000],
                "amount": [31800, 82400],
                "turnover_rate": [0.5, 0.6],
            }
        ),
    )

    def fail_slow_history(*_args, **_kwargs):  # pragma: no cover - assertion helper
        raise AssertionError("slow historical provider should not be called in snapshot mode")

    monkeypatch.setattr(adapter, "fetch_symbol_daily", fail_slow_history)
    monkeypatch.setattr(adapter, "fetch_many_symbol_daily_baostock", fail_slow_history)

    report = adapter.write_real_csi300_daily(
        end_date="20240103",
        incremental=True,
        use_snapshot=True,
    )
    data = pd.read_parquet(output_dir / "part-000.parquet")

    assert report["status"] == "ok"
    assert report["data_source_mode"] == "real_csi300_daily_incremental_plus_eastmoney_snapshot"
    assert report["snapshot_row_count"] == 2
    assert report["fetched_row_count"] == 2
    assert data.groupby("trade_date")["symbol"].nunique().to_dict() == {"2024-01-02": 2, "2024-01-03": 2}
    assert data[data["trade_date"].eq("2024-01-03")]["source"].eq("eastmoney_quote_snapshot_public_web").all()
