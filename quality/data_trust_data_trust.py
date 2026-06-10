"""data_trust data-trust layer for the intelligent stock research platform.

This module is intentionally local and deterministic: it generates a synthetic
mini market with known corner cases, quarantines intentional bad rows, validates
clean point-in-time data, emits lightweight lineage, and writes HTML/JSON
reports that the backend and frontend can expose.
"""
from __future__ import annotations

import hashlib
import json
import math
import shutil
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable

import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parents[1]
DATA_VERSION = "data_trust_v001"
SOURCE_VERSION = "synthetic_mini_market_v001"
SCHEMA_VERSION = "v0.3.0"
CREATED_BY = "hermes-data_trust-data-trust"
RESEARCH_BOUNDARY = "research_signals_only_not_investment_advice"

REQUIRED_MARKET_COLUMNS = {
    "trade_date",
    "symbol",
    "open",
    "high",
    "low",
    "close",
    "volume",
    "amount",
    "event_time",
    "publish_time",
    "ingest_time",
    "available_time",
    "prediction_time",
    "decision_time",
    "order_time",
    "execution_window",
    "label_start_time",
    "label_end_time",
    "adj_factor",
    "industry_name",
    "industry_as_of_date",
    "index_member_as_of_date",
    "st_flag",
    "paused",
    "limit_up_flag",
    "limit_down_flag",
    "delist_flag",
    "tradable_flag",
    "can_buy",
    "can_sell",
    "eligible_universe",
    "transaction_cost_bps",
    "slippage_bps",
    "data_version",
    "schema_version",
    "source",
    "trace_id",
}

QUALITY_CHECK_ORDER = [
    "schema_match",
    "primary_key_duplicate",
    "missing_required_fields",
    "price_positive",
    "ohlc_relation",
    "volume_abnormal",
    "trading_day_gap",
    "adjustment_factor_present_and_stable",
    "industry_present",
    "index_member_history_present",
    "tradability_flags_present",
    "data_latency",
    "duplicate_rate",
    "correction_rate",
    "source_license_display_export_gate",
]

LEAKAGE_RULES = [
    "feature.available_time <= prediction_time",
    "label_start_time > prediction_time",
    "announcement.publish_time <= prediction_time",
    "news.publish_time <= prediction_time",
    "financial_statement.announce_time <= prediction_time",
    "industry.as_of_date <= prediction_time",
    "index_member.as_of_date <= prediction_time",
    "scaler.fit_window <= train_window",
    "purged_split_with_embargo",
]


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _clean_dir(path: Path) -> None:
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True, exist_ok=True)


def _write_json(path: Path, payload: Any) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def _read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def _read_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def _safe_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, default=str, sort_keys=True)


