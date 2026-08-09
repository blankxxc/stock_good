from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from data.adapters.real_csi300_akshare import (
    _atomic_write_parquet,
    _symbol_with_suffix,
    fetch_many_symbol_daily_baostock,
    fetch_symbol_daily,
    normalize_real_daily_frame,
)

UPSTREAM_DIR = ROOT / "third_party" / "COGRASP"
UPSTREAM_CODES = UPSTREAM_DIR / "data" / "code.csv"
CURRENT_DAILY = ROOT / "data" / "real" / "csi300_daily" / "part-000.parquet"
OUTPUT = ROOT / "data" / "real" / "cograsp_csi300_daily" / "part-000.parquet"
REPORT = ROOT / "reports" / "real_data" / "cograsp_daily_ingestion_report.json"
EXPECTED_STOCKS = 300
REQUIRED_LOOKBACK = 15
DEFAULT_OFFICIAL_AS_OF_DATE = "2024-06-28"


def _json_default(value: Any) -> Any:
    if isinstance(value, (pd.Timestamp, datetime, Path)):
        return str(value)
    return value


def _write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
    try:
        temporary.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, default=_json_default),
            encoding="utf-8",
        )
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _official_universe() -> pd.DataFrame:
    if not UPSTREAM_CODES.exists():
        raise FileNotFoundError(
            "COGRASP submodule is missing; run: git submodule update --init --recursive"
        )
    frame = pd.read_csv(UPSTREAM_CODES, dtype={"Code": str})
    if list(frame.columns) != ["Code", "Name"] or len(frame) != EXPECTED_STOCKS:
        raise ValueError("Unexpected COGRASP data/code.csv schema or stock count")
    frame["Code"] = frame["Code"].str.zfill(6)
    frame["symbol"] = frame["Code"].map(_symbol_with_suffix)
    return frame


def _read_optional(path: Path) -> pd.DataFrame:
    return pd.read_parquet(path) if path.exists() else pd.DataFrame()


def _latest_completed_local_date(current: pd.DataFrame) -> str:
    if current.empty or "trade_date" not in current.columns:
        return (datetime.now().date() - timedelta(days=1)).strftime("%Y-%m-%d")
    return str(pd.to_datetime(current["trade_date"]).max().date())


def _merge_frames(
    frames: list[pd.DataFrame],
    symbols: set[str],
    start_date: str,
    end_date: str,
) -> pd.DataFrame:
    usable = [frame for frame in frames if not frame.empty]
    if not usable:
        return pd.DataFrame()
    merged = pd.concat(usable, ignore_index=True, sort=False)
    merged["trade_date"] = pd.to_datetime(merged["trade_date"]).dt.strftime("%Y-%m-%d")
    merged["symbol"] = merged["symbol"].astype(str).map(_symbol_with_suffix)
    merged = merged[
        merged["symbol"].isin(symbols)
        & merged["trade_date"].ge(start_date)
        & merged["trade_date"].le(end_date)
    ]
    return (
        merged.sort_values(["symbol", "trade_date"])
        .drop_duplicates(["symbol", "trade_date"], keep="last")
        .reset_index(drop=True)
    )


