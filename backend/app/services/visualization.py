"""Small, aligned daily projections for the visualization workbench."""
from __future__ import annotations

import hashlib
import math
from datetime import date, datetime
from pathlib import Path

import polars as pl
import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from backend.app.services.file_payload_cache import file_payload_cache

ROOT = Path(__file__).resolve().parents[3]
MARKET = ROOT / "data/real/csi300_daily/part-000.parquet"
FACTORS = ROOT / "data/gold/model_feature_matrix_wide/part-000.parquet"
SPEC = ROOT / "configs/factor/factor_spec.yaml"
PRICE_METRICS = {
    "raw_close": ("收盘价 · 未复权", "元"),
    "close": ("收盘价 · 研究复权口径", "复权价格"),
    "volume": ("成交量", "股"),
    "amount": ("成交额", "元"),
    "turnover_rate": ("换手率", "%"),
}
FACTOR_LABELS = {
    "return_1d": "1 日收益率", "return_5d": "5 日收益率", "return_10d": "10 日收益率",
    "return_20d": "20 日收益率", "momentum_20d": "20 日动量", "volatility_20d": "20 日波动率",
    "vwap_deviation": "成交均价偏离", "return_10d_gt_100pct": "十日涨幅超过 100%",
    "abnormal_move_4_times_10d": "十日内四次异动",
}


def _inputs():
    return [MARKET, FACTORS, SPEC]


def _scan(path: Path) -> pl.LazyFrame:
    return pl.scan_parquet(path).with_columns(pl.col("trade_date").cast(pl.String).str.slice(0, 10))


def _version() -> str:
    parts = [(p.name, p.stat().st_mtime_ns, p.stat().st_size) for p in _inputs() if p.is_file()]
    return hashlib.sha256(repr(parts).encode()).hexdigest()[:16]


class SeriesRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    symbols: list[str] = Field(min_length=1, max_length=4)
    metrics: list[str] = Field(min_length=1, max_length=12)
    start_date: date
    end_date: date

    @field_validator("symbols", "metrics")
    @classmethod
    def unique_items(cls, values):
        if any(len(value) > 100 for value in values):
            raise ValueError("股票或指标名称过长。")
        return sorted(set(values))

    @model_validator(mode="after")
    def bounded_dates(self):
        if self.start_date > self.end_date:
            raise ValueError("开始日期不能晚于结束日期。")
        if (self.end_date - self.start_date).days > 1830:
            raise ValueError("一次最多查看五年日频数据。")
        return self


@file_payload_cache(_inputs, maxsize=1)
def visualization_metadata() -> dict:
    if not MARKET.is_file():
        raise FileNotFoundError("暂无本地日频行情，请先更新数据。")
    version = _version()
    market = _scan(MARKET)
    schema = market.collect_schema()
    dates = market.select("trade_date").unique().sort("trade_date").collect()["trade_date"].to_list()
    if not dates:
        raise ValueError("本地日频行情为空。")
    stocks = market.select("symbol", "stock_name", "trade_date").sort("trade_date").group_by("symbol").agg(
        pl.col("stock_name").last()
    ).sort("symbol").collect().to_dicts()
    modes = market.select("adjustment_mode").unique().collect()["adjustment_mode"].drop_nulls().to_list() if "adjustment_mode" in schema else []
    basis = {"hfq": "后复权研究价格", "qfq": "前复权研究价格", "none": "未复权价格"}.get(modes[0], "研究价格（口径未标注）") if len(modes) == 1 else "研究价格（混合或未知口径）"
    metrics = [{"id": key, "label": label, "unit": unit, "group": "行情", "description": ""}
               for key, (label, unit) in PRICE_METRICS.items() if key in schema]
    for item in metrics:
        if item["id"] == "close":
            item["label"] = f"收盘价 · {basis}"
            item["description"] = "用于历史研究；复权价格不代表当日实际成交价格。"
    factor_end = None
    if FACTORS.is_file() and SPEC.is_file():
        specs = yaml.safe_load(SPEC.read_text(encoding="utf-8")) or {}
        factor_schema = pl.read_parquet_schema(FACTORS)
        factor_end = _scan(FACTORS).select(pl.col("trade_date").max()).collect().item()
        for name, spec in (specs.get("factors") or {}).items():
            if name not in factor_schema or name in PRICE_METRICS:
                continue
            label = spec.get("display_name") or FACTOR_LABELS.get(name, name)
            metrics.append({"id": name, "label": label, "unit": "因子原值", "group": "因子",
                            "description": str(spec.get("formula", ""))})
    if version != _version():
        raise ValueError("数据正在更新，请稍后重新加载图表。")
    return {"stocks": stocks, "metrics": metrics, "market_start": dates[0], "market_end": dates[-1],
            "default_start": dates[max(0, len(dates) - 120)], "factor_end": factor_end,
            "price_basis": basis, "data_version": version,
            "notes": ["日频数据；因子使用原始数值，收益率类 0.01 表示 1%。",
                      "缺失数据留空，不前向填充；未复权价格可能受除权除息影响。",
                      "带可用时间的因子仅展示在对应预测时点已经可用的观测；晚到或时间缺失的值留空。",
                      "股票池为当前本地成员，历史对比存在幸存者偏差。"]}