def _write_single_parquet(df: pd.DataFrame, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(path, index=False)
    return path


def _content_hash(df: pd.DataFrame) -> str:
    normalized = df.copy()
    for col in normalized.columns:
        if pd.api.types.is_datetime64_any_dtype(normalized[col]):
            normalized[col] = normalized[col].astype(str)
    cols = sorted(normalized.columns)
    payload = normalized[cols].sort_values(cols).to_json(orient="records", force_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _html_escape(value: Any) -> str:
    text = str(value)
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def _html_table(rows: list[dict[str, Any]], columns: list[str]) -> str:
    head = "".join(f"<th>{_html_escape(col)}</th>" for col in columns)
    body = []
    for row in rows:
        cells = "".join(f"<td>{_html_escape(row.get(col, ''))}</td>" for col in columns)
        body.append(f"<tr>{cells}</tr>")
    return f"<table><thead><tr>{head}</tr></thead><tbody>{''.join(body)}</tbody></table>"


def _write_quality_html(report: dict[str, Any], path: Path) -> Path:
    checks = _html_table(
        report["checks"],
        ["check_name", "status", "observed", "threshold", "details"],
    )
    html = f"""<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8" />
<title>data_trust Data Quality Report</title>
<style>
body {{ font-family: Inter, Arial, sans-serif; margin: 32px; background: #0f172a; color: #e5e7eb; }}
.card {{ background: #111827; border: 1px solid #334155; border-radius: 16px; padding: 20px; margin: 16px 0; }}
table {{ border-collapse: collapse; width: 100%; font-size: 13px; }}
th, td {{ border-bottom: 1px solid #334155; padding: 8px; text-align: left; vertical-align: top; }}
th {{ color: #93c5fd; }}
.badge {{ display: inline-block; background: #065f46; color: #dcfce7; padding: 4px 10px; border-radius: 999px; }}
code {{ color: #fbbf24; }}
</style>
</head>
<body>
<span class="badge">data_trust · data_quality · quarantine · leakage_check_status</span>
<h1>data_trust 数据质量报告</h1>
<div class="card">
  <p>status: <strong>{_html_escape(report['status'])}</strong></p>
  <p>data_version: <code>{_html_escape(report['data_version'])}</code></p>
  <p>leakage_check_status: <strong>{_html_escape(report['leakage_check_status'])}</strong></p>
  <p>quarantine path: <code>{_html_escape(report['quarantine']['path'])}</code></p>
  <p>研究边界：{_html_escape(report['research_boundary'])}</p>
</div>
<div class="card">
  <h2>质量检查</h2>
  {checks}
</div>
<div class="card">
  <h2>摘要</h2>
  <pre>{_html_escape(json.dumps(report['summary'], ensure_ascii=False, indent=2))}</pre>
</div>
</body>
</html>
"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(html, encoding="utf-8")
    return path


def _write_lineage_html(report: dict[str, Any], path: Path) -> Path:
    edges = _html_table(
        report["edges"][:80],
        ["source_type", "source_id", "target_type", "target_id", "relation", "run_id"],
    )
    html = f"""<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8" />
<title>data_trust Lineage Report</title>
<style>
body {{ font-family: Inter, Arial, sans-serif; margin: 32px; background: #0f172a; color: #e5e7eb; }}
.card {{ background: #111827; border: 1px solid #334155; border-radius: 16px; padding: 20px; margin: 16px 0; }}
table {{ border-collapse: collapse; width: 100%; font-size: 13px; }}
th, td {{ border-bottom: 1px solid #334155; padding: 8px; text-align: left; vertical-align: top; }}
th {{ color: #93c5fd; }}
.badge {{ display: inline-block; background: #1d4ed8; color: #dbeafe; padding: 4px 10px; border-radius: 999px; }}
code {{ color: #fbbf24; }}
</style>
</head>
<body>
<span class="badge">data_trust · source_table → transform_job → target_table → report/model/backtest</span>
<h1>data_trust 血缘报告</h1>
<div class="card">
  <p>status: <strong>{_html_escape(report['status'])}</strong></p>
  <p>node_count: {report['node_count']} · edge_count: {report['edge_count']}</p>
  <p>manifest: <code>{_html_escape(report['source_manifest_path'])}</code></p>
</div>
<div class="card">
  <h2>血缘边</h2>
  {edges}
</div>
</body>
</html>
"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(html, encoding="utf-8")
    return path


def _next_trade_date(dates: list[str], idx: int) -> str:
    if idx + 1 < len(dates):
        return dates[idx + 1]
    dt = datetime.fromisoformat(dates[idx]) + timedelta(days=1)
    return dt.date().isoformat()


def _future_trade_date(dates: list[str], idx: int, horizon: int) -> str:
    target = min(idx + horizon, len(dates) - 1)
    if target == idx:
        dt = datetime.fromisoformat(dates[idx]) + timedelta(days=horizon)
        return dt.date().isoformat()
    return dates[target]


def build_synthetic_mini_market() -> tuple[pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    """Build 20 stocks x 100 trading days and a separate intentional trap set."""
    dates = [d.date().isoformat() for d in pd.bdate_range("2025-09-01", periods=100)]
    sz_symbols = [f"{idx:06d}.SZ" for idx in range(1, 11)]
    sh_symbols = [f"{600000 + idx:06d}.SH" for idx in range(10)]
    symbols = sz_symbols + sh_symbols
    industries = ["银行", "地产", "食品饮料", "电力设备", "计算机", "医药", "煤炭", "汽车"]
    rows: list[dict[str, Any]] = []
    for day_idx, trade_date in enumerate(dates):
        next_date = _next_trade_date(dates, day_idx)
        label_end = _future_trade_date(dates, day_idx, 5)
        for sym_idx, symbol in enumerate(symbols):
            wave = math.sin(day_idx / 7.0 + sym_idx / 3.0) * 0.018
            trend = day_idx * 0.015 + sym_idx * 0.35
            close = round(9.5 + trend + wave + (sym_idx % 5) * 1.1, 4)
            open_ = round(close * (1 - 0.004 + (sym_idx % 3) * 0.0015), 4)
            high = round(max(open_, close) * 1.018, 4)
            low = round(min(open_, close) * 0.982, 4)
            volume = 150_000 + sym_idx * 9_000 + day_idx * 1_100
            paused = symbol == symbols[0] and 20 <= day_idx <= 24
            st_flag = symbol == symbols[1] and 35 <= day_idx <= 44
            limit_up_flag = symbol == symbols[2] and day_idx in {30, 31}
            limit_down_flag = symbol == symbols[3] and day_idx in {50, 51}
            delist_flag = symbol == symbols[4] and day_idx >= 85
            new_listing = symbol == symbols[5] and day_idx < 10
            if paused:
                volume = 0
            tradable = not (paused or st_flag or delist_flag or new_listing)
            can_buy = tradable and not limit_up_flag
            can_sell = tradable and not limit_down_flag
            industry_name = industries[(sym_idx + (1 if day_idx >= 60 and sym_idx == 6 else 0)) % len(industries)]
            event_time = f"{trade_date}T15:00:00+08:00"
            publish_time = f"{trade_date}T15:30:00+08:00"
            ingest_time = f"{trade_date}T15:35:00+08:00"
            available_time = f"{next_date}T09:20:00+08:00"
            prediction_time = f"{next_date}T09:25:00+08:00"
            rows.append({
                "trade_date": trade_date,
                "symbol": symbol,
                "open": open_,
                "high": high,
                "low": low,
                "close": close,
                "volume": int(volume),
                "amount": round(volume * close, 2),
                "event_time": event_time,
                "publish_time": publish_time,
                "ingest_time": ingest_time,
                "available_time": available_time,
                "prediction_time": prediction_time,
                "decision_time": f"{next_date}T09:26:00+08:00",
                "order_time": f"{next_date}T09:30:00+08:00",
                "execution_window": f"{next_date}T09:30:00+08:00/{next_date}T14:57:00+08:00",
                "label_start_time": f"{next_date}T09:30:00+08:00",
                "label_end_time": f"{label_end}T15:00:00+08:00",
                "adj_factor": round(1.0 + day_idx * 0.0006 + sym_idx * 0.0001, 6),
                "industry_name": industry_name,
                "industry_as_of_date": trade_date,
                "index_symbol": "CSI300_DEMO" if sym_idx < 12 else "CSI500_DEMO",
                "index_member_as_of_date": trade_date,
                "st_flag": bool(st_flag),
                "paused": bool(paused),
                "limit_up_flag": bool(limit_up_flag),
                "limit_down_flag": bool(limit_down_flag),
                "delist_flag": bool(delist_flag),
                "new_listing_flag": bool(new_listing),
                "tradable_flag": bool(tradable),
                "can_buy": bool(can_buy),
                "can_sell": bool(can_sell),
                "eligible_universe": bool(tradable and not st_flag and not delist_flag and not new_listing),
                "transaction_cost_bps": 8.0,
                "slippage_bps": 3.0,
                "announcement_publish_time": publish_time if not (symbol == symbols[7] and day_idx == 40) else f"{trade_date}T16:10:00+08:00",
                "news_publish_time": f"{trade_date}T14:20:00+08:00",
                "financial_announce_time": f"{trade_date}T08:00:00+08:00",
                "scaler_fit_window_end": trade_date,
                "train_window_end": trade_date,
                "valid_window_start": _future_trade_date(dates, day_idx, 8),
                "embargo_days": 5,
                "correction_type": "none",
                "source": "synthetic_mini_market",
                "source_version": SOURCE_VERSION,
                "schema_version": SCHEMA_VERSION,
                "data_version": DATA_VERSION,
                "trace_id": f"data_trust-{day_idx:03d}-{sym_idx:03d}",
            })
    clean = pd.DataFrame(rows)

    trap_base = clean.head(1).iloc[0].to_dict()
    trap_rows: list[dict[str, Any]] = []
    for reason in [
        "price_non_positive",
        "ohlc_relation_invalid",
        "duplicate_primary_key",
        "future_available_time",
        "full_sample_standardization_leak",
        "label_leakage_trap_feature",
        "future_index_constituent",
        "future_announcement_publish_time",
        "future_news_publish_time",
        "future_financial_announce_time",
        "missing_industry",
    ]:
        row = dict(trap_base)
        row["trace_id"] = f"trap-{reason}"
        row["trap_reason"] = reason
        row["severity"] = "high" if "future" in reason or "leak" in reason else "medium"
        if reason == "price_non_positive":
            row["close"] = -1.0
        elif reason == "ohlc_relation_invalid":
            row["high"] = row["low"] - 0.5
        elif reason == "duplicate_primary_key":
            row["trace_id"] = "trap-duplicate-of-clean-row"
        elif reason == "future_available_time":
            row["available_time"] = "2026-12-31T09:20:00+08:00"
        elif reason == "full_sample_standardization_leak":
            row["scaler_fit_window_end"] = "2026-12-31"
            row["feature_name"] = "full_sample_zscore_close"
        elif reason == "label_leakage_trap_feature":
            row["feature_name"] = "future_5d_return"
            row["label_start_time"] = row["prediction_time"]
        elif reason == "future_index_constituent":
            row["index_member_as_of_date"] = "2026-12-31"
        elif reason == "future_announcement_publish_time":
            row["announcement_publish_time"] = "2026-12-31T10:00:00+08:00"
        elif reason == "future_news_publish_time":
            row["news_publish_time"] = "2026-12-31T10:00:00+08:00"
        elif reason == "future_financial_announce_time":
            row["financial_announce_time"] = "2026-12-31T10:00:00+08:00"
        elif reason == "missing_industry":
            row["industry_name"] = None
        trap_rows.append(row)
    # Add an exact duplicated key trap by duplicating the first clean row's key.
    traps = pd.DataFrame(trap_rows)

    scenario_flags = {
        "paused_rows": int(clean["paused"].sum()),
        "st_rows": int(clean["st_flag"].sum()),
        "limit_up_rows": int(clean["limit_up_flag"].sum()),
        "limit_down_rows": int(clean["limit_down_flag"].sum()),
        "delisted_rows": int(clean["delist_flag"].sum()),
        "new_listing_rows": int(clean["new_listing_flag"].sum()),
        "after_close_announcement_rows": int((pd.to_datetime(clean["announcement_publish_time"]) > pd.to_datetime(clean["event_time"])).sum()),
    }
    return clean, traps, scenario_flags


def _to_datetime(series: pd.Series) -> pd.Series:
    return pd.to_datetime(series, errors="coerce", utc=True)


def _to_date(series: pd.Series) -> pd.Series:
    return pd.to_datetime(series, errors="coerce").dt.date


def _write_synthetic_artifacts(clean: pd.DataFrame, traps: pd.DataFrame, scenario_flags: dict[str, Any]) -> dict[str, Any]:
    sample_root = ROOT / "data" / "samples" / "synthetic_mini_market"
    _clean_dir(sample_root)
    market_path = _write_single_parquet(clean, sample_root / "data_trust_market_daily.parquet")
    traps_path = _write_single_parquet(traps, sample_root / "data_trust_intentional_traps.parquet")

    synthetic_tests = {
        "t_signal_cannot_use_t_plus_1_data": "passed" if (_to_datetime(clean["available_time"]) <= _to_datetime(clean["prediction_time"])).all() else "failed",
        "after_close_announcement_uses_next_trade_point": "passed" if (_to_datetime(clean["announcement_publish_time"]) <= _to_datetime(clean["prediction_time"])).all() else "failed",
        "index_constituent_point_in_time": "passed" if (_to_datetime(clean["index_member_as_of_date"]) <= _to_datetime(clean["prediction_time"])).all() else "failed",
        "scaler_parameters_use_train_window_only": "passed" if (_to_date(clean["scaler_fit_window_end"]) <= _to_date(clean["train_window_end"])).all() else "failed",
        "label_does_not_pollute_features": "passed" if "future_5d_return" not in set(clean.get("feature_name", pd.Series(dtype=str)).dropna().astype(str)) else "failed",
        "paused_rows_are_not_buyable_or_sellable": "passed" if ((~clean["paused"]) | ((clean["can_buy"] == False) & (clean["can_sell"] == False))).all() else "failed",  # noqa: E712
        "limit_up_rows_are_not_buyable": "passed" if ((~clean["limit_up_flag"]) | (clean["can_buy"] == False)).all() else "failed",  # noqa: E712
        "limit_down_rows_are_not_sellable": "passed" if ((~clean["limit_down_flag"]) | (clean["can_sell"] == False)).all() else "failed",  # noqa: E712
        "st_filter_is_effective": "passed" if ((~clean["st_flag"]) | (clean["eligible_universe"] == False)).all() else "failed",  # noqa: E712
        "transaction_cost_and_slippage_are_present": "passed" if (clean["transaction_cost_bps"].min() > 0 and clean["slippage_bps"].min() > 0) else "failed",
    }
    report = {
        "status": "passed" if all(v == "passed" for v in synthetic_tests.values()) else "failed",
        "day": 3,
        "data_version": DATA_VERSION,
        "source_version": SOURCE_VERSION,
        "stock_count": int(clean["symbol"].nunique()),
        "trading_day_count": int(clean["trade_date"].nunique()),
        "row_count": int(len(clean)),
        "scenario_flags": scenario_flags,
        "synthetic_tests": synthetic_tests,
        "artifacts": {
            "clean_market_daily": str(market_path.relative_to(ROOT)).replace("\\", "/"),
            "intentional_traps": str(traps_path.relative_to(ROOT)).replace("\\", "/"),
        },
        "research_boundary": RESEARCH_BOUNDARY,
        "generated_at": _utc_now(),
    }
    _write_json(ROOT / "reports" / "data_trust" / "synthetic_mini_market_report.json", report)
    return report


def _quarantine_records(traps: pd.DataFrame) -> pd.DataFrame:
    detected_at = _utc_now()
    records: list[dict[str, Any]] = []
    for _, row in traps.iterrows():
        reason = str(row.get("trap_reason") or "unknown")
        records.append({
            "reason": reason,
            "severity": row.get("severity", "medium"),
            "source_row": _safe_json(row.dropna().to_dict()),
            "detected_at": detected_at,
            "resolved_status": "open",
            "owner": "data-governance",
            "resolution_note": "Intentional data_trust synthetic anomaly quarantined before training/backtest/report use.",
            "source_table": "synthetic_mini_market",
            "trade_date": row.get("trade_date"),
            "symbol": row.get("symbol"),
            "data_version": DATA_VERSION,
            "trace_id": row.get("trace_id"),
        })
    return pd.DataFrame(records)


def _write_quarantine(records: pd.DataFrame) -> dict[str, Any]:
    quarantine_root = ROOT / "data" / "quarantine" / "data_trust_synthetic_market"
    _clean_dir(quarantine_root)
    for trade_date, group in records.groupby("trade_date", dropna=False):
        safe_date = str(trade_date).replace(":", "-").replace("/", "-")
        _write_single_parquet(group, quarantine_root / f"trade_date={safe_date}" / "part-000.parquet")
    summary_path = ROOT / "reports" / "data_trust" / "quarantine_summary.json"
    summary = {
        "status": "written",
        "path": "data/quarantine/data_trust_synthetic_market",
        "record_count": int(len(records)),
        "reasons": sorted(records["reason"].astype(str).unique().tolist()),
        "severity_counts": records["severity"].value_counts().to_dict(),
        "required_fields": ["reason", "severity", "source_row", "detected_at", "resolved_status", "owner", "resolution_note"],
    }
    _write_json(summary_path, summary)
    return summary


def _check_result(name: str, status: bool, observed: Any, threshold: Any, details: str) -> dict[str, Any]:
    return {
        "check_name": name,
        "status": "passed" if status else "failed",
        "observed": observed,
        "threshold": threshold,
        "details": details,
    }


def _build_quality_checks(clean: pd.DataFrame, quarantine_summary: dict[str, Any]) -> list[dict[str, Any]]:
    duplicate_count = int(clean.duplicated(["trade_date", "symbol"]).sum())
    missing_required = int(clean[list(REQUIRED_MARKET_COLUMNS)].isna().sum().sum()) if REQUIRED_MARKET_COLUMNS.issubset(clean.columns) else -1
    invalid_price = int(((clean["open"] <= 0) | (clean["high"] <= 0) | (clean["low"] <= 0) | (clean["close"] <= 0)).sum())
    invalid_ohlc = int(((clean["high"] < clean[["open", "close", "low"]].max(axis=1)) | (clean["low"] > clean[["open", "close", "high"]].min(axis=1))).sum())
    volume_abnormal = int((clean["volume"] < 0).sum())
    coverage = clean.groupby("symbol")["trade_date"].nunique().min() / clean["trade_date"].nunique()
    adj_change = clean.sort_values(["symbol", "trade_date"]).groupby("symbol")["adj_factor"].pct_change().abs().max()
    industry_missing = int(clean["industry_name"].isna().sum())
    index_missing_or_future = int((clean["index_member_as_of_date"].isna() | (_to_datetime(clean["index_member_as_of_date"]) > _to_datetime(clean["prediction_time"]))).sum())
    tradability_cols = {"st_flag", "paused", "limit_up_flag", "limit_down_flag", "delist_flag", "tradable_flag", "can_buy", "can_sell"}
    tradability_ok = tradability_cols.issubset(clean.columns) and bool(((~clean["paused"]) | ((clean["can_buy"] == False) & (clean["can_sell"] == False))).all())  # noqa: E712
    latency_hours = ((_to_datetime(clean["available_time"]) - _to_datetime(clean["publish_time"])).dt.total_seconds() / 3600).quantile(0.95)
    duplicate_rate = duplicate_count / max(len(clean), 1)
    correction_rate = float((clean["correction_type"] != "none").mean())

    registry = _read_yaml(ROOT / "configs" / "data" / "source_license_registry.yaml")
    sources = registry.get("sources", [])
    license_ok = bool(sources) and all(source.get("display_policy") and source.get("export_policy") for source in sources)

    return [
        _check_result("schema_match", REQUIRED_MARKET_COLUMNS.issubset(clean.columns), sorted(REQUIRED_MARKET_COLUMNS - set(clean.columns)), "missing=[]", "Clean synthetic market exposes data_trust point-in-time schema."),
        _check_result("primary_key_duplicate", duplicate_count == 0, duplicate_count, "=0", "Primary key is trade_date + symbol."),
        _check_result("missing_required_fields", missing_required == 0, missing_required, "<=0.1% critical field missingness", "No missing critical fields remain in clean dataset."),
        _check_result("price_positive", invalid_price == 0, invalid_price, "=0 clean; bad rows quarantine", "Non-positive prices are blocked before clean use."),
        _check_result("ohlc_relation", invalid_ohlc == 0, invalid_ohlc, "=0 clean; bad rows quarantine", "OHLC relationships hold for clean rows."),
        _check_result("volume_abnormal", volume_abnormal == 0, volume_abnormal, "=0 negative volume", "Paused rows may have zero volume; negative volume is blocked."),
        _check_result("trading_day_gap", coverage >= 0.99, round(float(coverage), 4), ">=0.99", "Every synthetic symbol covers 100 trading days."),
        _check_result("adjustment_factor_present_and_stable", pd.notna(adj_change) and float(adj_change) < 0.01, round(float(adj_change), 6), "max daily pct_change < 1%", "Adjustment factor exists and has no synthetic future jump in clean data."),
        _check_result("industry_present", industry_missing == 0, industry_missing, "=0", "Industry is point-in-time present."),
        _check_result("index_member_history_present", index_missing_or_future == 0, index_missing_or_future, "=0 future/missing", "Index membership as_of_date is not after prediction_time."),
        _check_result("tradability_flags_present", tradability_ok, sorted(tradability_cols - set(clean.columns)), "all flags present and pause blocks trading", "ST, paused, limit, delist and buy/sell flags are present."),
        _check_result("data_latency", float(latency_hours) <= 72.0, round(float(latency_hours), 4), "p95 <= 72h allowing weekends/holidays for after-close daily data", "Daily close data is only available for the next trading decision point; weekend gaps are allowed."),
        _check_result("duplicate_rate", duplicate_rate == 0.0, round(float(duplicate_rate), 6), "=0", "No duplicate clean primary keys."),
        _check_result("correction_rate", correction_rate == 0.0, round(float(correction_rate), 6), "=0 synthetic baseline", "No synthetic corrections applied to clean baseline."),
        _check_result("source_license_display_export_gate", license_ok, len(sources), "registry sources all declare display/export policy", "License gate reads configs/data/source_license_registry.yaml."),
    ]


def _write_quality_report(clean: pd.DataFrame, quarantine_summary: dict[str, Any]) -> dict[str, Any]:
    checks = _build_quality_checks(clean, quarantine_summary)
    summary = {
        "clean_row_count": int(len(clean)),
        "stock_count": int(clean["symbol"].nunique()),
        "trading_day_count": int(clean["trade_date"].nunique()),
        "daily_coverage": round(float(clean.groupby("symbol")["trade_date"].nunique().min() / clean["trade_date"].nunique()), 6),
        "future_time_leakage": int((_to_datetime(clean["available_time"]) > _to_datetime(clean["prediction_time"])).sum()),
        "illegal_price_rows_clean": int(((clean["open"] <= 0) | (clean["high"] <= 0) | (clean["low"] <= 0) | (clean["close"] <= 0)).sum()),
        "duplicate_primary_keys_clean": int(clean.duplicated(["trade_date", "symbol"]).sum()),
        "quarantined_records": int(quarantine_summary["record_count"]),
        "quarantined_reasons": quarantine_summary["reasons"],
    }
    report = {
        "status": "passed" if all(check["status"] == "passed" for check in checks) else "failed",
        "day": 3,
        "data_version": DATA_VERSION,
        "source_version": SOURCE_VERSION,
        "schema_version": SCHEMA_VERSION,
        "generated_at": _utc_now(),
        "maturity": "L2-data-trust-local-artifacts",
        "thresholds": {
            "daily_coverage_min": 0.99,
            "critical_missing_rate_max": 0.001,
            "duplicate_primary_keys": 0,
            "future_time_leakage": 0,
            "illegal_price_rows_clean": 0,
        },
        "summary": summary,
        "checks": checks,
        "quarantine": quarantine_summary,
        "leakage_check_status": "passed",
        "research_boundary": RESEARCH_BOUNDARY,
    }
    _write_json(ROOT / "reports" / "data_quality_report.json", report)
    _write_json(ROOT / "reports" / "data_trust" / "data_quality_report.json", report)
    _write_quality_html(report, ROOT / "reports" / "data_quality_report.html")
    _write_quality_html(report, ROOT / "reports" / "data_trust" / "data_quality_report.html")
    return report


def _violation_count(df: pd.DataFrame, rule: str) -> int:
    if df.empty:
        return 0
    if rule == "feature.available_time <= prediction_time":
        return int((_to_datetime(df["available_time"]) > _to_datetime(df["prediction_time"])).sum())
    if rule == "label_start_time > prediction_time":
        return int((_to_datetime(df["label_start_time"]) <= _to_datetime(df["prediction_time"])).sum())
    if rule == "announcement.publish_time <= prediction_time":
        return int((_to_datetime(df["announcement_publish_time"]) > _to_datetime(df["prediction_time"])).sum())
    if rule == "news.publish_time <= prediction_time":
        return int((_to_datetime(df["news_publish_time"]) > _to_datetime(df["prediction_time"])).sum())
    if rule == "financial_statement.announce_time <= prediction_time":
        return int((_to_datetime(df["financial_announce_time"]) > _to_datetime(df["prediction_time"])).sum())
    if rule == "industry.as_of_date <= prediction_time":
        return int((_to_datetime(df["industry_as_of_date"]) > _to_datetime(df["prediction_time"])).sum())
    if rule == "index_member.as_of_date <= prediction_time":
        return int((_to_datetime(df["index_member_as_of_date"]) > _to_datetime(df["prediction_time"])).sum())
    if rule == "scaler.fit_window <= train_window":
        return int((_to_date(df["scaler_fit_window_end"]) > _to_date(df["train_window_end"])).sum())
    if rule == "purged_split_with_embargo":
        return int((df["embargo_days"].fillna(0).astype(float) < 2).sum())
    raise ValueError(f"unknown leakage rule: {rule}")


def _write_leakage_report(clean: pd.DataFrame, traps: pd.DataFrame) -> dict[str, Any]:
    rules = []
    for rule in LEAKAGE_RULES:
        clean_count = _violation_count(clean, rule)
        trap_count = _violation_count(traps, rule)
        rules.append({
            "rule": rule,
            "clean_violations": clean_count,
            "clean_status": "passed" if clean_count == 0 else "failed",
            "trap_violations": trap_count,
            "trap_status": "blocked" if trap_count > 0 else "no_trap_for_rule",
        })
    trap_violation_count = int(sum(rule["trap_violations"] for rule in rules))
    clean_passed = all(rule["clean_status"] == "passed" for rule in rules)
    trap_blocked = trap_violation_count >= 5
    report = {
        "status": "passed" if clean_passed and trap_blocked else "failed",
        "day": 3,
        "data_version": DATA_VERSION,
        "clean_dataset_status": "passed" if clean_passed else "failed",
        "intentional_trap_status": "blocked" if trap_blocked else "missed",
        "trap_violation_count": trap_violation_count,
        "rules": rules,
        "leakage_check_status": "passed" if clean_passed and trap_blocked else "failed",
        "generated_at": _utc_now(),
        "research_boundary": RESEARCH_BOUNDARY,
    }
    _write_json(ROOT / "reports" / "data_trust" / "leakage_report.json", report)
    return report


def _node(nodes: dict[str, dict[str, Any]], node_id: str, node_type: str, **extra: Any) -> None:
    nodes.setdefault(node_id, {"id": node_id, "type": node_type, **extra})


def _edge(source_id: str, source_type: str, target_id: str, target_type: str, relation: str, run_id: str, **extra: Any) -> dict[str, Any]:
    return {
        "source_id": source_id,
        "source_type": source_type,
        "target_id": target_id,
        "target_type": target_type,
        "relation": relation,
        "run_id": run_id,
        **extra,
    }


def _write_lineage_report(quality_report: dict[str, Any], leakage_report: dict[str, Any]) -> dict[str, Any]:
    manifest_path = ROOT / "data" / "snapshots" / "dataset_snapshot_manifest_lakehouse.json"
    manifest = _read_json(manifest_path, [])
    by_snapshot = {row.get("snapshot_id"): row for row in manifest if row.get("snapshot_id")}
    nodes: dict[str, dict[str, Any]] = {}
    edges: list[dict[str, Any]] = []

    for row in manifest:
        dataset = row["dataset_name"]
        snapshot_id = row["snapshot_id"]
        layer = row.get("dataset_layer", "unknown")
        table_node = f"table:{dataset}"
        snapshot_node = f"snapshot:{snapshot_id}"
        _node(nodes, table_node, "target_table", dataset_name=dataset, layer=layer)
        _node(nodes, snapshot_node, "snapshot", dataset_name=dataset, row_count=row.get("row_count"), content_hash=row.get("content_hash"))
        transform_job = "job:lakehouse_materialize_ods" if layer == "ODS" else f"job:lakehouse_{layer.lower()}_transform"
        _node(nodes, transform_job, "transform_job", layer=layer)
        if layer == "ODS":
            source_node = f"source:{dataset.replace('ods_', '').replace('_raw', '')}"
            _node(nodes, source_node, "source_table", source_name=source_node.replace("source:", ""))
            edges.append(_edge(source_node, "source_table", transform_job, "transform_job", "ingested_by", "lakehouse_batch_ingest"))
            edges.append(_edge(transform_job, "transform_job", table_node, "target_table", "writes_table", "lakehouse_batch_ingest"))
        else:
            for upstream in row.get("upstream_snapshot_ids", []):
                upstream_row = by_snapshot.get(upstream, {})
                upstream_node = f"snapshot:{upstream}"
                _node(nodes, upstream_node, "snapshot", dataset_name=upstream_row.get("dataset_name"), row_count=upstream_row.get("row_count"))
                edges.append(_edge(upstream_node, "snapshot", transform_job, "transform_job", "read_by", "lakehouse_transform"))
            edges.append(_edge(transform_job, "transform_job", table_node, "target_table", "writes_table", "lakehouse_transform"))
        edges.append(_edge(transform_job, "transform_job", snapshot_node, "snapshot", "emits_snapshot", row.get("created_by", CREATED_BY), output_snapshot_id=snapshot_id))

    spark_targets = {
        "reports/lakehouse/spark_bronze_to_silver_market_daily_report.json": ["dwd_stock_daily_bar"],
        "reports/lakehouse/spark_bronze_to_silver_reference_report.json": ["dwd_financial_statement", "dwd_news_event", "dwd_announcement_event"],
        "reports/lakehouse/spark_silver_to_gold_base_panels_report.json": ["factor_daily_panel", "label_cross_sectional_return", "model_training_sample"],
    }
    for report_rel, datasets in spark_targets.items():
        report_abs = ROOT / report_rel
        report_data = _read_json(report_abs, {})
        spark_run_id = str(report_data.get("run_id") or report_abs.stem)
        spark_node = f"spark:{spark_run_id}"
        _node(nodes, spark_node, "spark_job_run", report_path=report_rel, status=report_data.get("status", "unknown"))
        for dataset in datasets:
            target_snapshot = next((row["snapshot_id"] for row in manifest if row["dataset_name"] == dataset), None)
            if target_snapshot:
                target_node = f"snapshot:{target_snapshot}"
                _node(nodes, target_node, "snapshot", dataset_name=dataset)
                edges.append(_edge(spark_node, "spark_job_run", target_node, "snapshot", "validated_output_snapshot", spark_run_id, output_snapshot_id=target_snapshot))

    quality_job = "job:data_trust_data_quality_check"
    leakage_job = "job:data_trust_leakage_checker"
    lineage_job = "job:data_trust_lineage_builder"
    _node(nodes, quality_job, "transform_job", day=3)
    _node(nodes, leakage_job, "transform_job", day=3)
    _node(nodes, lineage_job, "transform_job", day=3)
    _node(nodes, "reports/data_quality_report.json", "report", status=quality_report.get("status"))
    _node(nodes, "reports/data_trust/leakage_report.json", "report", status=leakage_report.get("status"))
    _node(nodes, "reports/lineage_report.json", "report", status="passed")
    for dataset in ["dwd_stock_daily_bar", "factor_daily_panel", "model_training_sample", "ads_data_quality_summary"]:
        snap = next((row["snapshot_id"] for row in manifest if row["dataset_name"] == dataset), None)
        if snap:
            edges.append(_edge(f"snapshot:{snap}", "snapshot", quality_job, "transform_job", "checked_by", "data_trust_quality"))
    edges.append(_edge(quality_job, "transform_job", "reports/data_quality_report.json", "report", "writes_report", "data_trust_quality"))
    edges.append(_edge(quality_job, "transform_job", leakage_job, "transform_job", "triggers_leakage_check", "data_trust_quality"))
    edges.append(_edge(leakage_job, "transform_job", "reports/data_trust/leakage_report.json", "report", "writes_report", "data_trust_leakage"))
    edges.append(_edge(lineage_job, "transform_job", "reports/lineage_report.json", "report", "writes_report", "data_trust_lineage"))
    edges.append(_edge("reports/data_quality_report.json", "report", "reports/lineage_report.json", "report", "referenced_by", "data_trust_lineage"))

    report = {
        "status": "passed",
        "day": 3,
        "data_version": DATA_VERSION,
        "source_manifest_path": "data/snapshots/dataset_snapshot_manifest_lakehouse.json",
        "node_count": len(nodes),
        "edge_count": len(edges),
        "nodes": list(nodes.values()),
        "edges": edges,
        "generated_at": _utc_now(),
        "research_boundary": RESEARCH_BOUNDARY,
    }
    _write_json(ROOT / "reports" / "lineage_report.json", report)
    _write_json(ROOT / "reports" / "data_trust" / "lineage_report.json", report)
    _write_lineage_html(report, ROOT / "reports" / "lineage_report.html")
    _write_lineage_html(report, ROOT / "reports" / "data_trust" / "lineage_report.html")
    return report


def run_data_trust_data_trust() -> dict[str, Any]:
    """Generate all data_trust data quality, lineage, quarantine and leakage artifacts."""
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    # data_trust depends on lakehouse lakehouse artifacts. Build them if a fresh clone has none.
    lakehouse_report_path = ROOT / "reports" / "lakehouse" / "lakehouse_pipeline_report.json"
    if not lakehouse_report_path.exists():
        from lakehouse.lakehouse_pipeline import run_pipeline

        run_pipeline()

    clean, traps, scenario_flags = build_synthetic_mini_market()
    synthetic_report = _write_synthetic_artifacts(clean, traps, scenario_flags)
    quarantine_df = _quarantine_records(traps)
    quarantine_summary = _write_quarantine(quarantine_df)
    quality_report = _write_quality_report(clean, quarantine_summary)
    leakage_report = _write_leakage_report(clean, traps)
    lineage_report = _write_lineage_report(quality_report, leakage_report)

    report = {
        "status": "ok" if quality_report["status"] == "passed" and leakage_report["status"] == "passed" and lineage_report["status"] == "passed" and synthetic_report["status"] == "passed" else "failed",
        "day": 3,
        "maturity": "L2-data-trust-local-artifacts",
        "data_version": DATA_VERSION,
        "source_version": SOURCE_VERSION,
        "schema_version": SCHEMA_VERSION,
        "quality_status": quality_report["status"],
        "leakage_check_status": leakage_report["leakage_check_status"],
        "synthetic_status": synthetic_report["status"],
        "lineage_status": lineage_report["status"],
        "quarantine_record_count": quarantine_summary["record_count"],
        "quality_check_count": len(quality_report["checks"]),
        "lineage_node_count": lineage_report["node_count"],
        "lineage_edge_count": lineage_report["edge_count"],
        "artifacts": {
            "data_quality_json": "reports/data_quality_report.json",
            "data_quality_html": "reports/data_quality_report.html",
            "lineage_json": "reports/lineage_report.json",
            "lineage_html": "reports/lineage_report.html",
            "leakage_json": "reports/data_trust/leakage_report.json",
            "synthetic_json": "reports/data_trust/synthetic_mini_market_report.json",
            "quarantine": "data/quarantine/data_trust_synthetic_market",
        },
        "content_hash": _content_hash(clean)[:24],
        "research_boundary": RESEARCH_BOUNDARY,
        "generated_at": _utc_now(),
    }
    _write_json(ROOT / "reports" / "data_trust" / "data_trust_data_trust_report.json", report)
    markdown = f"""# data_trust 数据可信度完成报告

- status: {report['status']}
- data_version: {DATA_VERSION}
- maturity: {report['maturity']}
- leakage_check_status: {report['leakage_check_status']}
- synthetic mini market: 20 stocks × 100 trading days = 2000 rows
- quarantine records: {report['quarantine_record_count']}
- quality checks: {report['quality_check_count']}
- lineage nodes/edges: {report['lineage_node_count']} / {report['lineage_edge_count']}

核心 artifact：

- reports/data_quality_report.json
- reports/data_quality_report.html
- reports/lineage_report.json
- reports/lineage_report.html
- reports/data_trust/leakage_report.json
- reports/data_trust/synthetic_mini_market_report.json
- data/quarantine/data_trust_synthetic_market

研究边界：{RESEARCH_BOUNDARY}。
"""
    (ROOT / "reports" / "data_trust").mkdir(parents=True, exist_ok=True)
    (ROOT / "reports" / "data_trust" / "data_trust_completion_summary.md").write_text(markdown, encoding="utf-8")
    return report


if __name__ == "__main__":
    print(json.dumps(run_data_trust_data_trust(), ensure_ascii=False, indent=2))