def update_cograsp_market_data(
    lookback_calendar_days: int = 120,
    overlap_calendar_days: int = 7,
    as_of_date: str = DEFAULT_OFFICIAL_AS_OF_DATE,
) -> dict[str, Any]:
    if lookback_calendar_days < 45:
        raise ValueError("lookback_calendar_days must be at least 45")
    if overlap_calendar_days < 0:
        raise ValueError("overlap_calendar_days must be non-negative")

    universe = _official_universe()
    symbols = set(universe["symbol"].tolist())
    names = dict(zip(universe["symbol"], universe["Name"], strict=True))
    current = _read_optional(CURRENT_DAILY)
    existing = _read_optional(OUTPUT)
    target_end = pd.Timestamp(as_of_date).strftime("%Y-%m-%d")
    requested_start = (
        pd.Timestamp(target_end) - pd.Timedelta(days=lookback_calendar_days)
    ).strftime("%Y-%m-%d")

    local_overlap = pd.DataFrame()
    if not current.empty:
        local_overlap = current[
            current["symbol"].astype(str).isin(symbols)
            & current["trade_date"].astype(str).ge(requested_start)
        ].copy()
    seed = _merge_frames([local_overlap, existing], symbols, requested_start, target_end)

    start_by_symbol: dict[str, str] = {}
    for symbol in universe["symbol"]:
        symbol_rows = seed[seed["symbol"].eq(symbol)] if not seed.empty else pd.DataFrame()
        if symbol_rows.empty:
            start_by_symbol[symbol] = requested_start.replace("-", "")
            continue
        latest = str(symbol_rows["trade_date"].max())
        if latest >= target_end:
            continue
        refresh_start = max(
            pd.Timestamp(requested_start),
            pd.Timestamp(latest) - pd.Timedelta(days=overlap_calendar_days),
        )
        start_by_symbol[symbol] = refresh_start.strftime("%Y%m%d")

    fetched_frames: list[pd.DataFrame] = []
    failures: list[dict[str, str]] = []
    grouped_starts: dict[str, list[str]] = {}
    for symbol, start in start_by_symbol.items():
        grouped_starts.setdefault(start, []).append(symbol)
    for start, group_symbols in grouped_starts.items():
        frames, batch_failures = fetch_many_symbol_daily_baostock(
            group_symbols,
            start,
            target_end.replace("-", ""),
        )
        fetched_frames.extend(frames)
        failures.extend({**failure, "provider": "baostock_batch"} for failure in batch_failures)

    fetched_symbols = {
        _symbol_with_suffix(str(symbol))
        for frame in fetched_frames
        for symbol in frame.get("symbol", pd.Series(dtype=str)).dropna().unique()
    }
    for symbol, start in start_by_symbol.items():
        if symbol in fetched_symbols:
            continue
        try:
            frame = fetch_symbol_daily(symbol, start, target_end.replace("-", ""))
            if not frame.empty:
                fetched_frames.append(frame)
        except Exception as exc:
            failures.append(
                {
                    "symbol": symbol,
                    "provider": "symbol_fallback",
                    "error": f"{type(exc).__name__}: {exc}",
                }
            )

    normalized_fetched = pd.DataFrame()
    if fetched_frames:
        normalized_fetched = normalize_real_daily_frame(
            pd.concat(fetched_frames, ignore_index=True, sort=False),
            names,
        )
    candidate = _merge_frames(
        [local_overlap, existing, normalized_fetched],
        symbols,
        requested_start,
        target_end,
    )
    if not candidate.empty:
        candidate["stock_name"] = candidate["symbol"].map(names).fillna(candidate["stock_name"])
        candidate["eligible_universe"] = True
        candidate["data_version"] = "cograsp_official_fixed_csi300_daily_v001"

    stock_count = int(candidate["symbol"].nunique()) if not candidate.empty else 0
    date_counts = (
        candidate.groupby("trade_date")["symbol"].nunique()
        if not candidate.empty
        else pd.Series(dtype=int)
    )
    common_dates = date_counts[date_counts.eq(EXPECTED_STOCKS)].index.astype(str).tolist()
    latest_common_date = common_dates[-1] if common_dates else None
    missing_symbols = sorted(symbols - set(candidate["symbol"].unique())) if not candidate.empty else sorted(symbols)
    status = "ok" if stock_count == EXPECTED_STOCKS and len(common_dates) >= REQUIRED_LOOKBACK else "partial"
    write_performed = status == "ok"
    if write_performed:
        OUTPUT.parent.mkdir(parents=True, exist_ok=True)
        _atomic_write_parquet(candidate, OUTPUT)

    report = {
        "status": status,
        "model": "COGRASP official IJCAI-2025",
        "upstream_url": "https://github.com/NingboSong/COGRASP",
        "upstream_commit": "34e31f856ac396fa5ecea1f4410fe6c7d0bd5851",
        "universe_policy": "official fixed 300 nodes from third_party/COGRASP/data/code.csv",
        "snapshot_policy": "frozen at the IJCAI paper test-period end; no node replacement or forward-fill",
        "requested_start_date": requested_start,
        "target_end_date": target_end,
        "row_count": int(len(candidate)),
        "stock_count": stock_count,
        "common_date_count": len(common_dates),
        "latest_common_date": latest_common_date,
        "required_lookback": REQUIRED_LOOKBACK,
        "fetch_symbol_count": len(start_by_symbol),
        "fetched_row_count": int(len(normalized_fetched)),
        "missing_symbols": missing_symbols,
        "failures": failures,
        "write_performed": write_performed,
        "output_path": str(OUTPUT.relative_to(ROOT)).replace("\\", "/"),
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "research_boundary": "research_signals_only_not_investment_advice",
    }
    _write_json_atomic(REPORT, report)
    return report


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Incrementally prepare the fixed 300-stock daily input required by official COGRASP."
    )
    parser.add_argument("--lookback-calendar-days", type=int, default=120)
    parser.add_argument("--overlap-calendar-days", type=int, default=7)
    parser.add_argument(
        "--as-of-date",
        default=DEFAULT_OFFICIAL_AS_OF_DATE,
        help="Official frozen-universe inference date (default: paper test-period end).",
    )
    args = parser.parse_args()
    report = update_cograsp_market_data(
        lookback_calendar_days=args.lookback_calendar_days,
        overlap_calendar_days=args.overlap_calendar_days,
        as_of_date=args.as_of_date,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2, default=_json_default))
    raise SystemExit(0 if report["status"] == "ok" else 1)


if __name__ == "__main__":
    main()