def _assert_unique(frame: pl.DataFrame):
    if frame.select("symbol", "trade_date").is_duplicated().any():
        raise ValueError("所选历史数据存在重复的股票日期，请先修复数据。")


def _finite(value):
    return float(value) if value is not None and math.isfinite(value) else None


def _factor_available(row: dict) -> bool:
    try:
        available = row["available_time"]
        cutoff = row["prediction_time"]
        available = available if isinstance(available, datetime) else datetime.fromisoformat(available)
        cutoff = cutoff if isinstance(cutoff, datetime) else datetime.fromisoformat(cutoff)
        return available.tzinfo is not None and cutoff.tzinfo is not None and available <= cutoff
    except (KeyError, TypeError, ValueError):
        return False


def query_series(request: SeriesRequest) -> dict:
    return _series(tuple(request.symbols), tuple(request.metrics), request.start_date.isoformat(), request.end_date.isoformat())


@file_payload_cache(_inputs, maxsize=12)
def _series(symbols: tuple[str, ...], metrics: tuple[str, ...], start: str, end: str) -> dict:
    meta = visualization_metadata()
    catalog = {item["id"]: item for item in meta["metrics"]}
    names = {item["symbol"]: item["stock_name"] for item in meta["stocks"]}
    if set(symbols) - names.keys() or set(metrics) - catalog.keys():
        raise ValueError("请选择本地股票池和指标列表中的项目。")
    version = _version()
    dates = _scan(MARKET).filter(pl.col("trade_date").is_between(pl.lit(start), pl.lit(end))).select("trade_date").unique().sort("trade_date").collect()["trade_date"].to_list()
    if len(dates) > 1260:
        raise ValueError("所选区间超过 1260 个交易日，请缩短区间。")
    lookup: dict[tuple, dict] = {}
    for path, selected in [(MARKET, [m for m in metrics if m in PRICE_METRICS]),
                           (FACTORS, [m for m in metrics if m not in PRICE_METRICS])]:
        if not selected:
            continue
        source = _scan(path)
        timing = [name for name in ("available_time", "prediction_time") if path == FACTORS and name in source.collect_schema()]
        frame = source.filter(pl.col("symbol").is_in(symbols) & pl.col("trade_date").is_between(pl.lit(start), pl.lit(end))).select("symbol", "trade_date", *selected, *timing).collect()
        _assert_unique(frame)
        for row in frame.iter_rows(named=True):
            available = not timing or _factor_available(row)
            lookup.setdefault((row["symbol"], row["trade_date"]), {}).update({key: _finite(row[key]) if available else None for key in selected})
    series = []
    for symbol in symbols:
        for metric in metrics:
            values = [lookup.get((symbol, day), {}).get(metric) for day in dates]
            series.append({"symbol": symbol, "stock_name": names[symbol], "metric": metric, "values": values,
                           "observations": sum(v is not None for v in values)})
    if version != _version() or version != meta["data_version"]:
        raise ValueError("数据正在更新，请稍后重新加载图表。")
    return {"dates": dates, "series": series, "metrics": [catalog[m] for m in metrics],
            "start_date": start, "end_date": end, "data_version": version,
            "market_end": meta["market_end"], "factor_end": meta["factor_end"],
            "price_basis": meta["price_basis"], "notes": meta["notes"]}
