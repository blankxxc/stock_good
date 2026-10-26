"""Deterministic daily strategy experiments: prior-close signals, next-open fills."""
from __future__ import annotations

import hashlib
import json
import math
from datetime import date, datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Literal

import numpy as np
import pandas as pd
from pydantic import BaseModel, ConfigDict, Field

ROOT = Path(__file__).resolve().parents[3]
MARKET_PATH = ROOT / "data/real/csi300_daily/part-000.parquet"
ENGINE_VERSION = "daily-strategy-lab-v2"
STRATEGIES = [
    {"id": "momentum", "label": "动量策略", "description": "按过去 N 个交易日涨幅从高到低选股。"},
    {"id": "reversal", "label": "反转策略", "description": "按过去 N 个交易日涨幅从低到高选股。"},
    {"id": "low_volatility", "label": "低波动策略", "description": "优先选择过去 N 个交易日收益波动较小的股票。"},
    {"id": "trend", "label": "均线趋势策略", "description": "收盘价高于 N 日均线时，按 N 日涨幅从高到低选股。"},
]
ASSUMPTIONS = [
    "使用前一交易日收盘及此前的数据选股，在下一交易日开盘调仓，当日收盘估值。",
    "等权、只做多；每隔指定交易日调仓。无合格股票时持有现金，现金利息为零。期末持仓按收盘价估值，不强制卖出。",
    "手续费与滑点按每笔买卖成交金额分别扣除；此处为统一成本假设，不另行计算最低佣金和印花税。",
    "按复权价格模拟比例持仓，允许碎股；暂停或缺失行情不成交，已有持仓按最近收盘价估值。未还原整手、涨跌停排队和市场冲击。",
    "股票池为当前本地沪深300成员的历史行情，存在幸存者偏差；历史 ST 等标记受数据源覆盖限制。",
    "勾选剔除 ST 时，仅纳入信号日明确为非 ST 的股票；ST、缺少历史状态或状态无效的股票均排除。取消勾选则不按 ST 状态过滤。",
    "等权基准使用相同日期、过滤条件、调仓周期及成本。不同策略的参数比较不等同于样本外验证。",
]


class ExperimentRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    start_date: date
    end_date: date
    strategies: list[Literal["momentum", "reversal", "low_volatility", "trend"]] = Field(min_length=1, max_length=4)
    lookback: int = Field(default=20, ge=2, le=120)
    top_k: int = Field(default=10, ge=1, le=50)
    rebalance_days: int = Field(default=5, ge=1, le=60)
    initial_capital: float = Field(default=100000, ge=1000, le=100000000, allow_inf_nan=False)
    fee_bps: float = Field(default=3, ge=0, le=100, allow_inf_nan=False)
    slippage_bps: float = Field(default=5, ge=0, le=100, allow_inf_nan=False)
    exclude_st: bool = True
    exclude_extreme: bool = False
    exclude_abnormal: bool = False


@lru_cache(maxsize=1)
def _market_snapshot(path: str, modified: int, size: int) -> tuple[pd.DataFrame, str]:
    # Cache by file generation; the content hash identifies exported experiments.
    data = Path(path).read_bytes()
    import io

    return pd.read_parquet(io.BytesIO(data)), hashlib.sha256(data).hexdigest()


def load_market() -> tuple[pd.DataFrame, str]:
    if not MARKET_PATH.is_file():
        raise FileNotFoundError("尚无本地日频行情，请先完成日频数据更新。")
    stat = MARKET_PATH.stat()
    return _market_snapshot(str(MARKET_PATH), stat.st_mtime_ns, stat.st_size)


def _st_flags(frame: pd.DataFrame) -> pd.Series:
    """Preserve unknown ST status, including an absent source column."""
    if "st_flag" not in frame:
        return pd.Series(pd.NA, index=frame.index, dtype="boolean")
    values = pd.to_numeric(frame["st_flag"], errors="coerce")
    return values.where(values.isin([0, 1])).astype("boolean")


