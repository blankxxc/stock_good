from __future__ import annotations

import json

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
