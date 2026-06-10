from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd


def project_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _read_parquet(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    return pd.read_parquet(path)


def _ensure_realtime_streaming_report() -> dict[str, Any]:
    root = project_root()
    report_path = root / "reports" / "realtime_streaming" / "realtime_streaming_realtime_report.json"
    if report_path.exists():
        return _read_json(report_path)
    try:
        from streaming.flink.realtime_streaming_realtime_pipeline import run_realtime_streaming_realtime_pipeline

        return run_realtime_streaming_realtime_pipeline(write_outputs=True)
    except Exception as exc:  # keep API informative if local artifacts are missing
        return {"status": "realtime_streaming_realtime_pending", "error": str(exc)}


def realtime_payload(research_boundary: str) -> dict[str, Any]:
    root = project_root()
    report = _ensure_realtime_streaming_report()
    topic_health = _read_json(root / "reports" / "realtime_streaming" / "topic_health.json")
    snapshot = _read_json(root / "reports" / "realtime_streaming" / "online_feature_snapshot.json")
    factors = _read_parquet(root / "reports" / "realtime_streaming" / "realtime_factor_latest.parquet")
    if report.get("status") != "ok" or factors.empty:
        return {
            "module": "realtime",
            "status": "realtime_streaming_realtime_pending",
            "maturity": "L1-route-stub",
            "research_boundary": research_boundary,
            "error": report.get("error"),
        }
    latest_ts = str(factors["event_time"].max())
    latest = factors.sort_values(["event_time", "symbol", "factor_name"]).tail(20)
    return {
        "module": "realtime",
        "status": "realtime_streaming_realtime_pipeline_ready",
        "maturity": "L1-local-redpanda-flink-poc-with-replay-feed",
        "research_boundary": research_boundary,
        "feed_mode": report.get("feed_mode"),
        "realtime_factor_rows": int(len(factors)),
        "latest_factor_timestamp": latest_ts,
        "topic_health": topic_health.get("topics", {}),
        "online_feature_snapshot": {
            "status": snapshot.get("status"),
            "row_count": snapshot.get("row_count"),
            "adapter": snapshot.get("adapter"),
            "feast_adapter_status": snapshot.get("feast_adapter_status"),
        },
        "sink_status": report.get("sink_status", {}),
        "diff_report": report.get("diff_report", {}),
        "signal_preview_note": "PoC / not formal signal; research monitoring only, not investment advice",
        "latest_factors": latest.to_dict(orient="records"),
        "artifacts": report.get("artifacts", {}),
    }


def flink_jobs_payload(research_boundary: str) -> dict[str, Any]:
    root = project_root()
    report = _ensure_realtime_streaming_report()
    job_status = _read_json(root / "reports" / "realtime_streaming" / "flink_job_status.json")
    jobs = job_status.get("jobs", [])
    if report.get("status") != "ok" or not jobs:
        return {
            "module": "flink-jobs",
            "status": "realtime_streaming_flink_jobs_pending",
            "maturity": "L1-route-stub",
            "research_boundary": research_boundary,
            "error": report.get("error"),
        }
    return {
        "module": "flink-jobs",
        "status": "realtime_streaming_flink_jobs_ready",
        "maturity": "L1-local-flink-semantics-poc",
        "research_boundary": research_boundary,
        "feed_mode": report.get("feed_mode"),
        "jobs": jobs,
        "job_count": len(jobs),
        "checkpoint_status": "completed_for_local_poc",
        "savepoint_status": job_status.get("savepoint_status"),
        "watermark_note": "event-time watermark and late-data fields are generated in the local PoC outputs",
        "artifacts": report.get("artifacts", {}),
    }