def _st_coverage(status: pd.Series, scope: str) -> dict:
    count = len(status)
    known = int(status.notna().sum())
    return {
        "scope": scope, "observation_count": count,
        "known_st_count": int(status.eq(True).sum()),
        "known_non_st_count": int(status.eq(False).sum()),
        "unknown_count": count - known,
        "known_fraction": known / count if count else None,
    }


def lab_metadata() -> dict:
    frame, fingerprint = load_market()
    dates = sorted(pd.to_datetime(frame["trade_date"]).dt.strftime("%Y-%m-%d").unique())
    if len(dates) < 3:
        raise ValueError("至少需要三个交易日的行情。")
    return {
        "status": "ready", "strategies": STRATEGIES, "assumptions": ASSUMPTIONS,
        "market_start": dates[0], "market_end": dates[-1], "trading_days": len(dates),
        "stock_count": int(frame["symbol"].nunique()), "data_fingerprint": fingerprint,
        "engine_version": ENGINE_VERSION,
        "st_coverage": _st_coverage(_st_flags(frame), "available_history_rows"),
        "default_start": dates[max(21, len(dates) - 120)] if len(dates) > 21 else dates[2],
        "default_end": dates[-1],
    }


def _metrics(curve: list[dict], capital: float) -> dict:
    nav = np.array([point["nav"] for point in curve])
    returns = np.diff(np.r_[1.0, nav]) / np.r_[1.0, nav[:-1]]
    volatility = float(returns.std(ddof=1)) if len(returns) > 1 else 0.0
    annual_log = math.log(nav[-1]) * 252 / len(nav)
    return {
        "total_return": float(nav[-1] - 1),
        "annualized_return": math.expm1(annual_log) if annual_log < 700 else None,
        "max_drawdown": min(point["drawdown"] for point in curve),
        "sharpe": float(returns.mean() / volatility * math.sqrt(252)) if volatility > 1e-12 else None,
        "win_rate": float((returns > 0).mean()),
        "average_turnover": float(np.mean([point["turnover"] for point in curve])),
        "total_cost": sum(point["cost"] for point in curve),
        "final_equity": float(nav[-1] * capital),
        "trade_count": sum(point["trade_count"] for point in curve),
        "blocked_orders": sum(point["blocked_orders"] for point in curve),
    }


