from __future__ import annotations

import json
import math
import os
import random
import socket
import threading
import time
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4
from zoneinfo import ZoneInfo

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
OUTPUT_DIR = ROOT / "data" / "real" / "csi300_daily"
REPORT_PATH = ROOT / "reports" / "real_data" / "csi300_daily_ingestion_report.json"
MEMBERSHIP_PATH = ROOT / "data" / "real" / "csi300_membership" / "current.parquet"
MEMBERSHIP_HISTORY_PATH = ROOT / "data" / "real" / "csi300_membership" / "history.parquet"
SNAPSHOT_PATH = ROOT / "data" / "real" / "csi300_intraday_snapshot" / "latest.parquet"
CALENDAR_PATH = ROOT / "data" / "real" / "trading_calendar" / "sse_szse.parquet"
RESEARCH_BOUNDARY = "research_signals_only_not_investment_advice"
SCHEMA_VERSION = "real_csi300_daily_v002"
SOURCE_VERSION = "baostock_akshare_current_csi300_constituents_v002"
DATA_VERSION = "real_csi300_recent_3y_daily_hfq_v002"
PRICE_ADJUSTMENT_MODE = "hfq"
EXPECTED_UNIVERSE_SIZE = 300
MIN_LATEST_COVERAGE_RATIO = 0.95
MAX_CACHED_UNIVERSE_AGE_DAYS = 14
PROVIDER_RETRY_ATTEMPTS = 2
PROVIDER_RETRY_BASE_SECONDS = 0.5
_PROCESS_LOCK_GUARD = threading.Lock()
_PROCESS_LOCK_PATHS: set[str] = set()
KEY_COLUMNS = ["symbol", "trade_date"]
MARKET_VALUE_COLUMNS = [
    "stock_name",
    "open",
    "high",
    "low",
    "close",
    "volume",
    "amount",
    "turnover_rate",
    "source",
    "source_version",
]


def _json_default(value: Any) -> Any:
    if isinstance(value, (pd.Timestamp, datetime)):
        return value.isoformat()
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        return None
    return str(value)


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
    try:
        temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=_json_default), encoding="utf-8")
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _write_ingestion_report(payload: dict[str, Any]) -> None:
    report = dict(payload)
    generated_at = str(report.setdefault("generated_at", datetime.now(timezone.utc).isoformat(timespec="seconds")))
    run_id = str(report.setdefault("run_id", uuid4().hex))
    _write_json(REPORT_PATH, report)
    safe_timestamp = generated_at.replace(":", "").replace("+", "_")
    try:
        _write_json(REPORT_PATH.parent / "history" / f"{safe_timestamp}_{run_id}.json", report)
    except OSError:
        pass


