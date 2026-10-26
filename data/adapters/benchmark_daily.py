"""Daily Shanghai/Shenzhen index closes used by abnormal-movement factors."""
from __future__ import annotations

import contextlib
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
BENCHMARK_PATH = ROOT / "data" / "real" / "benchmark_daily" / "part-000.parquet"
INDEX_CODES = {"000001.SH": "sh.000001", "399001.SZ": "sz.399001"}


def read_benchmark_daily() -> pd.DataFrame:
    if not BENCHMARK_PATH.exists():
        return pd.DataFrame(columns=["trade_date", "index_symbol", "close", "available_time"])
    return pd.read_parquet(BENCHMARK_PATH)


def fetch_benchmark_daily(start_date: str, end_date: str) -> pd.DataFrame:
    import baostock as bs

    frames = []
    # Keep CLI stdout machine-readable; BaoStock prints session messages.
    with contextlib.redirect_stdout(sys.stderr):
        login = bs.login()
        try:
            if login.error_code != "0":
                raise RuntimeError(f"Benchmark login failed: {login.error_msg}")
            for symbol, code in INDEX_CODES.items():
                query = bs.query_history_k_data_plus(
                    code, "date,code,close", start_date=start_date, end_date=end_date,
                    frequency="d", adjustflag="3",
                )
                if query.error_code != "0":
                    raise RuntimeError(f"Benchmark {symbol}: {query.error_msg}")
                rows = []
                while query.next():
                    rows.append(query.get_row_data())
                if query.error_code != "0" or not rows:
                    raise RuntimeError(f"Incomplete benchmark history for {symbol}: {query.error_msg}")
                frame = pd.DataFrame(rows, columns=query.fields).rename(columns={"date": "trade_date"})
                frame["index_symbol"] = symbol
                frames.append(frame[["trade_date", "index_symbol", "close"]])
        finally:
            bs.logout()
    return pd.concat(frames, ignore_index=True)


def update_benchmark_daily(start_date: str, end_date: str) -> dict:
    """Refresh the requested stock-history interval; retain data outside it."""
    from data.adapters.real_csi300_akshare import _atomic_write_parquet, _exclusive_file_lock

    with _exclusive_file_lock(BENCHMARK_PATH.with_suffix(".lock"), "daily benchmark update"):
        fresh = fetch_benchmark_daily(start_date, end_date).copy()
        fresh["trade_date"] = pd.to_datetime(fresh["trade_date"]).dt.strftime("%Y-%m-%d")
        fresh["close"] = pd.to_numeric(fresh["close"], errors="coerce")
        if fresh.empty or not (np.isfinite(fresh["close"]) & fresh["close"].gt(0)).all():
            raise ValueError("Benchmark history contains empty or invalid closing prices")
        if fresh.duplicated(["index_symbol", "trade_date"]).any():
            raise ValueError("Benchmark history contains duplicate dates")
        for symbol in INDEX_CODES:
            dates = fresh.loc[fresh.index_symbol.eq(symbol), "trade_date"]
            if dates.empty or dates.min() > start_date or dates.max() < end_date:
                raise ValueError(f"Benchmark {symbol} does not cover {start_date} to {end_date}")
        fresh["available_time"] = fresh["trade_date"] + "T15:30:00+08:00"
        fresh["source_version"] = "baostock_daily_index_v001"
        fresh["license_id"] = "public_web_baostock_research_only"
        existing = read_benchmark_daily()
        merged = pd.concat([existing, fresh], ignore_index=True) if not existing.empty else fresh
        merged = merged.drop_duplicates(["index_symbol", "trade_date"], keep="last")
        merged = merged.sort_values(["index_symbol", "trade_date"]).reset_index(drop=True)
        changed = not existing.equals(merged)
        if changed:
            _atomic_write_parquet(merged, BENCHMARK_PATH)
        return {"status": "ok" if changed else "no_change", "data_changed": changed,
                "rows": len(merged), "latest_trade_date": merged.trade_date.max()}
