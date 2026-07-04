from __future__ import annotations

import argparse
import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "reports" / "daily_update" / "daily_market_data_update_report.json"

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _json_default(value: Any) -> Any:
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        value = float(value)
        return None if math.isnan(value) or math.isinf(value) else value
    if isinstance(value, (pd.Timestamp,)):
        return value.isoformat()
    if isinstance(value, Path):
        return str(value)
    return str(value)


def _latest_real_data_status() -> dict[str, Any]:
    path = ROOT / "data" / "real" / "csi300_daily" / "part-000.parquet"
    if not path.exists():
        return {"exists": False, "path": str(path.relative_to(ROOT)).replace("\\", "/")}
    daily = pd.read_parquet(path)
    latest_trade_date = None if daily.empty or "trade_date" not in daily.columns else str(daily["trade_date"].max())
    latest_stock_count = 0
    if latest_trade_date and "symbol" in daily.columns:
        latest_stock_count = int(daily[daily["trade_date"].astype(str).eq(latest_trade_date)]["symbol"].nunique())
    return {
        "exists": True,
        "path": str(path.relative_to(ROOT)).replace("\\", "/"),
        "rows": int(len(daily)),
        "symbol_count": int(daily["symbol"].nunique()) if "symbol" in daily.columns else 0,
        "latest_trade_date": latest_trade_date,
        "latest_stock_count": latest_stock_count,
    }


def run_daily_update(skip_fetch: bool = False, full_refresh: bool = False, overlap_days: int = 7, use_snapshot: bool = True) -> dict[str, Any]:
    steps: list[dict[str, Any]] = []

    if skip_fetch:
        steps.append({"step": "fetch_real_csi300_daily", "status": "skipped", "reason": "--skip-fetch"})
    else:
        from data.adapters.real_csi300_akshare import write_real_csi300_daily

        fetch_report = write_real_csi300_daily(incremental=not full_refresh, overlap_days=overlap_days, use_snapshot=use_snapshot and not full_refresh)
        steps.append({
            "step": "fetch_real_csi300_daily",
            "status": fetch_report.get("status", "ok"),
            "mode": "full_refresh" if full_refresh else "incremental",
            "requested_incremental_start_date": fetch_report.get("requested_incremental_start_date"),
            "snapshot_row_count": fetch_report.get("snapshot_row_count"),
            "fetched_row_count": fetch_report.get("fetched_row_count"),
            "real_data": _latest_real_data_status(),
        })

    from factors.offline.polars_factor_engine import materialize_factor_store
    from models.research_loop_research_loop import build_labels
    from scripts.build_latest_live_scores import build_latest_live_scores

    factor_report = materialize_factor_store(write_outputs=True)
    steps.append({
        "step": "materialize_factor_store",
        "status": factor_report.get("status", "ok"),
        "output_rows": factor_report.get("output_rows") or factor_report.get("factor_long_rows"),
    })

    _labels, label_report = build_labels(write_outputs=True)
    steps.append({
        "step": "build_labels",
        "status": label_report.get("status", "ok"),
        "row_count": label_report.get("row_count"),
        "tradable_rows": label_report.get("tradable_rows"),
    })

    live_report = build_latest_live_scores()
    steps.append({
        "step": "build_latest_live_scores",
        "status": live_report.get("status", "ok"),
        "latest_trade_date": live_report.get("latest_trade_date"),
        "stock_count": live_report.get("stock_count"),
        "rows": live_report.get("rows"),
    })

    report = {
        "status": "ok" if all(step.get("status") in {"ok", "skipped"} for step in steps) else "failed",
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "frequency": "daily_after_market_close",
        "recommended_time_cn": "交易日 16:30 后",
        "real_data": _latest_real_data_status(),
        "steps": steps,
        "research_boundary": "research_signals_only_not_investment_advice",
    }
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2, default=_json_default), encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Daily CSI300 incremental real-data refresh plus factor/label/latest-score rebuild.")
    parser.add_argument("--skip-fetch", action="store_true", help="Do not call the upstream data adapter; rebuild derived artifacts from existing parquet.")
    parser.add_argument("--full-refresh", action="store_true", help="Replace the 3-year daily parquet instead of doing the default incremental merge.")
    parser.add_argument("--no-snapshot", action="store_true", help="Disable the default Eastmoney same-day quote snapshot bridge and use slower historical providers for incremental fetch.")
    parser.add_argument("--overlap-days", type=int, default=7, help="Calendar-day overlap for default incremental fetch; refreshes partial latest dates.")
    args = parser.parse_args()
    print(json.dumps(run_daily_update(skip_fetch=args.skip_fetch, full_refresh=args.full_refresh, overlap_days=args.overlap_days, use_snapshot=not args.no_snapshot), ensure_ascii=False, indent=2, default=_json_default))


if __name__ == "__main__":
    main()
