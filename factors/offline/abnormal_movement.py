"""Daily research flags using the project's user-defined abnormal-move rules."""
from __future__ import annotations

import numpy as np
import pandas as pd

RETURN_FLAG = "return_10d_gt_100pct"
MOVEMENT_FLAG = "abnormal_move_4_times_10d"
FLAG_NAMES = [RETURN_FLAG, MOVEMENT_FLAG]
FLAG_LABELS = {
    RETURN_FLAG: "十日涨幅大于100%",
    MOVEMENT_FLAG: "十日内至少四次异动",
}
BENCHMARK_BY_EXCHANGE = {"SH": "000001.SH", "SZ": "399001.SZ"}


def compute_abnormal_movement_factors(
    daily: pd.DataFrame, benchmark_daily: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Return 0/1/NaN flags aligned with daily's original index.

    Returns compound over 1–3 sessions, subtract the matching index's compound
    return, and trigger strictly above 20 percentage points. After a trigger,
    its close is the earliest possible base for the next event. Count event
    end dates in [t-9, t]. Missing prices restart observation; ten complete
    return observations are required before either flag is known. No forward
    fill, cross-sectional market proxy, or future prices are used.
    """
    if benchmark_daily is None:
        from data.adapters.benchmark_daily import read_benchmark_daily

        benchmark_daily = read_benchmark_daily()
    result = pd.DataFrame(np.nan, index=daily.index, columns=FLAG_NAMES)
    if daily.empty:
        return result
    frame = daily[[column for column in ("symbol", "trade_date", "close", "available_time", "prediction_time") if column in daily]].copy()
    frame["trade_date"] = pd.to_datetime(frame["trade_date"]).dt.normalize()
    # Parse repeated timestamps once for the whole panel, rather than four
    # times per stock. Keep UTC comparisons and missing-time semantics intact.
    for column in ("available_time", "prediction_time"):
        if column in frame:
            frame[column] = pd.to_datetime(frame[column], utc=True, errors="coerce")
    if frame.duplicated(["symbol", "trade_date"]).any():
        raise ValueError("Daily factor input contains duplicate symbol/trade_date rows")
    frame["_position"] = np.arange(len(frame))
    benchmarks = benchmark_daily.copy()
    if not benchmarks.empty:
        benchmarks["trade_date"] = pd.to_datetime(benchmarks["trade_date"]).dt.normalize()
        if benchmarks.duplicated(["index_symbol", "trade_date"]).any():
            raise ValueError("Benchmark input contains duplicate index_symbol/trade_date rows")
        benchmarks["close"] = pd.to_numeric(benchmarks["close"], errors="coerce")
        if "available_time" in benchmarks:
            benchmarks["available_time"] = pd.to_datetime(benchmarks["available_time"], utc=True, errors="coerce")
    benchmark_groups = {symbol: rows.set_index("trade_date") for symbol, rows in benchmarks.groupby("index_symbol")} if not benchmarks.empty else {}
    calendar = pd.DatetimeIndex(frame["trade_date"].unique()).sort_values()
    if not benchmarks.empty:
        calendar = calendar.union(pd.DatetimeIndex(benchmarks["trade_date"].unique())).sort_values()

    for symbol, rows in frame.groupby("symbol", sort=False):
        rows = rows.sort_values("trade_date")
        dates = calendar[(calendar >= rows.trade_date.min()) & (calendar <= rows.trade_date.max())]
        group = rows.set_index("trade_date").reindex(dates)
        close = pd.to_numeric(group["close"], errors="coerce")
        close = close.where(np.isfinite(close) & close.gt(0))
        valid_prices = close.rolling(11, min_periods=11).count().eq(11)
        return_flag = ((close / close.shift(10) - 1) > 1.0 + 1e-12).astype(float).where(valid_prices)
        flags = pd.DataFrame({RETURN_FLAG: return_flag, MOVEMENT_FLAG: np.nan}, index=dates)

        benchmark_symbol = BENCHMARK_BY_EXCHANGE.get(str(symbol).upper().rsplit(".", 1)[-1])
        index_rows = benchmark_groups.get(benchmark_symbol, pd.DataFrame())
        if not index_rows.empty:
            index_rows = index_rows.reindex(dates)
            index_close = index_rows["close"].copy()
            # Never claim the factor was available before its benchmark input.
            if "available_time" in index_rows:
                available = index_rows["available_time"]
                cutoff_column = "available_time" if "available_time" in group else "prediction_time"
                if cutoff_column in group:
                    cutoff = group[cutoff_column]
                    index_close = index_close.where(available.le(cutoff))
            if "prediction_time" in group and "available_time" in group:
                stock_available = group["available_time"]
                prediction = group["prediction_time"]
                index_close = index_close.where(stock_available.le(prediction))
            prices = close.to_numpy(dtype=float)
            index_prices = index_close.to_numpy(dtype=float)
            events = np.zeros(len(group), dtype=int)
            movement_flag = np.full(len(group), np.nan)
            segment_start = 0
            last_event = 0
            for i in range(len(group)):
                if not (np.isfinite(prices[i]) and np.isfinite(index_prices[i]) and index_prices[i] > 0):
                    segment_start = last_event = i + 1
                    continue
                first_base = max(segment_start, last_event, i - 3)
                for base in range(first_base, i):
                    excess = prices[i] / prices[base] - index_prices[i] / index_prices[base]
                    if excess > 0.20 + 1e-12:
                        events[i] = 1
                        last_event = i
                        break
                if i - segment_start >= 10:
                    movement_flag[i] = float(events[i - 9:i + 1].sum() >= 4)
            flags[MOVEMENT_FLAG] = movement_flag
        result.iloc[rows["_position"].to_numpy()] = flags.loc[rows["trade_date"], FLAG_NAMES].to_numpy()
    return result
