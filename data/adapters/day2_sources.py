from __future__ import annotations

from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Iterable

import yaml


@dataclass(frozen=True)
class SourceLicense:
    dataset_name: str
    source_name: str
    source_type: str
    priority: int
    license_status: str
    adapter_status: str
    display_policy: str
    export_policy: str
    sample_scope: str
    notes: str


DAY2_SOURCE_REGISTRY: list[SourceLicense] = [
    SourceLicense("trading_calendar", "synthetic_day2", "reference", 1, "authorized", "local_sample_ready", "display_allowed", "export_allowed", "synthetic_contract_sample", "交易日历：Day2 使用本地合成样例验证时间语义。"),
    SourceLicense("stock_list", "synthetic_day2", "reference", 1, "authorized", "local_sample_ready", "display_allowed", "export_allowed", "synthetic_contract_sample", "股票列表：本地小 universe，不代表真实股票池。"),
    SourceLicense("listing_status", "synthetic_day2", "reference", 1, "authorized", "local_sample_ready", "display_allowed", "export_allowed", "synthetic_contract_sample", "上市/退市状态样例。"),
    SourceLicense("st_status", "synthetic_day2", "reference", 1, "authorized", "local_sample_ready", "display_allowed", "export_allowed", "synthetic_contract_sample", "ST 状态样例。"),
    SourceLicense("suspension_status", "synthetic_day2", "reference", 1, "authorized", "local_sample_ready", "display_allowed", "export_allowed", "synthetic_contract_sample", "停牌状态样例。"),
    SourceLicense("limit_rules", "synthetic_day2", "reference", 1, "authorized", "local_sample_ready", "display_allowed", "export_allowed", "synthetic_contract_sample", "涨跌停规则样例。"),
    SourceLicense("market_daily_ohlcv", "synthetic_day2", "batch_market", 1, "authorized", "local_sample_ready", "display_allowed", "export_allowed", "synthetic_contract_sample", "日频 OHLCV：Day2 稳定离线样例。"),
    SourceLicense("adjustment_factor", "synthetic_day2", "batch_market", 1, "authorized", "local_sample_ready", "display_allowed", "export_allowed", "synthetic_contract_sample", "复权因子样例。"),
    SourceLicense("industry_classification_history", "synthetic_day2", "reference", 1, "authorized", "local_sample_ready", "display_allowed", "export_allowed", "synthetic_contract_sample", "行业历史分类样例，带 as_of_date。"),
    SourceLicense("index_constituent_history", "synthetic_day2", "reference", 1, "authorized", "local_sample_ready", "display_allowed", "export_allowed", "synthetic_contract_sample", "指数历史成分样例，避免未来成分泄漏。"),
    SourceLicense("concept_classification", "synthetic_day2", "reference", 1, "authorized", "local_sample_ready", "display_allowed", "export_allowed", "synthetic_contract_sample", "基础概念分类样例。"),
    SourceLicense("financial_statement_basic", "synthetic_day2", "fundamental", 1, "authorized", "local_sample_ready", "display_allowed", "export_allowed", "synthetic_contract_sample", "基础财务字段样例，带 announce_time。"),
    SourceLicense("market_minute_rt", "external_vendor", "realtime_market", 2, "restricted", "adapter_contract_ready", "aggregate_only", "export_blocked", "schema_only_placeholder", "分钟实时行情需要供应商授权；Day2 仅保留 schema/adapter。"),
    SourceLicense("market_tick_rt", "external_vendor", "realtime_market", 2, "restricted", "adapter_contract_ready", "aggregate_only", "export_blocked", "schema_only_placeholder", "tick/逐笔实时数据受限，不伪造授权。"),
    SourceLicense("orderbook_rt", "external_vendor", "realtime_market", 2, "restricted", "adapter_contract_ready", "aggregate_only", "export_blocked", "schema_only_placeholder", "盘口快照受限，仅 schema placeholder。"),
    SourceLicense("trade_rt", "external_vendor", "realtime_market", 2, "restricted", "adapter_contract_ready", "aggregate_only", "export_blocked", "schema_only_placeholder", "逐笔成交受限，仅 schema placeholder。"),
    SourceLicense("announcement_event", "exchange_or_vendor", "event", 2, "restricted", "adapter_contract_ready", "citation_required", "export_blocked", "schema_only_placeholder", "公告原文/摘要依赖授权；Day2 只保存事件契约。"),
    SourceLicense("news_event", "news_vendor", "event", 2, "restricted", "adapter_contract_ready", "citation_required", "export_blocked", "schema_only_placeholder", "新闻正文受版权限制；Day2 只保留哈希/标题样例。"),
    SourceLicense("macro_event", "public_or_vendor", "macro", 3, "adapter_pending", "adapter_pending", "metadata_only", "export_blocked", "schema_only_placeholder", "宏观事件源待选型。"),
    SourceLicense("fund_flow", "vendor", "flow", 3, "adapter_pending", "adapter_pending", "metadata_only", "export_blocked", "schema_only_placeholder", "资金流字段待授权/映射。"),
    SourceLicense("northbound_flow", "exchange_or_vendor", "flow", 3, "not_authorized", "adapter_contract_ready", "no_display", "export_blocked", "schema_only_placeholder", "北向资金明细未授权，必须显示 not_authorized。"),
]


def registry_as_dicts() -> list[dict[str, object]]:
    return [asdict(item) for item in DAY2_SOURCE_REGISTRY]


def write_registry(root: Path) -> Path:
    path = root / "configs" / "data" / "source_license_registry.yaml"
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": "v0.2.0-day2",
        "registry_name": "day2_source_license_registry",
        "research_boundary": "research_signals_only_not_investment_advice",
        "sources": registry_as_dicts(),
    }
    path.write_text(yaml.safe_dump(payload, allow_unicode=True, sort_keys=False), encoding="utf-8")
    return path


def status_counts(sources: Iterable[dict[str, object]] | None = None) -> dict[str, int]:
    rows = list(sources) if sources is not None else registry_as_dicts()
    counts: dict[str, int] = {}
    for row in rows:
        status = str(row["license_status"])
        counts[status] = counts.get(status, 0) + 1
    counts["restricted_or_blocked"] = sum(counts.get(key, 0) for key in ("restricted", "not_authorized", "adapter_pending"))
    return counts


if __name__ == "__main__":
    print(write_registry(Path(__file__).resolve().parents[2]))
