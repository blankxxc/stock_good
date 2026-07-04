from __future__ import annotations

import json
import math
import shutil
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
OUTPUT_DIR = ROOT / "data" / "real" / "csi300_daily"
REPORT_PATH = ROOT / "reports" / "real_data" / "csi300_daily_ingestion_report.json"
RESEARCH_BOUNDARY = "research_signals_only_not_investment_advice"
SCHEMA_VERSION = "real_csi300_daily_v001"
SOURCE_VERSION = "baostock_akshare_current_csi300_constituents_v001"
DATA_VERSION = "real_csi300_recent_3y_daily_v001"


def _json_default(value: Any) -> Any:
    if isinstance(value, (pd.Timestamp, datetime)):
        return value.isoformat()
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        return None
    return str(value)


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=_json_default), encoding="utf-8")


def _display_path(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def _symbol_with_suffix(code: str) -> str:
    raw = str(code).strip().upper()
    if raw.endswith((".SH", ".SZ")):
        return raw
    raw = raw.zfill(6)
    suffix = "SH" if raw.startswith(("5", "6", "9")) else "SZ"
    return f"{raw}.{suffix}"


def _symbol_for_akshare(symbol: str) -> str:
    return str(symbol).split(".", 1)[0].zfill(6)


def _symbol_for_baostock(symbol: str) -> str:
    normalized = _symbol_with_suffix(symbol)
    code, suffix = normalized.split(".", 1)
    return f"{suffix.lower()}.{code}"


def default_date_window(today: datetime | None = None) -> tuple[str, str]:
    now = today or datetime.now(timezone.utc)
    start = now.date() - timedelta(days=365 * 3 + 30)
    end = now.date()
    return start.strftime("%Y%m%d"), end.strftime("%Y%m%d")


def fetch_current_csi300_constituents_baostock() -> pd.DataFrame:
    import baostock as bs

    lg = bs.login()
    try:
        if lg.error_code != "0":
            raise RuntimeError(f"baostock login failed: {lg.error_code} {lg.error_msg}")
        rs = bs.query_hs300_stocks()
        if rs.error_code != "0":
            raise RuntimeError(f"baostock query_hs300_stocks failed: {rs.error_code} {rs.error_msg}")
        rows: list[list[str]] = []
        while rs.next():
            rows.append(rs.get_row_data())
        raw = pd.DataFrame(rows, columns=rs.fields)
        if raw.empty:
            raise RuntimeError("baostock returned empty CSI300 constituents")
        out = pd.DataFrame({"symbol": raw["code"].astype(str).map(lambda code: _symbol_with_suffix(code.split(".", 1)[1]))})
        out["name"] = raw["code_name"].astype(str)
        return out.drop_duplicates("symbol").sort_values("symbol").reset_index(drop=True)
    finally:
        bs.logout()


def fetch_current_csi300_constituents_akshare() -> pd.DataFrame:
    import akshare as ak

    errors: list[str] = []
    for func_name in ("index_stock_cons_csindex", "index_stock_cons"):
        try:
            raw = getattr(ak, func_name)(symbol="000300")
            if raw is not None and not raw.empty:
                break
        except Exception as exc:  # network/provider errors are surfaced in the report
            errors.append(f"{func_name}: {type(exc).__name__}: {exc}")
    else:
        raise RuntimeError("Unable to fetch CSI300 constituents via akshare; " + " | ".join(errors))

    code_col = next(
        (
            c
            for c in raw.columns
            if str(c) in {"成分券代码", "成份券代码", "品种代码", "证券代码"}
            or str(c).lower() in {"code", "symbol", "constituent_code"}
        ),
        next((c for c in raw.columns if "代码" in str(c) and "指数" not in str(c)), raw.columns[0]),
    )
    name_col = next(
        (
            c
            for c in raw.columns
            if str(c) in {"成分券名称", "成份券名称", "品种名称", "证券名称"}
            or str(c).lower() in {"name", "stock_name", "constituent_name"}
        ),
        next((c for c in raw.columns if "名称" in str(c) and "指数" not in str(c) and "英文" not in str(c)), None),
    )
    exchange_col = next((c for c in raw.columns if str(c) in {"交易所", "交易市场", "市场"}), None)
    symbols = raw[code_col].astype(str).str.extract(r"(\d{6})", expand=False).fillna(raw[code_col].astype(str))
    out = pd.DataFrame({"symbol": symbols.map(_symbol_with_suffix)})
    if exchange_col:
        exchange = raw[exchange_col].astype(str)
        out.loc[exchange.str.contains("上海|SH", case=False, regex=True, na=False), "symbol"] = symbols.str.zfill(6) + ".SH"
        out.loc[exchange.str.contains("深圳|SZ", case=False, regex=True, na=False), "symbol"] = symbols.str.zfill(6) + ".SZ"
    out["name"] = raw[name_col].astype(str).to_numpy() if name_col else out["symbol"]
    out = out.drop_duplicates("symbol").sort_values("symbol").reset_index(drop=True)
    return out


def fetch_current_csi300_constituents() -> pd.DataFrame:
    errors: list[str] = []
    for provider_name, fetcher in (("baostock", fetch_current_csi300_constituents_baostock), ("akshare", fetch_current_csi300_constituents_akshare)):
        try:
            constituents = fetcher()
            if len(constituents) < 200:
                raise RuntimeError(f"provider returned suspiciously small CSI300 universe: {len(constituents)}")
            return constituents
        except Exception as exc:
            errors.append(f"{provider_name}: {type(exc).__name__}: {exc}")
    raise RuntimeError("Unable to fetch CSI300 constituents; " + " | ".join(errors))


def fetch_symbol_daily_baostock(symbol: str, start_date: str, end_date: str) -> pd.DataFrame:
    import baostock as bs

    start = f"{start_date[:4]}-{start_date[4:6]}-{start_date[6:8]}"
    end = f"{end_date[:4]}-{end_date[4:6]}-{end_date[6:8]}"
    lg = bs.login()
    try:
        if lg.error_code != "0":
            raise RuntimeError(f"baostock login failed: {lg.error_code} {lg.error_msg}")
        rs = bs.query_history_k_data_plus(
            _symbol_for_baostock(symbol),
            "date,code,open,high,low,close,volume,amount,turn",
            start_date=start,
            end_date=end,
            frequency="d",
            adjustflag="2",
        )
        if rs.error_code != "0":
            raise RuntimeError(f"baostock query_history_k_data_plus failed: {rs.error_code} {rs.error_msg}")
        rows: list[list[str]] = []
        while rs.next():
            rows.append(rs.get_row_data())
        if not rows:
            return pd.DataFrame()
        raw = pd.DataFrame(rows, columns=rs.fields)
        df = raw.rename(columns={"date": "trade_date", "turn": "turnover_rate"}).copy()
        df["symbol"] = _symbol_with_suffix(symbol)
        return df[["trade_date", "open", "high", "low", "close", "volume", "amount", "turnover_rate", "symbol"]]
    finally:
        bs.logout()


def fetch_symbol_daily_akshare(symbol: str, start_date: str, end_date: str) -> pd.DataFrame:
    import akshare as ak

    raw = ak.stock_zh_a_hist(symbol=_symbol_for_akshare(symbol), period="daily", start_date=start_date, end_date=end_date, adjust="qfq")
    if raw is None or raw.empty:
        return pd.DataFrame()
    rename = {
        "日期": "trade_date",
        "开盘": "open",
        "收盘": "close",
        "最高": "high",
        "最低": "low",
        "成交量": "volume",
        "成交额": "amount",
        "换手率": "turnover_rate",
    }
    df = raw.rename(columns=rename).copy()
    required = ["trade_date", "open", "high", "low", "close", "volume", "amount"]
    missing = [col for col in required if col not in df.columns]
    if missing:
        raise KeyError(f"{symbol} missing daily fields from akshare: {missing}; columns={list(raw.columns)}")
    df = df[required + (["turnover_rate"] if "turnover_rate" in df.columns else [])]
    df["symbol"] = _symbol_with_suffix(symbol)
    return df


def fetch_symbol_daily(symbol: str, start_date: str, end_date: str) -> pd.DataFrame:
    errors: list[str] = []
    for provider_name, fetcher in (("baostock", fetch_symbol_daily_baostock), ("akshare", fetch_symbol_daily_akshare)):
        try:
            return fetcher(symbol, start_date, end_date)
        except Exception as exc:
            errors.append(f"{provider_name}: {type(exc).__name__}: {exc}")
    raise RuntimeError(f"Unable to fetch daily bars for {symbol}; " + " | ".join(errors))


def _eastmoney_secid(symbol: str) -> str:
    normalized = _symbol_with_suffix(symbol)
    code, suffix = normalized.split(".", 1)
    market = "1" if suffix == "SH" else "0"
    return f"{market}.{code}"


def _eastmoney_number(value: Any) -> Any:
    return None if value in {None, "-", "--"} else value


def _eastmoney_trade_date(row: dict[str, Any]) -> str:
    timestamp = row.get("f124")
    if timestamp in {None, "-", "--"}:
        return datetime.now(ZoneInfo("Asia/Shanghai")).date().isoformat()
    return datetime.fromtimestamp(int(timestamp), ZoneInfo("Asia/Shanghai")).date().isoformat()


def fetch_eastmoney_quote_snapshot(symbols: list[str]) -> pd.DataFrame:
    """Fetch one same-day Eastmoney quote snapshot for a symbol list.

    This is a freshness bridge for the local research console. It is not a replacement for
    adjusted historical daily bars used by strict backtests.
    """

    if not symbols:
        return pd.DataFrame()

    import requests

    code_to_symbol = {_symbol_for_akshare(symbol): _symbol_with_suffix(symbol) for symbol in symbols}
    rows: list[dict[str, Any]] = []
    url = "https://push2.eastmoney.com/api/qt/ulist.np/get"
    fields = "f12,f14,f2,f5,f6,f15,f16,f17,f18,f20,f21,f8,f124"
    chunk_size = 50
    for offset in range(0, len(symbols), chunk_size):
        chunk = symbols[offset : offset + chunk_size]
        params = {
            "fltt": 2,
            "invt": 2,
            "fields": fields,
            "secids": ",".join(_eastmoney_secid(symbol) for symbol in chunk),
        }
        response = requests.get(url, params=params, timeout=30)
        response.raise_for_status()
        payload = response.json()
        for item in (payload.get("data") or {}).get("diff") or []:
            code = str(item.get("f12", "")).zfill(6)
            symbol = code_to_symbol.get(code)
            if not symbol:
                continue
            rows.append(
                {
                    "trade_date": _eastmoney_trade_date(item),
                    "symbol": symbol,
                    "name": item.get("f14") or symbol,
                    "open": _eastmoney_number(item.get("f17")),
                    "high": _eastmoney_number(item.get("f15")),
                    "low": _eastmoney_number(item.get("f16")),
                    "close": _eastmoney_number(item.get("f2")),
                    "volume": _eastmoney_number(item.get("f5")),
                    "amount": _eastmoney_number(item.get("f6")),
                    "turnover_rate": _eastmoney_number(item.get("f8")),
                }
            )
    return pd.DataFrame(rows)


def fetch_many_symbol_daily_baostock(symbols: list[str], start_date: str, end_date: str) -> tuple[list[pd.DataFrame], list[dict[str, str]]]:
    """Fetch many symbols through BaoStock sessions in chunks to keep full CSI300 ingestion fast and stable."""

    import baostock as bs

    frames: list[pd.DataFrame] = []
    failures: list[dict[str, str]] = []
    start = f"{start_date[:4]}-{start_date[4:6]}-{start_date[6:8]}"
    end = f"{end_date[:4]}-{end_date[4:6]}-{end_date[6:8]}"
    chunk_size = 75
    for offset in range(0, len(symbols), chunk_size):
        chunk = symbols[offset : offset + chunk_size]
        lg = bs.login()
        try:
            if lg.error_code != "0":
                raise RuntimeError(f"baostock login failed: {lg.error_code} {lg.error_msg}")
            for symbol in chunk:
                try:
                    rs = bs.query_history_k_data_plus(
                        _symbol_for_baostock(symbol),
                        "date,code,open,high,low,close,volume,amount,turn",
                        start_date=start,
                        end_date=end,
                        frequency="d",
                        adjustflag="2",
                    )
                    if rs.error_code != "0":
                        raise RuntimeError(f"{rs.error_code} {rs.error_msg}")
                    rows: list[list[str]] = []
                    while rs.next():
                        rows.append(rs.get_row_data())
                    if not rows:
                        continue
                    raw = pd.DataFrame(rows, columns=rs.fields)
                    df = raw.rename(columns={"date": "trade_date", "turn": "turnover_rate"}).copy()
                    df["symbol"] = _symbol_with_suffix(symbol)
                    frames.append(df[["trade_date", "open", "high", "low", "close", "volume", "amount", "turnover_rate", "symbol"]])
                except Exception as exc:
                    failures.append({"symbol": symbol, "error": f"{type(exc).__name__}: {exc}"})
        finally:
            bs.logout()
    return frames, failures


def normalize_real_daily_frame(frame: pd.DataFrame, constituent_names: dict[str, str] | None = None) -> pd.DataFrame:
    df = frame.copy()
    df["trade_date"] = pd.to_datetime(df["trade_date"]).dt.strftime("%Y-%m-%d")
    df["symbol"] = df["symbol"].astype(str).map(_symbol_with_suffix)
    for col in ["open", "high", "low", "close", "volume", "amount"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df = df.dropna(subset=["trade_date", "symbol", "open", "high", "low", "close", "volume", "amount"])
    df = df[df["close"].gt(0) & df["open"].gt(0) & df["high"].ge(df[["open", "close"]].max(axis=1)) & df["low"].le(df[["open", "close"]].min(axis=1))]
    df = df.sort_values(["symbol", "trade_date"]).drop_duplicates(["symbol", "trade_date"], keep="last").reset_index(drop=True)
    names = constituent_names or {}
    df["stock_name"] = df["symbol"].map(names).fillna(df["symbol"])
    df["industry_name"] = "unknown_real_csi300"
    df["adj_factor"] = 1.0
    df["eligible_universe"] = True
    df["tradable_flag"] = df["volume"].fillna(0).gt(0)
    df["delist_flag"] = False
    df["paused"] = ~df["tradable_flag"]
    df["st_flag"] = False
    df["limit_up_flag"] = False
    df["limit_down_flag"] = False
    df["can_buy"] = df["tradable_flag"]
    df["can_sell"] = df["tradable_flag"]
    df["event_time"] = df["trade_date"] + "T15:00:00+08:00"
    df["publish_time"] = df["trade_date"] + "T15:30:00+08:00"
    df["available_time"] = df["publish_time"]
    df["prediction_time"] = df["trade_date"] + "T16:00:00+08:00"
    df["execution_window"] = "t_plus_1_open"
    df["source"] = "baostock_or_akshare_public_web"
    df["source_version"] = SOURCE_VERSION
    df["schema_version"] = SCHEMA_VERSION
    df["data_version"] = DATA_VERSION
    df["license_id"] = "public_web_akshare_research_only"
    df["research_boundary"] = RESEARCH_BOUNDARY
    df["trace_id"] = [f"real-csi300-{i:08d}" for i in range(len(df))]
    return df


def _existing_daily_parquet_path() -> Path:
    return OUTPUT_DIR / "part-000.parquet"


def _read_existing_daily() -> pd.DataFrame:
    path = _existing_daily_parquet_path()
    if not path.exists():
        return pd.DataFrame()
    return pd.read_parquet(path)


def _incremental_start_date(existing: pd.DataFrame, requested_start: str, overlap_days: int) -> tuple[str, str | None]:
    if existing.empty or "trade_date" not in existing.columns:
        return requested_start, None
    latest = pd.to_datetime(existing["trade_date"], errors="coerce").max()
    if pd.isna(latest):
        return requested_start, None
    overlap_start = latest - timedelta(days=max(overlap_days, 0))
    incremental_start = max(requested_start, overlap_start.strftime("%Y%m%d"))
    return incremental_start, latest.strftime("%Y-%m-%d")


def _merge_incremental_daily(existing: pd.DataFrame, refreshed: pd.DataFrame) -> pd.DataFrame:
    if existing.empty:
        return refreshed.sort_values(["symbol", "trade_date"]).reset_index(drop=True)
    if refreshed.empty:
        return existing.sort_values(["symbol", "trade_date"]).reset_index(drop=True)
    merged = pd.concat([existing, refreshed], ignore_index=True, sort=False)
    merged["trade_date"] = pd.to_datetime(merged["trade_date"]).dt.strftime("%Y-%m-%d")
    merged["symbol"] = merged["symbol"].astype(str).map(_symbol_with_suffix)
    for col in ["open", "high", "low", "close", "volume", "amount", "turnover_rate", "adj_factor"]:
        if col in merged.columns:
            merged[col] = pd.to_numeric(merged[col], errors="coerce")
    return (
        merged.sort_values(["symbol", "trade_date"])
        .drop_duplicates(["symbol", "trade_date"], keep="last")
        .reset_index(drop=True)
    )


def _constituents_from_existing_daily(existing: pd.DataFrame) -> pd.DataFrame:
    if existing.empty or "symbol" not in existing.columns:
        return pd.DataFrame()
    latest_names = existing.sort_values(["symbol", "trade_date"]).drop_duplicates("symbol", keep="last")
    names = latest_names["stock_name"] if "stock_name" in latest_names.columns else latest_names["symbol"]
    return (
        pd.DataFrame({"symbol": latest_names["symbol"].astype(str).map(_symbol_with_suffix), "name": names.astype(str)})
        .drop_duplicates("symbol")
        .sort_values("symbol")
        .reset_index(drop=True)
    )


def _write_daily_parquet(output: pd.DataFrame) -> None:
    temp_dir = OUTPUT_DIR.with_name(f"{OUTPUT_DIR.name}_tmp")
    shutil.rmtree(temp_dir, ignore_errors=True)
    temp_dir.mkdir(parents=True, exist_ok=True)
    output.to_parquet(temp_dir / "part-000.parquet", index=False)
    shutil.rmtree(OUTPUT_DIR, ignore_errors=True)
    temp_dir.replace(OUTPUT_DIR)


def write_real_csi300_daily(
    max_symbols: int | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    incremental: bool = False,
    overlap_days: int = 7,
    use_snapshot: bool = False,
) -> dict[str, Any]:
    default_start, default_end = default_date_window()
    start = start_date or default_start
    end = end_date or default_end
    existing = pd.DataFrame()
    previous_latest_trade_date: str | None = None
    requested_incremental_start_date = start
    try:
        if incremental:
            existing = _read_existing_daily()
            requested_incremental_start_date, previous_latest_trade_date = _incremental_start_date(existing, start, overlap_days)
            start = requested_incremental_start_date

        existing_constituents = _constituents_from_existing_daily(existing) if incremental and not existing.empty else pd.DataFrame()
        try:
            constituents = fetch_current_csi300_constituents()
        except Exception:
            constituents = existing_constituents
        if constituents.empty:
            constituents = existing_constituents
        if not existing_constituents.empty:
            missing_existing = existing_constituents[~existing_constituents["symbol"].isin(constituents["symbol"])]
            if not missing_existing.empty:
                constituents = pd.concat([constituents, missing_existing], ignore_index=True, sort=False).drop_duplicates("symbol").sort_values("symbol").reset_index(drop=True)
        if max_symbols:
            constituents = constituents.head(max_symbols).copy()
        frames: list[pd.DataFrame] = []
        failures: list[dict[str, str]] = []
        used_snapshot = False
        snapshot_row_count = 0
        names = dict(zip(constituents["symbol"], constituents["name"], strict=False))
        symbols = constituents["symbol"].astype(str).tolist()
        if incremental and use_snapshot:
            try:
                snapshot = fetch_eastmoney_quote_snapshot(symbols)
                if not snapshot.empty:
                    frames = [snapshot]
                    snapshot_row_count = int(len(snapshot))
                    used_snapshot = True
            except Exception as exc:
                failures.append({"symbol": "__eastmoney_snapshot__", "error": f"{type(exc).__name__}: {exc}"})
        if not frames and not (incremental and use_snapshot) and fetch_symbol_daily.__module__ == __name__ and fetch_symbol_daily.__name__ == "fetch_symbol_daily":
            try:
                frames, failures = fetch_many_symbol_daily_baostock(symbols, start, end)
            except Exception as exc:
                failures = [{"symbol": "__batch__", "error": f"{type(exc).__name__}: {exc}"}]
        if not frames:
            for symbol in symbols:
                try:
                    hist = fetch_symbol_daily(symbol, start, end)
                    if not hist.empty:
                        frames.append(hist)
                except Exception as exc:
                    failures.append({"symbol": symbol, "error": f"{type(exc).__name__}: {exc}"})
        if not frames:
            if incremental and not existing.empty:
                normalized = pd.DataFrame()
                output = existing.sort_values(["symbol", "trade_date"]).reset_index(drop=True)
            else:
                raise RuntimeError(f"No CSI300 daily rows fetched; failures={failures[:5]}")
        else:
            normalized = normalize_real_daily_frame(pd.concat(frames, ignore_index=True, sort=False), names)
            if used_snapshot:
                normalized["source"] = "eastmoney_quote_snapshot_public_web"
                normalized["source_version"] = "eastmoney_push2_quote_snapshot_v001"
                normalized["license_id"] = "eastmoney_public_web_research_only"
            output = _merge_incremental_daily(existing, normalized) if incremental else normalized

        _write_daily_parquet(output)
        latest_trade_date = None if output.empty else str(output["trade_date"].max())
        latest_stock_count = 0
        if latest_trade_date:
            latest_stock_count = int(output[output["trade_date"].astype(str).eq(latest_trade_date)]["symbol"].nunique())
        fetched_rows = int(0 if "normalized" not in locals() else len(normalized))
        data_source_mode = "real_csi300_recent_3y_daily"
        if incremental and not existing.empty:
            data_source_mode = "real_csi300_daily_incremental_plus_eastmoney_snapshot" if used_snapshot else "real_csi300_daily_incremental"
        report = {
            "status": "ok",
            "data_source_mode": data_source_mode,
            "data_version": DATA_VERSION,
            "source_version": SOURCE_VERSION,
            "incremental_update": bool(incremental and not existing.empty),
            "overlap_days": int(overlap_days),
            "previous_row_count": int(len(existing)) if incremental and not existing.empty else 0,
            "previous_latest_trade_date": previous_latest_trade_date,
            "snapshot_row_count": snapshot_row_count,
            "snapshot_caveat": "same-day quote snapshot for research-console freshness; replace with adjusted historical daily bars for strict backtests" if used_snapshot else None,
            "fetched_row_count": fetched_rows,
            "row_count": int(len(output)),
            "stock_count": int(output["symbol"].nunique()) if "symbol" in output.columns else 0,
            "latest_stock_count": latest_stock_count,
            "start_date": str(output["trade_date"].min()) if not output.empty else None,
            "end_date": latest_trade_date,
            "requested_start_date": start_date or default_start,
            "requested_incremental_start_date": requested_incremental_start_date,
            "requested_end_date": end,
            "constituent_method": "baostock current CSI300 constituents with akshare fallback; replace with point-in-time membership before production backtests",
            "failed_symbols": failures,
            "output_path": _display_path(OUTPUT_DIR),
            "research_boundary": RESEARCH_BOUNDARY,
            "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        }
    except Exception as exc:
        report = {
            "status": "failed",
            "data_source_mode": "real_csi300_recent_3y_daily_unavailable",
            "error": f"{type(exc).__name__}: {exc}",
            "remediation": "Check network/SSL access to Eastmoney/CSIndex via akshare, or place normalized parquet under data/real/csi300_daily/part-000.parquet.",
            "expected_schema": ["trade_date", "symbol", "open", "high", "low", "close", "volume", "amount", "available_time", "prediction_time"],
            "research_boundary": RESEARCH_BOUNDARY,
            "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        }
    _write_json(REPORT_PATH, report)
    return report


if __name__ == "__main__":
    print(json.dumps(write_real_csi300_daily(), ensure_ascii=False, indent=2, default=_json_default))
