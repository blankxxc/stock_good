from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "reports" / "daily_update" / "daily_market_data_update_report.json"
STATE = ROOT / "reports" / "daily_update" / "pipeline_state.json"
PIPELINE_LOCK = ROOT / "reports" / "daily_update" / ".daily_market_pipeline.lock"

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


def _write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
    try:
        temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=_json_default), encoding="utf-8")
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def _write_run_report(report: dict[str, Any]) -> None:
    payload = dict(report)
    generated_at = str(payload.setdefault("generated_at", datetime.now(timezone.utc).isoformat(timespec="seconds")))
    run_id = str(payload.setdefault("run_id", uuid4().hex))
    _write_json_atomic(REPORT, payload)
    safe_timestamp = generated_at.replace(":", "").replace("+", "_")
    try:
        _write_json_atomic(REPORT.parent / "history" / f"{safe_timestamp}_{run_id}.json", payload)
    except OSError:
        pass


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


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
        "fingerprint": _sha256(path),
    }


DERIVED_STEPS = [
    "materialize_factor_store",
    "build_labels",
    "train_cograsp_current",
    "build_latest_live_scores",
    "refresh_sentiment_event_data",
    "train_sentiment_event_fusion",
    "build_sentiment_event_scores",
    "train_finmamba_official",
]


