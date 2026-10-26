"""Backfill unadjusted OHLC and daily isST without replacing adjusted history."""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import socket
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from data.adapters import real_csi300_akshare as adapter

CACHE = ROOT / "data/real/daily_price_status_cache"
REPORT = ROOT / "reports/data_repair/daily_price_status.json"


def enrich_existing_daily(existing: pd.DataFrame, raw: pd.DataFrame) -> pd.DataFrame:
    """Require matching prices/activity dates and known historical status for every row."""
    keys = ["symbol", "trade_date"]
    supplements = ["raw_open", "raw_high", "raw_low", "raw_close", "raw_price_source", "isST"]
    base = existing.drop(columns=supplements, errors="ignore")
    result = adapter._attach_raw_prices(base, raw, "baostock_unadjusted_daily")
    source = raw.copy()
    source["trade_date"] = pd.to_datetime(source.trade_date).dt.strftime("%Y-%m-%d")
    fields = keys + ["volume", "amount", "tradestatus", "isST"]
    compared = result.merge(source[fields], on=keys, how="left", suffixes=("", "_raw"), validate="one_to_one")
    for column in ("volume", "amount"):
        actual = pd.to_numeric(compared[f"{column}_raw"], errors="coerce")
        suspended = pd.to_numeric(compared.get("tradestatus_raw", compared["tradestatus"]), errors="coerce").eq(0)
        blank = compared[f"{column}_raw"].isna() | compared[f"{column}_raw"].astype(str).str.strip().eq("")
        actual = actual.mask(suspended & blank, 0)
        expected = pd.to_numeric(compared[column], errors="coerce")
        tolerance = expected.abs() * 1e-8 + (1 if column == "amount" else 0)
        mismatch = actual.isna() | (actual - expected).abs().gt(tolerance)
        if mismatch.any():
            raise ValueError(f"{column} differs between existing and raw source on {int(mismatch.sum())} rows")
    result["isST"] = compared["isST"].to_numpy()
    result = adapter.normalize_daily_supplements(result)
    if result.st_flag.isna().any():
        raise ValueError(f"Historical isST missing/invalid on {int(result.st_flag.isna().sum())} rows")
    result["data_version"] = adapter.DATA_VERSION
    result["schema_version"] = adapter.SCHEMA_VERSION
    return result


def run_backfill(publish: bool = False, max_symbols: int | None = None) -> dict:
    import baostock as bs
    from scripts.update_daily_market_data import PIPELINE_LOCK

    with adapter._exclusive_file_lock(PIPELINE_LOCK, "daily price/status repair"), adapter._exclusive_update_lock():
        path = adapter._existing_daily_parquet_path()
        fingerprint = hashlib.sha256(path.read_bytes()).hexdigest()
        existing = pd.read_parquet(path)
        symbols = sorted(existing.symbol.unique())
        if max_symbols:
            symbols = symbols[:max_symbols]
        frames, failures = [], []
        old_timeout = socket.getdefaulttimeout()
        socket.setdefaulttimeout(30)
        try:
            for offset in range(0, len(symbols), 50):
                login = bs.login()
                if login.error_code != "0":
                    raise RuntimeError(f"BaoStock login failed: {login.error_code} {login.error_msg}")
                try:
                    for index, symbol in enumerate(symbols[offset:offset + 50], start=offset + 1):
                        target = existing[existing.symbol.eq(symbol)]
                        start, end = str(target.trade_date.min()), str(target.trade_date.max())
                        cached = CACHE / f"{symbol}_{start}_{end}.parquet"
                        try:
                            if cached.exists():
                                raw = pd.read_parquet(cached)
                            else:
                                raw = adapter._call_with_retry(adapter._query_baostock_history, symbol, start, end, "3")
                            # Verify every cached/network symbol before using it; never accept a partial page.
                            enrich_existing_daily(target, raw)
                            if not cached.exists():
                                adapter._atomic_write_parquet(raw, cached)
                            frames.append(raw)
                        except Exception as exc:
                            failures.append({"symbol": symbol, "error": f"{type(exc).__name__}: {exc}"})
                        if index % 10 == 0 or index == len(symbols):
                            print(json.dumps({"completed": index, "total": len(symbols), "failed": len(failures)}), flush=True)
                finally:
                    bs.logout()
        finally:
            socket.setdefaulttimeout(old_timeout)
        report = {
            "generated_at": datetime.now(timezone.utc).isoformat(), "status": "failed" if failures else "validated",
            "source": "baostock query_history_k_data_plus adjustflag=3, daily isST",
            "source_docs": "https://baostock.com/mainContent?file=pythonAPI.md",
            "original_sha256": fingerprint, "requested_symbols": len(symbols), "failures": failures,
            "published": False,
        }
        if not failures and frames:
            selected = existing[existing.symbol.isin(symbols)]
            enriched = enrich_existing_daily(selected, pd.concat(frames, ignore_index=True))
            positive_volume = pd.to_numeric(enriched.volume).gt(0)
            vwap = enriched.amount / enriched.volume.where(positive_volume)
            outside = positive_volume & ((vwap < enriched.raw_low - .01) | (vwap > enriched.raw_high + .01))
            report.update({
                "rows": len(enriched), "raw_price_rows": int(enriched.raw_close.notna().sum()),
                "st_known_rows": int(enriched.st_flag.notna().sum()), "st_true_rows": int(enriched.st_flag.sum()),
                "start_date": str(enriched.trade_date.min()), "end_date": str(enriched.trade_date.max()),
                "vwap_outside_raw_range_rows": int(outside.sum()),
            })
            if publish and len(symbols) == existing.symbol.nunique():
                if hashlib.sha256(path.read_bytes()).hexdigest() != fingerprint:
                    raise RuntimeError("Daily data changed during repair; refusing to overwrite it")
                backup = ROOT / "reports/data_repair/backups" / f"daily-before-{fingerprint[:16]}.parquet"
                backup.parent.mkdir(parents=True, exist_ok=True)
                if not backup.exists():
                    shutil.copy2(path, backup)
                adapter._atomic_write_parquet(enriched, path)
                report.update({"published": True, "status": "ok", "backup": str(backup.relative_to(ROOT)),
                               "updated_sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
        adapter._write_json(REPORT, report)
        return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--publish", action="store_true", help="Back up and atomically publish only fully verified history")
    parser.add_argument("--max-symbols", type=int, help="Diagnostic subset; never publishes a partial universe")
    args = parser.parse_args()
    result = run_backfill(args.publish, args.max_symbols)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    raise SystemExit(1 if result["status"] == "failed" else 0)