def _display_path(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def _call_with_retry(fetcher: Any, *args: Any) -> Any:
    last_error: Exception | None = None
    for attempt in range(PROVIDER_RETRY_ATTEMPTS):
        try:
            return fetcher(*args)
        except Exception as exc:
            last_error = exc
            if attempt + 1 < PROVIDER_RETRY_ATTEMPTS:
                delay = PROVIDER_RETRY_BASE_SECONDS * (2**attempt) + random.uniform(0, 0.2)
                time.sleep(delay)
    assert last_error is not None
    raise last_error


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
    now = today or datetime.now(ZoneInfo("Asia/Shanghai"))
    start = now.date() - timedelta(days=365 * 3 + 30)
    end = now.date()
    return start.strftime("%Y%m%d"), end.strftime("%Y%m%d")


def fetch_trade_dates_baostock(start_date: str, end_date: str) -> list[str]:
    import baostock as bs

    start = f"{start_date[:4]}-{start_date[4:6]}-{start_date[6:8]}"
    end = f"{end_date[:4]}-{end_date[4:6]}-{end_date[6:8]}"
    lg = bs.login()
    try:
        if lg.error_code != "0":
            raise RuntimeError(f"baostock login failed: {lg.error_code} {lg.error_msg}")
        rs = bs.query_trade_dates(start_date=start, end_date=end)
        if rs.error_code != "0":
            raise RuntimeError(f"baostock query_trade_dates failed: {rs.error_code} {rs.error_msg}")
        rows: list[list[str]] = []
        while rs.next():
            rows.append(rs.get_row_data())
        raw = pd.DataFrame(rows, columns=rs.fields)
        if raw.empty:
            return []
        return sorted(raw.loc[raw["is_trading_day"].astype(str).eq("1"), "calendar_date"].astype(str).tolist())
    finally:
        bs.logout()


def fetch_trade_dates_akshare(start_date: str, end_date: str) -> list[str]:
    import akshare as ak

    raw = ak.tool_trade_date_hist_sina()
    if raw is None or raw.empty or "trade_date" not in raw.columns:
        raise RuntimeError("akshare returned no trading calendar")
    dates = pd.to_datetime(raw["trade_date"], errors="coerce").dropna()
    start = datetime.strptime(start_date, "%Y%m%d").date()
    end = datetime.strptime(end_date, "%Y%m%d").date()
    return sorted(value.date().isoformat() for value in dates if start <= value.date() <= end)


def _read_cached_trade_dates(start_date: str, end_date: str) -> list[str]:
    if not CALENDAR_PATH.exists():
        return []
    cached = pd.read_parquet(CALENDAR_PATH)
    if cached.empty or not {"trade_date", "covered_through"}.issubset(cached.columns):
        return []
    if str(cached["covered_through"].max()).replace("-", "") < end_date:
        return []
    values = pd.to_datetime(cached["trade_date"], errors="coerce").dropna()
    start = datetime.strptime(start_date, "%Y%m%d").date()
    end = datetime.strptime(end_date, "%Y%m%d").date()
    return sorted(value.date().isoformat() for value in values if start <= value.date() <= end)


def fetch_trade_dates(start_date: str, end_date: str) -> tuple[list[str], str]:
    errors: list[str] = []
    for provider, fetcher in (("baostock", fetch_trade_dates_baostock), ("akshare", fetch_trade_dates_akshare)):
        try:
            dates = _call_with_retry(fetcher, start_date, end_date)
            calendar = pd.DataFrame({"trade_date": dates})
            calendar["covered_through"] = datetime.strptime(end_date, "%Y%m%d").date().isoformat()
            calendar["source"] = provider
            _atomic_write_parquet(calendar, CALENDAR_PATH)
            return dates, provider
        except Exception as exc:
            errors.append(f"{provider}: {type(exc).__name__}: {exc}")
    cached = _read_cached_trade_dates(start_date, end_date)
    if cached:
        return cached, "cache"
    raise RuntimeError("Unable to load a verified China A-share trading calendar; " + " | ".join(errors))


def _latest_completed_trade_date(trade_dates: list[str], requested_end: str, now: datetime | None = None) -> str | None:
    current = now or datetime.now(ZoneInfo("Asia/Shanghai"))
    end = min(datetime.strptime(requested_end, "%Y%m%d").date(), current.date())
    candidates = [datetime.strptime(value, "%Y-%m-%d").date() for value in trade_dates if datetime.strptime(value, "%Y-%m-%d").date() <= end]
    if current.time() < datetime.strptime("16:30", "%H:%M").time():
        candidates = [value for value in candidates if value < current.date()]
    return max(candidates).isoformat() if candidates else None


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
            constituents = _call_with_retry(fetcher)
            if len(constituents) != EXPECTED_UNIVERSE_SIZE:
                raise RuntimeError(
                    f"provider returned {len(constituents)} CSI300 constituents; expected {EXPECTED_UNIVERSE_SIZE}"
                )
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
            adjustflag="1",
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
        df["source"] = "baostock_public_web"
        df["source_version"] = "baostock_history_k_daily_hfq_v001"
        df["license_id"] = "public_web_baostock_research_only"
        return df[
            [
                "trade_date",
                "open",
                "high",
                "low",
                "close",
                "volume",
                "amount",
                "turnover_rate",
                "symbol",
                "source",
                "source_version",
                "license_id",
            ]
        ]
    finally:
        bs.logout()


def fetch_symbol_daily_akshare(symbol: str, start_date: str, end_date: str) -> pd.DataFrame:
    import akshare as ak

    raw = ak.stock_zh_a_hist(
        symbol=_symbol_for_akshare(symbol),
        period="daily",
        start_date=start_date,
        end_date=end_date,
        adjust="hfq",
        timeout=30,
    )
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
    # Eastmoney/AkShare daily volume is expressed in lots; the canonical contract uses shares.
    df["volume"] = pd.to_numeric(df["volume"], errors="coerce") * 100
    df["symbol"] = _symbol_with_suffix(symbol)
    df["source"] = "akshare_eastmoney_public_web"
    df["source_version"] = "akshare_stock_zh_a_hist_daily_hfq_v001"
    df["license_id"] = "public_web_akshare_research_only"
    return df


def fetch_symbol_daily(symbol: str, start_date: str, end_date: str) -> pd.DataFrame:
    errors: list[str] = []
    provider_responded = False
    for provider_name, fetcher in (("baostock", fetch_symbol_daily_baostock), ("akshare", fetch_symbol_daily_akshare)):
        try:
            frame = _call_with_retry(fetcher, symbol, start_date, end_date)
            provider_responded = True
            if not frame.empty:
                return frame
        except Exception as exc:
            errors.append(f"{provider_name}: {type(exc).__name__}: {exc}")
    if provider_responded:
        return pd.DataFrame()
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
    output = pd.DataFrame(rows)
    if not output.empty:
        output["volume"] = pd.to_numeric(output["volume"], errors="coerce") * 100
    return output


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
                    df["source"] = "baostock_public_web"
                    df["source_version"] = "baostock_history_k_daily_hfq_v001"
                    df["license_id"] = "public_web_baostock_research_only"
                    frames.append(df)
                except Exception as exc:
                    failures.append({"symbol": symbol, "error": f"{type(exc).__name__}: {exc}"})
        finally:
            bs.logout()
    return frames, failures


def normalize_real_daily_frame(frame: pd.DataFrame, constituent_names: dict[str, str] | None = None) -> pd.DataFrame:
    df = frame.copy()
    df["trade_date"] = pd.to_datetime(df["trade_date"]).dt.strftime("%Y-%m-%d")
    df["symbol"] = df["symbol"].astype(str).map(_symbol_with_suffix)
    for col in ["open", "high", "low", "close", "volume", "amount", "turnover_rate"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    df = df.dropna(subset=["trade_date", "symbol", "open", "high", "low", "close", "volume", "amount"])
    df = df[df["close"].gt(0) & df["open"].gt(0) & df["high"].ge(df[["open", "close"]].max(axis=1)) & df["low"].le(df[["open", "close"]].min(axis=1))]
    df = df.sort_values(["symbol", "trade_date"]).drop_duplicates(["symbol", "trade_date"], keep="last").reset_index(drop=True)
    names = constituent_names or {}
    df["stock_name"] = df["symbol"].map(names).fillna(df["symbol"])
    df["industry_name"] = "unknown_real_csi300"
    df["adj_factor"] = 1.0
    df["adjustment_mode"] = PRICE_ADJUSTMENT_MODE
    df["volume_unit"] = "share"
    df["amount_unit"] = "CNY"
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
    if "source" in df.columns:
        df["source"] = df["source"].fillna("baostock_or_akshare_public_web")
    else:
        df["source"] = "baostock_or_akshare_public_web"
    if "source_version" in df.columns:
        df["source_version"] = df["source_version"].fillna(SOURCE_VERSION)
    else:
        df["source_version"] = SOURCE_VERSION
    df["schema_version"] = SCHEMA_VERSION
    df["data_version"] = DATA_VERSION
    if "license_id" in df.columns:
        df["license_id"] = df["license_id"].fillna("public_web_akshare_research_only")
    else:
        df["license_id"] = "public_web_akshare_research_only"
    df["research_boundary"] = RESEARCH_BOUNDARY
    df["trace_id"] = "real-csi300-" + df["symbol"].str.replace(".", "", regex=False) + "-" + df["trade_date"].str.replace("-", "", regex=False)
    return df


def _existing_daily_parquet_path() -> Path:
    return OUTPUT_DIR / "part-000.parquet"


def _read_existing_daily() -> pd.DataFrame:
    path = _existing_daily_parquet_path()
    if not path.exists():
        return pd.DataFrame()
    return pd.read_parquet(path)


def _read_cached_current_constituents() -> pd.DataFrame:
    if not MEMBERSHIP_PATH.exists():
        return pd.DataFrame()
    cached = pd.read_parquet(MEMBERSHIP_PATH)
    required = {"symbol", "name"}
    if cached.empty or not required.issubset(cached.columns):
        return pd.DataFrame()
    return cached[["symbol", "name"]].drop_duplicates("symbol").sort_values("symbol").reset_index(drop=True)


def _cached_current_constituents_age_days(now: datetime | None = None) -> int | None:
    if not MEMBERSHIP_PATH.exists():
        return None
    cached = pd.read_parquet(MEMBERSHIP_PATH, columns=["as_of_date"])
    if cached.empty:
        return None
    as_of = pd.to_datetime(cached["as_of_date"], errors="coerce").max()
    if pd.isna(as_of):
        return None
    current = (now or datetime.now(ZoneInfo("Asia/Shanghai"))).date()
    return max((current - pd.Timestamp(as_of).date()).days, 0)


def _atomic_write_parquet(frame: pd.DataFrame, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(f".{target.stem}.{uuid4().hex}.tmp.parquet")
    try:
        frame.to_parquet(temporary, index=False)
        os.replace(temporary, target)
    finally:
        temporary.unlink(missing_ok=True)


def _write_current_constituents(constituents: pd.DataFrame, as_of_date: str) -> None:
    snapshot = constituents[["symbol", "name"]].copy()
    snapshot["as_of_date"] = as_of_date
    snapshot["source_version"] = SOURCE_VERSION
    _atomic_write_parquet(snapshot, MEMBERSHIP_PATH)
    history = pd.read_parquet(MEMBERSHIP_HISTORY_PATH) if MEMBERSHIP_HISTORY_PATH.exists() else pd.DataFrame()
    history = (
        pd.concat([history, snapshot], ignore_index=True, sort=False)
        .drop_duplicates(["as_of_date", "symbol"], keep="last")
        .sort_values(["as_of_date", "symbol"])
        .reset_index(drop=True)
    )
    _atomic_write_parquet(history, MEMBERSHIP_HISTORY_PATH)


def _incremental_start_date(existing: pd.DataFrame, requested_start: str, overlap_days: int) -> tuple[str, str | None]:
    if existing.empty or "trade_date" not in existing.columns:
        return requested_start, None
    latest = pd.to_datetime(existing["trade_date"], errors="coerce").max()
    if pd.isna(latest):
        return requested_start, None
    overlap_start = latest - timedelta(days=max(overlap_days, 0))
    incremental_start = max(requested_start, overlap_start.strftime("%Y%m%d"))
    return incremental_start, latest.strftime("%Y-%m-%d")


def _symbol_incremental_start_dates(
    existing: pd.DataFrame,
    symbols: list[str],
    requested_start: str,
    overlap_days: int,
) -> dict[str, str]:
    if existing.empty or "trade_date" not in existing.columns or "symbol" not in existing.columns:
        return {symbol: requested_start for symbol in symbols}
    normalized = existing[["symbol", "trade_date"]].copy()
    normalized["symbol"] = normalized["symbol"].astype(str).map(_symbol_with_suffix)
    normalized["trade_date"] = pd.to_datetime(normalized["trade_date"], errors="coerce")
    latest_by_symbol = normalized.dropna(subset=["trade_date"]).groupby("symbol")["trade_date"].max().to_dict()
    windows: dict[str, str] = {}
    for symbol in symbols:
        latest = latest_by_symbol.get(_symbol_with_suffix(symbol))
        if latest is None or pd.isna(latest):
            windows[symbol] = requested_start
            continue
        overlap_start = pd.Timestamp(latest) - timedelta(days=overlap_days)
        windows[symbol] = max(requested_start, overlap_start.strftime("%Y%m%d"))
    return windows


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


def _dataset_change_summary(existing: pd.DataFrame, candidate: pd.DataFrame) -> dict[str, int | bool]:
    if candidate.empty and existing.empty:
        return {"data_changed": False, "new_row_count": 0, "revised_row_count": 0, "deleted_row_count": 0}
    if existing.empty:
        return {
            "data_changed": not candidate.empty,
            "new_row_count": int(len(candidate)),
            "revised_row_count": 0,
            "deleted_row_count": 0,
        }

    left = existing.drop_duplicates(KEY_COLUMNS, keep="last").set_index(KEY_COLUMNS).sort_index()
    right = candidate.drop_duplicates(KEY_COLUMNS, keep="last").set_index(KEY_COLUMNS).sort_index()
    new_keys = right.index.difference(left.index)
    deleted_keys = left.index.difference(right.index)
    common_keys = right.index.intersection(left.index)
    comparable = [column for column in MARKET_VALUE_COLUMNS if column in left.columns and column in right.columns]
    revised_count = 0
    if len(common_keys) and comparable:
        old_values = left.loc[common_keys, comparable]
        new_values = right.loc[common_keys, comparable]
        equal_cells = old_values.eq(new_values) | (old_values.isna() & new_values.isna())
        revised_count = int((~equal_cells.all(axis=1)).sum())
    new_count = int(len(new_keys))
    return {
        "data_changed": bool(new_count or revised_count or len(deleted_keys)),
        "new_row_count": new_count,
        "revised_row_count": revised_count,
        "deleted_row_count": int(len(deleted_keys)),
    }


def _cross_provider_consistency_errors(existing: pd.DataFrame, refreshed: pd.DataFrame) -> list[str]:
    required = {"symbol", "trade_date", "close", "source"}
    if existing.empty or refreshed.empty or not required.issubset(existing.columns) or not required.issubset(refreshed.columns):
        return []
    old = existing[list(required)].drop_duplicates(KEY_COLUMNS, keep="last")
    new = refreshed[list(required)].drop_duplicates(KEY_COLUMNS, keep="last")
    compared = old.merge(new, on=KEY_COLUMNS, suffixes=("_old", "_new"))
    compared = compared[compared["source_old"].astype(str).ne(compared["source_new"].astype(str))].copy()
    if compared.empty:
        return []
    old_close = pd.to_numeric(compared["close_old"], errors="coerce")
    new_close = pd.to_numeric(compared["close_new"], errors="coerce")
    relative_error = (new_close - old_close).abs() / old_close.abs().replace(0, pd.NA)
    bad = compared[relative_error.gt(0.005).fillna(False)]
    if bad.empty:
        return []
    examples = bad[KEY_COLUMNS].head(5).astype(str).agg("/".join, axis=1).tolist()
    return [
        f"cross-provider adjusted close mismatch above 0.5% for {len(bad)} overlapping rows; examples={examples}"
    ]


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
    _atomic_write_parquet(output, _existing_daily_parquet_path())


def _lock_path() -> Path:
    return OUTPUT_DIR.parent / f".{OUTPUT_DIR.name}.update.lock"


@contextmanager
def _exclusive_file_lock(lock_path: Path, purpose: str):
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    resolved_lock_path = str(lock_path.resolve())
    with _PROCESS_LOCK_GUARD:
        if resolved_lock_path in _PROCESS_LOCK_PATHS:
            raise RuntimeError(f"{purpose} already running; lock={_display_path(lock_path)}")
        _PROCESS_LOCK_PATHS.add(resolved_lock_path)
    try:
        handle = lock_path.open("a+b")
    except Exception:
        with _PROCESS_LOCK_GUARD:
            _PROCESS_LOCK_PATHS.discard(resolved_lock_path)
        raise
    locked = False
    owner_token = uuid4().hex
    metadata_path = lock_path.with_name(f"{lock_path.name}.meta.json")
    try:
        handle.seek(0)
        if handle.read(1) == b"":
            handle.seek(0)
            handle.write(b"\0")
            handle.flush()
        handle.seek(0)
        try:
            if os.name == "nt":
                import msvcrt

                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl

                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            locked = True
        except OSError as exc:
            raise RuntimeError(f"{purpose} already running; lock={_display_path(lock_path)}") from exc

        _write_json(
            metadata_path,
            {
                "pid": os.getpid(),
                "host": socket.gethostname(),
                "owner_token": owner_token,
                "purpose": purpose,
                "started_at": datetime.now(timezone.utc).isoformat(),
            },
        )
        yield
    finally:
        if locked:
            handle.seek(0)
            if os.name == "nt":
                import msvcrt

                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl

                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        handle.close()
        try:
            metadata = json.loads(metadata_path.read_text(encoding="utf-8")) if metadata_path.exists() else {}
            if metadata.get("owner_token") == owner_token:
                metadata_path.unlink(missing_ok=True)
        except (OSError, json.JSONDecodeError):
            pass
        with _PROCESS_LOCK_GUARD:
            _PROCESS_LOCK_PATHS.discard(resolved_lock_path)


@contextmanager
def _exclusive_update_lock():
    with _exclusive_file_lock(_lock_path(), "daily data update"):
        yield


def _write_real_csi300_daily_unlocked(
    max_symbols: int | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    incremental: bool = True,
    overlap_days: int = 7,
    use_snapshot: bool = False,
    validate_freshness: bool = True,
) -> dict[str, Any]:
    default_start, default_end = default_date_window()
    try:
        requested_start = start_date or default_start
        requested_end = end_date or default_end
        if overlap_days < 0:
            raise ValueError("overlap_days must be non-negative")
        start_value = datetime.strptime(requested_start, "%Y%m%d")
        end_value = datetime.strptime(requested_end, "%Y%m%d")
        if start_value > end_value:
            raise ValueError("start_date must not be after end_date")

        existing = _read_existing_daily()
        previous_latest_trade_date = None if existing.empty else str(existing["trade_date"].max())
        existing_version = None if existing.empty or "data_version" not in existing.columns else str(existing["data_version"].dropna().iloc[-1])
        existing_adjustment = None if existing.empty or "adjustment_mode" not in existing.columns else str(existing["adjustment_mode"].dropna().iloc[-1])
        migration_required = bool(
            incremental
            and not existing.empty
            and (existing_version != DATA_VERSION or existing_adjustment != PRICE_ADJUSTMENT_MODE)
        )
        effective_incremental = bool(incremental and not migration_required)

        universe_warning: str | None = None
        universe_source = "live"
        try:
            constituents = fetch_current_csi300_constituents()
        except Exception as exc:
            constituents = _read_cached_current_constituents()
            universe_source = "cache"
            universe_warning = f"{type(exc).__name__}: {exc}"
            cached_age_days = _cached_current_constituents_age_days()
            if cached_age_days is None or cached_age_days > MAX_CACHED_UNIVERSE_AGE_DAYS:
                raise RuntimeError(
                    f"CSI300 universe refresh failed and cached membership is stale; "
                    f"cache_age_days={cached_age_days}; error={universe_warning}"
                ) from exc
        if constituents.empty or (validate_freshness and len(constituents) != EXPECTED_UNIVERSE_SIZE):
            raise RuntimeError(
                f"No verified {EXPECTED_UNIVERSE_SIZE}-stock CSI300 universe is available; "
                f"received={len(constituents)}; warning={universe_warning}"
            )
        constituents = constituents.drop_duplicates("symbol").sort_values("symbol").reset_index(drop=True)
        full_universe_size = int(len(constituents))
        smoke_mode = bool(max_symbols and max_symbols < full_universe_size)
        if max_symbols:
            constituents = constituents.head(max_symbols).copy()

        names = dict(zip(constituents["symbol"], constituents["name"], strict=False))
        symbols = constituents["symbol"].astype(str).tolist()
        symbol_starts = (
            _symbol_incremental_start_dates(existing, symbols, requested_start, overlap_days)
            if effective_incremental
            else {symbol: requested_start for symbol in symbols}
        )
        requested_incremental_start_date = min(symbol_starts.values(), default=requested_start)

        trade_dates: list[str] = []
        calendar_source = "disabled"
        expected_latest_trade_date: str | None = None
        fetch_end = requested_end
        if validate_freshness:
            trade_dates, calendar_source = fetch_trade_dates(requested_incremental_start_date, requested_end)
            expected_latest_trade_date = _latest_completed_trade_date(trade_dates, requested_end)
            if expected_latest_trade_date:
                fetch_end = expected_latest_trade_date.replace("-", "")
        if requested_incremental_start_date > fetch_end:
            candidate = existing.copy()
            candidate_summary = _dataset_change_summary(existing, candidate)
            report = {
                "status": "no_change",
                "data_source_mode": "real_csi300_daily_incremental",
                "data_version": DATA_VERSION,
                "source_version": SOURCE_VERSION,
                "incremental_update": effective_incremental,
                "migration_required": migration_required,
                "data_changed": False,
                "candidate_data_changed": False,
                "new_row_count": 0,
                "revised_row_count": 0,
                "deleted_row_count": 0,
                "write_performed": False,
                "row_count": int(len(existing)),
                "stock_count": int(existing["symbol"].nunique()) if "symbol" in existing.columns else 0,
                "previous_latest_trade_date": previous_latest_trade_date,
                "expected_latest_trade_date": expected_latest_trade_date,
                "requested_start_date": requested_start,
                "requested_incremental_start_date": requested_incremental_start_date,
                "requested_end_date": requested_end,
                "calendar_source": calendar_source,
                "reason": "requested range does not include a completed trading day after the local watermark",
                "research_boundary": RESEARCH_BOUNDARY,
            }
            _write_ingestion_report(report)
            return report

        frames: list[pd.DataFrame] = []
        attempt_failures: list[dict[str, str]] = []
        used_snapshot = False
        snapshot_row_count = 0
        if effective_incremental and use_snapshot:
            try:
                snapshot = fetch_eastmoney_quote_snapshot(symbols)
                if not snapshot.empty:
                    snapshot["source"] = "eastmoney_quote_snapshot_public_web"
                    snapshot["source_version"] = "eastmoney_push2_quote_snapshot_v001"
                    snapshot["license_id"] = "eastmoney_public_web_research_only"
                    snapshot["snapshot_captured_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
                    _atomic_write_parquet(snapshot, SNAPSHOT_PATH)
                    snapshot_row_count = int(len(snapshot))
                    used_snapshot = True
            except Exception as exc:
                attempt_failures.append({"symbol": "__eastmoney_snapshot__", "provider": "eastmoney_snapshot", "error": f"{type(exc).__name__}: {exc}"})

        if fetch_symbol_daily.__module__ == __name__ and fetch_symbol_daily.__name__ == "fetch_symbol_daily":
            symbols_by_start: dict[str, list[str]] = {}
            for symbol, symbol_start in symbol_starts.items():
                symbols_by_start.setdefault(symbol_start, []).append(symbol)
            for symbol_start, window_symbols in symbols_by_start.items():
                try:
                    batch_frames, batch_failures = fetch_many_symbol_daily_baostock(window_symbols, symbol_start, fetch_end)
                    frames.extend(batch_frames)
                    attempt_failures.extend({**item, "provider": "baostock_batch"} for item in batch_failures)
                except Exception as exc:
                    attempt_failures.append({"symbol": "__batch__", "provider": "baostock_batch", "error": f"{type(exc).__name__}: {exc}"})

        fetched_symbols = {
            _symbol_with_suffix(symbol)
            for frame in frames
            if "symbol" in frame.columns
            for symbol in frame["symbol"].dropna().astype(str).unique()
        }
        missing_symbols = [symbol for symbol in symbols if _symbol_with_suffix(symbol) not in fetched_symbols]
        if missing_symbols:
            for symbol in missing_symbols:
                try:
                    hist = fetch_symbol_daily(symbol, symbol_starts[symbol], fetch_end)
                    if not hist.empty:
                        frames.append(hist)
                except Exception as exc:
                    attempt_failures.append({"symbol": symbol, "provider": "symbol_fallback", "error": f"{type(exc).__name__}: {exc}"})

        final_fetched_symbols = {
            _symbol_with_suffix(symbol)
            for frame in frames
            if "symbol" in frame.columns
            for symbol in frame["symbol"].dropna().astype(str).unique()
        }
        still_missing = sorted(set(symbols) - final_fetched_symbols)
        failed_symbol_names = {
            _symbol_with_suffix(str(item["symbol"]))
            for item in attempt_failures
            if str(item.get("symbol", "")).split(".", 1)[0].isdigit()
        }
        existing_symbols = set(existing["symbol"].astype(str).map(_symbol_with_suffix)) if "symbol" in existing.columns else set()
        unresolved_symbols = sorted(
            symbol
            for symbol in still_missing
            if not effective_incremental or symbol not in existing_symbols or symbol in failed_symbol_names
        )
        recovered_failures = [
            item
            for item in attempt_failures
            if item.get("symbol") in {"__batch__", "__eastmoney_snapshot__"}
            or _symbol_with_suffix(str(item.get("symbol"))) not in unresolved_symbols
        ]
        unresolved_failures = [
            {
                "symbol": symbol,
                "errors": [item["error"] for item in attempt_failures if _symbol_with_suffix(str(item.get("symbol"))) == symbol]
                or ["empty response from all historical providers"],
            }
            for symbol in unresolved_symbols
        ]

        if not frames:
            raise RuntimeError(
                f"All daily providers failed or returned no rows; failures={unresolved_failures[:5] or attempt_failures[:5]}"
            )
        raw_row_count = int(sum(len(frame) for frame in frames))
        normalized = normalize_real_daily_frame(pd.concat(frames, ignore_index=True, sort=False), names)
        rejected_row_count = raw_row_count - int(len(normalized))
        if normalized.empty:
            raise RuntimeError("Daily providers returned rows but none passed schema validation")

        candidate = _merge_incremental_daily(existing, normalized) if effective_incremental else normalized
        retention_start = datetime.strptime(requested_start, "%Y%m%d").date().isoformat()
        candidate = (
            candidate[
                candidate["symbol"].isin(symbols)
                & candidate["trade_date"].astype(str).ge(retention_start)
            ]
            .sort_values(["symbol", "trade_date"])
            .reset_index(drop=True)
        )
        candidate_summary = _dataset_change_summary(existing, candidate)
        candidate_latest_trade_date = None if candidate.empty else str(candidate["trade_date"].max())
        candidate_latest_stock_count = 0
        if candidate_latest_trade_date:
            candidate_latest_stock_count = int(
                candidate[candidate["trade_date"].astype(str).eq(candidate_latest_trade_date)]["symbol"].nunique()
            )
        latest_coverage_ratio = candidate_latest_stock_count / max(len(symbols), 1)
        freshness_errors = _cross_provider_consistency_errors(existing, normalized) if effective_incremental else []
        if validate_freshness and expected_latest_trade_date and candidate_latest_trade_date != expected_latest_trade_date:
            freshness_errors.append(
                f"latest trade date {candidate_latest_trade_date} does not match expected {expected_latest_trade_date}"
            )
        if validate_freshness and expected_latest_trade_date and latest_coverage_ratio < MIN_LATEST_COVERAGE_RATIO:
            freshness_errors.append(
                f"latest-date coverage {latest_coverage_ratio:.2%} is below {MIN_LATEST_COVERAGE_RATIO:.0%}"
            )

        integrity_blocked = bool(unresolved_failures or freshness_errors)
        commit_allowed = not integrity_blocked and not smoke_mode
        write_performed = bool(commit_allowed and candidate_summary["data_changed"])
        if commit_allowed:
            _write_current_constituents(constituents, expected_latest_trade_date or candidate_latest_trade_date or requested_end)
        if write_performed:
            _write_daily_parquet(candidate)
        output = candidate if commit_allowed else existing.sort_values(["symbol", "trade_date"]).reset_index(drop=True)
        latest_trade_date = None if output.empty else str(output["trade_date"].max())
        latest_stock_count = 0 if not latest_trade_date else int(
            output[output["trade_date"].astype(str).eq(latest_trade_date)]["symbol"].nunique()
        )

        data_source_mode = "real_csi300_recent_3y_daily"
        if effective_incremental and not existing.empty:
            data_source_mode = "real_csi300_daily_incremental"
        if migration_required:
            data_source_mode = "real_csi300_daily_hfq_migration_full_refresh"
        status = "partial" if integrity_blocked else "ok" if smoke_mode or write_performed else "no_change"
        report = {
            "status": status,
            "data_source_mode": data_source_mode,
            "data_version": DATA_VERSION,
            "source_version": SOURCE_VERSION,
            "price_adjustment_mode": PRICE_ADJUSTMENT_MODE,
            "incremental_update": bool(effective_incremental and not existing.empty),
            "migration_required": migration_required,
            "overlap_days": int(overlap_days),
            "previous_row_count": int(len(existing)),
            "previous_latest_trade_date": previous_latest_trade_date,
            "snapshot_row_count": snapshot_row_count,
            "snapshot_path": _display_path(SNAPSHOT_PATH) if used_snapshot else None,
            "snapshot_caveat": "intraday snapshots are stored separately and never merged into adjusted official daily bars" if used_snapshot else None,
            "fetched_row_count": int(len(normalized)),
            "raw_fetched_row_count": raw_row_count,
            "rejected_row_count": rejected_row_count,
            "data_changed": bool(commit_allowed and candidate_summary["data_changed"]),
            "candidate_data_changed": bool(candidate_summary["data_changed"]),
            "new_row_count": int(candidate_summary["new_row_count"] if commit_allowed else 0),
            "revised_row_count": int(candidate_summary["revised_row_count"] if commit_allowed else 0),
            "deleted_row_count": int(candidate_summary["deleted_row_count"] if commit_allowed else 0),
            "candidate_new_row_count": int(candidate_summary["new_row_count"]),
            "candidate_revised_row_count": int(candidate_summary["revised_row_count"]),
            "candidate_deleted_row_count": int(candidate_summary["deleted_row_count"]),
            "write_performed": write_performed,
            "row_count": int(len(output)),
            "stock_count": int(output["symbol"].nunique()) if "symbol" in output.columns else 0,
            "latest_stock_count": latest_stock_count,
            "candidate_row_count": int(len(candidate)),
            "candidate_stock_count": int(candidate["symbol"].nunique()),
            "candidate_latest_stock_count": candidate_latest_stock_count,
            "latest_coverage_ratio": latest_coverage_ratio,
            "start_date": str(output["trade_date"].min()) if not output.empty else None,
            "end_date": latest_trade_date,
            "candidate_end_date": candidate_latest_trade_date,
            "expected_latest_trade_date": expected_latest_trade_date,
            "requested_start_date": requested_start,
            "requested_incremental_start_date": requested_incremental_start_date,
            "requested_end_date": requested_end,
            "fetch_end_date": fetch_end,
            "calendar_source": calendar_source,
            "universe_source": universe_source,
            "universe_warning": universe_warning,
            "target_stock_count": int(len(symbols)),
            "constituent_method": "current CSI300 constituents only; use the membership snapshot for present-day research and point-in-time membership for historical backtests",
            "unresolved_failures": unresolved_failures,
            "failed_symbols": unresolved_failures,
            "recovered_failures": recovered_failures,
            "empty_symbols": still_missing,
            "freshness_errors": freshness_errors,
            "smoke_mode": smoke_mode,
            "commit_blocked_reason": (
                "diagnostic --max-symbols run"
                if smoke_mode
                else "unresolved provider failures or freshness gate failure"
                if not commit_allowed
                else None
            ),
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
    _write_ingestion_report(report)
    return report


def write_real_csi300_daily(
    max_symbols: int | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    incremental: bool = True,
    overlap_days: int = 7,
    use_snapshot: bool = False,
    validate_freshness: bool = True,
) -> dict[str, Any]:
    try:
        with _exclusive_update_lock():
            return _write_real_csi300_daily_unlocked(
                max_symbols=max_symbols,
                start_date=start_date,
                end_date=end_date,
                incremental=incremental,
                overlap_days=overlap_days,
                use_snapshot=use_snapshot,
                validate_freshness=validate_freshness,
            )
    except Exception as exc:
        lock_conflict = "already running" in str(exc)
        report = {
            "status": "failed",
            "data_source_mode": "real_csi300_daily_update_locked" if lock_conflict else "real_csi300_daily_update_failed",
            "error": f"{type(exc).__name__}: {exc}",
            "research_boundary": RESEARCH_BOUNDARY,
            "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        }
        _write_ingestion_report(report)
        return report


if __name__ == "__main__":
    result = write_real_csi300_daily()
    print(json.dumps(result, ensure_ascii=False, indent=2, default=_json_default))
    raise SystemExit(0 if result.get("status") in {"ok", "no_change"} else 1)