def run_daily_update(
    skip_fetch: bool = False,
    full_refresh: bool = False,
    overlap_days: int = 7,
    use_snapshot: bool = False,
    force_rebuild: bool = False,
    fetch_news: bool = False,
) -> dict[str, Any]:
    from data.adapters.real_csi300_akshare import _exclusive_file_lock

    with _exclusive_file_lock(PIPELINE_LOCK, "daily market pipeline"):
        steps: list[dict[str, Any]] = []
        fetch_report: dict[str, Any] = {"status": "skipped", "data_changed": False}
        state = _read_json(STATE)
        if not isinstance(state.get("steps"), dict):
            state["steps"] = {}
        state_steps = state["steps"]

        if skip_fetch:
            steps.append({"step": "fetch_real_csi300_daily", "status": "skipped", "reason": "--skip-fetch"})
        else:
            from data.adapters.real_csi300_akshare import write_real_csi300_daily

            fetch_report = write_real_csi300_daily(
                incremental=not full_refresh,
                overlap_days=overlap_days,
                use_snapshot=use_snapshot and not full_refresh,
            )
            steps.append({
                "step": "fetch_real_csi300_daily",
                "status": fetch_report.get("status", "failed"),
                "mode": "full_refresh" if full_refresh else "incremental",
                "requested_incremental_start_date": fetch_report.get("requested_incremental_start_date"),
                "expected_latest_trade_date": fetch_report.get("expected_latest_trade_date"),
                "snapshot_row_count": fetch_report.get("snapshot_row_count"),
                "fetched_row_count": fetch_report.get("fetched_row_count"),
                "new_row_count": fetch_report.get("new_row_count"),
                "revised_row_count": fetch_report.get("revised_row_count"),
                "deleted_row_count": fetch_report.get("deleted_row_count"),
                "data_changed": fetch_report.get("data_changed", False),
                "write_performed": fetch_report.get("write_performed", False),
                "real_data": _latest_real_data_status(),
            })

        fetch_status = str(fetch_report.get("status", "failed"))
        upstream_blocked = fetch_status in {"failed", "partial", "stale"}
        raw_status = _latest_real_data_status()
        raw_fingerprint = raw_status.get("fingerprint")
        if not raw_status.get("exists") or not raw_fingerprint:
            upstream_blocked = True

        step_runners: dict[str, Any] = {}
        if not upstream_blocked:
            from factors.offline.polars_factor_engine import materialize_factor_store
            from models.cograsp_current import CURRENT_DAILY, train_current_cograsp
            from models.sentiment_event_fusion import (
                build_sentiment_event_scores,
                train_sentiment_event_fusion,
            )
            from models.research_loop_research_loop import build_labels
            from scripts.build_latest_live_scores import build_latest_live_scores
            from scripts.train_finmamba_official import train_official_finmamba
            from data.adapters.sentiment_event_data import update_sentiment_event_data

            step_runners = {
                "materialize_factor_store": lambda: materialize_factor_store(write_outputs=True),
                "build_labels": lambda: build_labels(write_outputs=True)[1],
                "train_cograsp_current": lambda: train_current_cograsp(
                    pd.read_parquet(CURRENT_DAILY)
                ),
                "build_latest_live_scores": build_latest_live_scores,
                "refresh_sentiment_event_data": lambda: update_sentiment_event_data(
                    fetch_news=fetch_news
                ),
                "train_sentiment_event_fusion": lambda: train_sentiment_event_fusion(
                    pd.read_parquet(CURRENT_DAILY)
                ),
                "build_sentiment_event_scores": build_sentiment_event_scores,
                "train_finmamba_official": lambda: train_official_finmamba(
                    device="auto", epochs=5
                ),
            }

        dependency_failed = upstream_blocked
        ran_derived_step = False
        sentiment_data_refreshed = False
        for step_name in DERIVED_STEPS:
            checkpoint = state_steps.get(step_name, {}) if isinstance(state_steps, dict) else {}
            checkpoint_current = bool(
                checkpoint.get("status") in {"ok", "blocked_runtime"}
                and checkpoint.get("input_fingerprint") == raw_fingerprint
            )
            needs_run = bool(
                skip_fetch
                or full_refresh
                or force_rebuild
                or not checkpoint_current
                or (step_name == "refresh_sentiment_event_data" and fetch_news)
                or (
                    sentiment_data_refreshed
                    and step_name in {"train_sentiment_event_fusion", "build_sentiment_event_scores"}
                )
            )
            if dependency_failed:
                steps.append({"step": step_name, "status": "skipped", "reason": "upstream or dependency step was not complete"})
                continue
            if not needs_run:
                steps.append({"step": step_name, "status": "skipped", "reason": "checkpoint already matches market-data fingerprint"})
                continue

            ran_derived_step = True
            started_at = datetime.now(timezone.utc)
            try:
                step_report = step_runners[step_name]()
                step_status = str(step_report.get("status", "ok"))
                step_entry = {
                    "step": step_name,
                    "status": step_status,
                    "input_fingerprint": raw_fingerprint,
                    "duration_seconds": round((datetime.now(timezone.utc) - started_at).total_seconds(), 3),
                }
                for field in (
                    "output_rows", "factor_long_rows", "row_count", "tradable_rows",
                    "latest_trade_date", "latest_market_date", "stock_count", "rows",
                    "market_sentiment_rows", "stored_event_rows", "news_symbol_coverage",
                    "training_sample_count", "prediction_rows",
                ):
                    if field in step_report:
                        step_entry[field] = step_report[field]
                steps.append(step_entry)
                state_steps[step_name] = {
                    "status": step_status,
                    "input_fingerprint": raw_fingerprint,
                    "completed_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                }
                if step_status not in {"ok", "blocked_runtime"}:
                    dependency_failed = True
                elif step_name == "refresh_sentiment_event_data":
                    sentiment_data_refreshed = True
            except Exception as exc:
                dependency_failed = True
                steps.append({
                    "step": step_name,
                    "status": "failed",
                    "error": f"{type(exc).__name__}: {exc}",
                    "input_fingerprint": raw_fingerprint,
                    "duration_seconds": round((datetime.now(timezone.utc) - started_at).total_seconds(), 3),
                })
                state_steps[step_name] = {
                    "status": "failed",
                    "input_fingerprint": raw_fingerprint,
                    "error": f"{type(exc).__name__}: {exc}",
                    "completed_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                }
            state["raw_data"] = raw_status
            state["updated_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
            _write_json_atomic(STATE, state)

        step_statuses = {str(step.get("status")) for step in steps}
        if "failed" in step_statuses:
            overall_status = "failed"
        elif fetch_status in {"partial", "stale"} or "partial" in step_statuses:
            overall_status = "partial"
        elif dependency_failed:
            overall_status = "failed"
        elif fetch_status == "no_change" and not ran_derived_step:
            overall_status = "no_change"
        else:
            overall_status = "ok"

        if overall_status in {"ok", "no_change"} and raw_fingerprint:
            state["status"] = "ok"
            state["published_raw_fingerprint"] = raw_fingerprint
            state["published_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
        else:
            state["status"] = overall_status
        state["raw_data"] = raw_status
        state["updated_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
        _write_json_atomic(STATE, state)

        report = {
            "status": overall_status,
            "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "frequency": "daily_after_market_close",
            "recommended_time_cn": "交易日 16:30 后",
            "real_data": raw_status,
            "raw_fingerprint": raw_fingerprint,
            "published_raw_fingerprint": state.get("published_raw_fingerprint"),
            "data_changed": bool(fetch_report.get("data_changed", False)),
            "resumed_from_checkpoint": bool(ran_derived_step and not fetch_report.get("data_changed", False)),
            "steps": steps,
            "research_boundary": "research_signals_only_not_investment_advice",
        }
        _write_run_report(report)
        return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Daily CSI300 incremental real-data refresh plus factor/label/latest-score rebuild.")
    parser.add_argument("--skip-fetch", action="store_true", help="Do not call the upstream data adapter; rebuild derived artifacts from existing parquet.")
    parser.add_argument("--full-refresh", action="store_true", help="Replace the 3-year daily parquet instead of doing the default incremental merge.")
    snapshot = parser.add_mutually_exclusive_group()
    snapshot.add_argument("--use-snapshot", action="store_true", help="Explicitly allow the same-day quote bridge; adjusted historical daily bars are the default.")
    snapshot.add_argument("--no-snapshot", action="store_false", dest="use_snapshot", help=argparse.SUPPRESS)
    parser.set_defaults(use_snapshot=False)
    parser.add_argument("--force-rebuild", action="store_true", help="Rebuild factors, labels, and latest scores even when daily data is unchanged.")
    parser.add_argument(
        "--fetch-news",
        action="store_true",
        help="Incrementally fetch recent real stock news before training the optional sentiment-event model.",
    )
    parser.add_argument("--overlap-days", type=int, default=7, help="Calendar-day overlap for default incremental fetch; refreshes partial latest dates.")
    args = parser.parse_args()
    try:
        report = run_daily_update(
            skip_fetch=args.skip_fetch,
            full_refresh=args.full_refresh,
            overlap_days=args.overlap_days,
            use_snapshot=args.use_snapshot,
            force_rebuild=args.force_rebuild,
            fetch_news=args.fetch_news,
        )
    except Exception as exc:
        report = {
            "status": "failed",
            "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "error": f"{type(exc).__name__}: {exc}",
            "steps": [],
            "research_boundary": "research_signals_only_not_investment_advice",
        }
        _write_run_report(report)
    print(json.dumps(report, ensure_ascii=False, indent=2, default=_json_default))
    raise SystemExit(0 if report.get("status") in {"ok", "no_change"} else 1)


if __name__ == "__main__":
    main()
