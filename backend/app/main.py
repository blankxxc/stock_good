from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.app.services.day2_catalog import data_quality_payload, lakehouse_payload, license_payload, lineage_payload

SERVICE_NAME = "stock-research-platform"
RESEARCH_BOUNDARY = "research_signals_only_not_investment_advice"

app = FastAPI(
    title="Intelligent Stock Research Platform",
    version="0.1.0-day3",
    description=(
        "Research console for cross-sectional ranking, factor diagnostics, "
        "backtest reports, risk explanation, and RAG-cited research notes. "
        "It does not provide deterministic trading instructions."
    ),
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict[str, Any]:
    return {
        "status": "ok",
        "service": SERVICE_NAME,
        "version": "0.1.0-day3",
        "time": datetime.now(timezone.utc).isoformat(),
        "research_boundary": RESEARCH_BOUNDARY,
        "modules": {
            "backend": "stub_ready",
            "frontend": "route_stubs_ready",
            "lakehouse": "day2_parquet_duckdb_snapshot_ready",
            "data_quality": "day3_quality_quarantine_leakage_ready",
            "lineage": "day3_source_job_snapshot_report_ready",
            "spark": "day2_bronze_to_silver_smoke_ready",
            "flink": "job_graph_stub_ready",
            "redpanda_kafka": "topic_contract_ready",
            "clickhouse": "day2_ads_loader_ready",
            "rag": "claim_schema_ready",
            "audit": "metadata_table_ready",
        },
    }


ROUTE_MODULES = {
    "auth": "认证、RBAC 与 action-level permission 占位",
    "overview": "研究平台总览、数据 cutoff、模型版本和质量状态",
    "data-quality": "数据质量、缺失、异常、quarantine 与延迟摘要",
    "lineage": "ODS/DWD/DWS/ADS、Spark/Flink job 到结果快照的血缘",
    "lakehouse": "Bronze/Silver/Gold/ADS 与 Iceberg/Hudi/Delta PoC 状态",
    "spark-jobs": "Spark 离线 ETL、批量因子、标签和训练样本 job 状态",
    "realtime": "Kafka topic、实时数据延迟、在线特征和实时评分状态",
    "flink-jobs": "Flink event-time、watermark、window、late-data job 状态",
    "factors": "离线/实时/事件/市场环境/关系因子库",
    "features": "Feature Store、feature view、point-in-time join 和 materialization job",
    "graph": "行业/概念/供应链/共现/价格相关关系图",
    "models": "Qlib、LightGBM、MASTER、StockMixer、HIST、TRSR 适配器",
    "experiments": "MLflow/Qlib Recorder 实验记录",
    "backtests": "TopK、long-short、risk/cost/capacity 回测报告",
    "rag": "claim 级证据、as-of 检索、引用和评测",
    "reports": "报告状态机、license gate、export_manifest 与 file_hash",
    "simulation": "模拟账户、模拟订单、模拟持仓和风控约束",
    "admin": "用户、角色、权限、系统配置管理",
    "audit": "审计日志和治理事件查询",
    "licenses": "数据许可证、可展示范围和 license_gate",
}


def route_payload(module: str) -> dict[str, Any]:
    if module == "licenses":
        return license_payload(RESEARCH_BOUNDARY)
    if module == "lakehouse":
        return lakehouse_payload(RESEARCH_BOUNDARY)
    if module == "data-quality":
        return data_quality_payload(RESEARCH_BOUNDARY)
    if module == "lineage":
        return lineage_payload(RESEARCH_BOUNDARY)
    return {
        "module": module,
        "status": "day2_contract_ready" if module in {"overview", "spark-jobs", "reports"} else "day1_placeholder_ready",
        "description": ROUTE_MODULES[module],
        "maturity": "L1-contract-and-route-stub",
        "research_boundary": RESEARCH_BOUNDARY,
    }


for module_name in ROUTE_MODULES:
    async def endpoint(module: str = module_name) -> dict[str, Any]:  # type: ignore[misc]
        return route_payload(module)

    app.add_api_route(f"/api/{module_name}", endpoint, methods=["GET"], name=f"get_{module_name}")
    app.add_api_route(f"/api/{module_name}/status", endpoint, methods=["GET"], name=f"get_{module_name}_status")