def run_experiment(request: ExperimentRequest, market: pd.DataFrame | None = None,
                   fingerprint: str | None = None, benchmark_daily: pd.DataFrame | None = None) -> dict:
    if request.start_date > request.end_date:
        raise ValueError("开始日期不能晚于结束日期。")
    if len(set(request.strategies)) != len(request.strategies):
        raise ValueError("同一次实验不能重复选择策略。")
    if market is None:
        market, fingerprint = load_market()
    frame = market.copy()
    frame["trade_date"] = pd.to_datetime(frame["trade_date"]).dt.normalize()
    if frame.duplicated(["symbol", "trade_date"]).any():
        raise ValueError("日频行情存在重复记录，请先检查数据。")
    first, last = frame.trade_date.min().date(), frame.trade_date.max().date()
    if request.start_date < first or request.end_date > last:
        raise ValueError(f"日期须在本地数据范围 {first} 至 {last} 内。")
    # Truncate before computing any signal, including the two abnormal-move flags.
    frame = frame[frame.trade_date.le(pd.Timestamp(request.end_date))].sort_values(["trade_date", "symbol"])
    frame["st_flag"] = _st_flags(frame)
    symbols = sorted(frame.symbol.unique())
    calendar = pd.DatetimeIndex(frame.trade_date.unique()).sort_values()
    dates = np.flatnonzero(calendar >= pd.Timestamp(request.start_date))
    if len(dates) < 2:
        raise ValueError("所选区间至少需要两个交易日。")
    if dates[0] <= request.lookback:
        raise ValueError(f"开始日期之前至少需要 {request.lookback + 1} 个交易日作为观察期，请延后开始日期或缩短观察期。")
    if len(dates) > 800:
        raise ValueError("单次实验最多支持 800 个交易日。")

    def pivot(name: str, default: float = np.nan) -> pd.DataFrame:
        if name not in frame:
            return pd.DataFrame(default, index=calendar, columns=symbols)
        return frame.pivot(index="trade_date", columns="symbol", values=name).reindex(index=calendar, columns=symbols)

    def flag(name: str, default: bool, missing: bool) -> pd.DataFrame:
        return pivot(name, default).astype("boolean").fillna(missing).astype(bool)

    close = pivot("close").astype(float)
    close = close.where(np.isfinite(close) & close.gt(0))
    opens = pivot("open").astype(float)
    valid_open = np.isfinite(opens) & opens.gt(0)
    volume_ok = pivot("volume").fillna(0).gt(0)
    tradeable = valid_open & close.notna() & volume_ok & flag("tradable_flag", True, False)
    buyable = (tradeable & flag("can_buy", True, False)).to_numpy()
    sellable = (tradeable & flag("can_sell", True, False)).to_numpy()
    eligible = close.rolling(request.lookback + 1).count().eq(request.lookback + 1)
    eligible &= ~flag("delist_flag", False, True)
    st_status = pivot("st_flag").astype("boolean")
    signal_st_status = st_status.iloc[dates[::request.rebalance_days] - 1]
    st_coverage = _st_coverage(
        pd.Series(signal_st_status.to_numpy().reshape(-1), dtype="boolean"),
        "rebalance_signal_stock_days",
    )
    st_coverage["exclude_unknown"] = request.exclude_st
    if request.exclude_st:
        eligible &= st_status.eq(False).fillna(False)
    factor_fingerprint = None
    if request.exclude_extreme or request.exclude_abnormal:
        from factors.offline.abnormal_movement import FLAG_NAMES, compute_abnormal_movement_factors

        if benchmark_daily is None:
            from data.adapters.benchmark_daily import BENCHMARK_PATH

            if BENCHMARK_PATH.exists():
                import io

                index_bytes = BENCHMARK_PATH.read_bytes()
                benchmark_daily = pd.read_parquet(io.BytesIO(index_bytes))
                factor_fingerprint = hashlib.sha256(index_bytes).hexdigest()
            else:
                benchmark_daily = pd.DataFrame()
        frame[FLAG_NAMES] = compute_abnormal_movement_factors(frame, benchmark_daily)
        for enabled, name in zip((request.exclude_extreme, request.exclude_abnormal), FLAG_NAMES):
            if enabled:
                # Unknown is excluded, not silently treated as "no abnormal move".
                eligible &= pivot(name).eq(0)
    momentum = close / close.shift(request.lookback) - 1
    scores = {
        "momentum": momentum,
        "reversal": -momentum,
        "low_volatility": -close.pct_change(fill_method=None).rolling(request.lookback).std(),
        "trend": momentum.where(close.gt(close.rolling(request.lookback).mean())),
        "equal_weight": pd.DataFrame(1.0, index=calendar, columns=symbols),
    }
    marks = close.ffill()
    open_marks = opens.where(valid_open, marks.shift()).fillna(0).to_numpy(dtype=float)
    close_marks = marks.fillna(0).to_numpy(dtype=float)
    names = frame.drop_duplicates("symbol", keep="last").set_index("symbol").get("stock_name", pd.Series(dtype=str)).to_dict()
    capital = request.initial_capital
    cost_rate = (request.fee_bps + request.slippage_bps) / 10000

    def simulate(strategy: str, details: bool = True) -> dict:
        score = scores[strategy].where(eligible).to_numpy(dtype=float)
        units = np.zeros(len(symbols))
        cash, previous_equity, peak = capital, capital, capital
        curve = []
        for offset, i in enumerate(dates):
            current_open = open_marks[i]
            opening_equity = cash + float(units @ current_open)
            orders, cost, turnover_value, blocked, trade_count = [], 0.0, 0.0, 0, 0
            rebalance = offset % request.rebalance_days == 0
            if rebalance:
                valid = np.flatnonzero(np.isfinite(score[i - 1]))
                ranked = valid[np.argsort(-score[i - 1, valid], kind="stable")]
                selected = ranked if strategy == "equal_weight" else ranked[:request.top_k]
                target = np.zeros(len(symbols))
                if len(selected):
                    target[selected] = opening_equity / len(selected)
                before = units * current_open
                sells = np.maximum(before - target, 0)
                buys = np.maximum(target - before, 0)

                def record(j: int, side: str, notional: float, fee: float, status: str) -> None:
                    if details:
                        orders.append({"symbol": symbols[j], "stock_name": names.get(symbols[j], symbols[j]),
                                       "side": side, "notional": round(notional, 4), "cost": round(fee, 4), "status": status})

                for j in np.flatnonzero(sells > 1e-7):
                    if not sellable[i, j]:
                        blocked += 1
                        record(j, "sell", 0.0, 0.0, "行情不可交易")
                        continue
                    value = float(sells[j])
                    fee = value * cost_rate
                    units[j] = max(0, units[j] - value / current_open[j])
                    cash += value - fee
                    cost += fee
                    turnover_value += value
                    trade_count += 1
                    record(j, "sell", value, fee, "已成交")
                for j in np.flatnonzero((buys > 1e-7) & ~buyable[i]):
                    blocked += 1
                    record(j, "buy", 0.0, 0.0, "行情不可交易")
                buys = np.where(buyable[i], buys, 0)
                required_cash = float(buys.sum()) * (1 + cost_rate)
                scale = min(1.0, max(0.0, cash) / required_cash) if required_cash else 0.0
                for j in np.flatnonzero(buys * scale > 1e-7):
                    value = float(buys[j] * scale)
                    fee = value * cost_rate
                    units[j] += value / current_open[j]
                    cash -= value + fee
                    cost += fee
                    turnover_value += value
                    trade_count += 1
                    record(j, "buy", value, fee, "已成交")
                cash = max(0.0, cash)
            values = units * close_marks[i]
            equity = cash + float(values.sum())
            peak = max(peak, equity)
            point = {
                "trade_date": calendar[i].strftime("%Y-%m-%d"), "signal_date": calendar[i - 1].strftime("%Y-%m-%d") if rebalance else None,
                "nav": equity / capital, "equity": equity, "daily_return": equity / previous_equity - 1,
                "drawdown": equity / peak - 1, "cash": cash, "cost": cost,
                "turnover": turnover_value / opening_equity, "rebalance": rebalance,
                "trade_count": trade_count, "blocked_orders": blocked,
                "holding_count": int((values > 1e-7).sum()),
            }
            if details:
                point["orders"] = orders
                point["holdings"] = [{"symbol": symbols[j], "stock_name": names.get(symbols[j], symbols[j]),
                                       "weight": float(values[j] / equity), "market_value": float(values[j])}
                                      for j in np.flatnonzero(values > 1e-7)]
            curve.append(point)
            previous_equity = equity
        return {"id": strategy, "label": next((s["label"] for s in STRATEGIES if s["id"] == strategy), "股票池等权"),
                "metrics": _metrics(curve, capital), "curve": curve}

    baseline = simulate("equal_weight", details=False)
    results = [simulate(strategy) for strategy in request.strategies]
    for result in results:
        result["metrics"]["excess_return"] = result["metrics"]["total_return"] - baseline["metrics"]["total_return"]
    config = request.model_dump(mode="json")
    identity = json.dumps([ENGINE_VERSION, fingerprint, factor_fingerprint, config], sort_keys=True)
    return {
        "status": "ok", "experiment_id": hashlib.sha256(identity.encode()).hexdigest()[:16],
        "engine_version": ENGINE_VERSION, "created_at": datetime.now(timezone.utc).isoformat(),
        "config": config, "data_fingerprint": fingerprint, "benchmark_fingerprint": factor_fingerprint,
        "actual_start": calendar[dates[0]].strftime("%Y-%m-%d"), "actual_end": calendar[dates[-1]].strftime("%Y-%m-%d"),
        "trading_days": len(dates), "stock_count": len(symbols), "assumptions": ASSUMPTIONS,
        "st_coverage": st_coverage,
        "results": results, "baseline": baseline,
    }
