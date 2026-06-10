from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.app.services.lakehouse_catalog import data_quality_payload, lakehouse_payload, license_payload, lineage_payload
from backend.app.services.factor_store_catalog import factor_payload, feature_payload, spark_jobs_payload
from backend.app.services.research_loop_catalog import backtests_payload, dashboard_research_loop_payload, experiments_payload, scores_payload
from backend.app.services.realtime_streaming_catalog import flink_jobs_payload, realtime_payload
from backend.app.services.event_regime_catalog import event_regime_payload
from backend.app.services.relation_graph_catalog import relation_graph_payload
from backend.app.services.advanced_models_catalog import advanced_models_payload
from backend.app.services.rag_evidence_catalog import rag_payload
from backend.app.services.research_site_catalog import site_payload
from backend.app.services.governance_simulation_catalog import admin_payload, audit_payload, licenses_governance_simulation_payload, reports_payload, simulation_payload
from ops.ops_deployment_ops import build_ops_deployment_artifacts
from ops.final_acceptance_final import build_final_acceptance_final_artifacts

SERVICE_NAME = "stock-research-platform"
RESEARCH_BOUNDARY = "research_signals_only_not_investment_advice"

app = FastAPI(
    title="Intelligent Stock Research Platform",
    version="0.1.0-final_acceptance",
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
        "version": "0.1.0-final_acceptance",
        "time": datetime.now(timezone.utc).isoformat(),
        "research_boundary": RESEARCH_BOUNDARY,
        "modules": {
            "backend": "stub_ready",
            "frontend": "research_site_productized_routes_ready",
            "site": "research_site_productized_research_console_ready",
            "lakehouse": "lakehouse_parquet_duckdb_snapshot_ready",
            "data_quality": "data_trust_quality_quarantine_leakage_ready",
            "lineage": "data_trust_source_job_snapshot_report_ready",
            "spark": "factor_store_factor_materialization_consistency_ready",
            "factor_store": "factor_store_offline_factor_store_ready",
            "labels": "research_loop_cross_sectional_labels_ready",
            "scores": "research_loop_lightgbm_scores_ready",
            "backtests": "research_loop_tradable_backtest_risk_capacity_ready",
            "experiments": "research_loop_experiment_recorder_ready",
            "realtime": "realtime_streaming_replay_kafka_online_feature_ready",
            "flink": "realtime_streaming_event_time_factor_jobs_ready",
            "redpanda_kafka": "realtime_streaming_standard_topics_replay_ready",
            "clickhouse": "realtime_streaming_clickhouse_adapter_reserved_sqlite_sink_ready",
            "event_regime": "event_regime_event_market_regime_ablation_ready",
            "financial_text": "event_regime_finbert_compatible_lexicon_baseline_ready",
            "relation_graph": "relation_graph_stock_relation_graph_ready",
            "graph_factors": "relation_graph_relation_spillover_factor_ready",
            "hist_trsr_adapter": "relation_graph_hist_trsr_relation_inputs_ready",
            "advanced_models": "advanced_models_research_candidate_adapters_ready",
            "rag": "rag_evidence_claim_evidence_rag_ready",
            "simulation": "governance_simulation_paper_simulation_governance_ready",
            "rbac": "governance_simulation_rbac_duties_ready",
            "reports": "governance_simulation_report_export_manifest_ready",
            "license_policy": "governance_simulation_license_policy_engine_ready",
            "audit": "governance_simulation_append_only_audit_ready",
            "orchestration": "ops_deployment_prefect_local_dag_ready",
            "config_hash": "ops_deployment_resolved_config_hash_ready",
            "backfill": "ops_deployment_backfill_dry_run_ready",
            "dataset_snapshots": "ops_deployment_recoverable_snapshot_manifest_ready",
            "observability": "ops_deployment_ops_metrics_ready",
            "ci_cd": "ops_deployment_quality_gates_ready",
            "deployment": "ops_deployment_compose_proxy_k8s_ready",
            "backup_restore": "ops_deployment_backup_restore_smoke_ready",
            "final_acceptance": "final_acceptance_final_acceptance_ready",
            "documentation": "final_acceptance_docs_demo_coverage_ready",
        },
    }


ROUTE_MODULES = {
    "site": "官网层、Research Console 全页面、统一视觉系统和 artifact-backed 主卡片",
    "auth": "认证、RBAC 与 action-level permission 占位",
    "dashboard": "研究平台 dashboard、最新 run、模型版本、质量状态和核心指标",
    "overview": "研究平台总览、数据 cutoff、模型版本和质量状态",
    "data-quality": "数据质量、缺失、异常、quarantine 与延迟摘要",
    "lineage": "ODS/DWD/DWS/ADS、Spark/Flink job 到结果快照的血缘",
    "lakehouse": "Bronze/Silver/Gold/ADS 与 Iceberg/Hudi/Delta PoC 状态",
    "spark-jobs": "Spark 离线 ETL、批量因子、标签和训练样本 job 状态",
    "realtime": "Kafka topic、实时数据延迟、在线特征和实时评分状态",
    "flink-jobs": "Flink event-time、watermark、window、late-data job 状态",
    "factors": "离线/实时/事件/市场环境/关系因子库",
    "event-regime": "新闻/公告/事件因子、金融文本 baseline、market regime 与 ablation 状态",
    "features": "Feature Store、feature view、point-in-time join 和 materialization job",
    "graph": "行业/概念/供应链/共现/价格相关关系图",
    "models": "Qlib、LightGBM、MASTER、StockMixer、HIST、TRSR 适配器",
    "scores": "横截面模型分数、rank、percentile、置信度和研究边界",
    "experiments": "MLflow/Qlib Recorder 实验记录",
    "backtests": "TopK、long-short、risk/cost/capacity 回测报告",
    "rag": "claim 级证据、as-of 检索、引用和评测",
    "reports": "报告状态机、license gate、export_manifest 与 file_hash",
    "simulation": "模拟账户、模拟订单、模拟持仓和风控约束",
    "admin": "用户、角色、权限、系统配置管理",
    "audit": "审计日志和治理事件查询",
    "ops": "ops_deployment 任务编排、配置哈希、回填、可观测性、CI/CD、部署和备份恢复",
    "orchestration": "Prefect local DAG、MVP pipeline 和扩展 DAG dry-run",
    "backfill": "backfill_request、dry-run 影响范围和新 snapshot",
    "observability": "数据/任务/模型/系统指标和 Spark/Flink/Kafka/ClickHouse/PostgreSQL/Redis 状态",
    "deployment": "Docker Compose、反向代理、K8s 草案、CI/CD 和 backup/restore smoke",
    "final-acceptance": "final_acceptance 全量联调、最终验收、覆盖矩阵、文档和演示资产",
    "licenses": "数据许可证、可展示范围和 license_gate",
}


def route_payload(module: str) -> dict[str, Any]:
    if module == "site":
        return site_payload(RESEARCH_BOUNDARY)
    if module in {"dashboard", "overview"}:
        return dashboard_research_loop_payload(RESEARCH_BOUNDARY)
    if module == "licenses":
        return licenses_governance_simulation_payload(RESEARCH_BOUNDARY)
    if module == "admin":
        return admin_payload(RESEARCH_BOUNDARY)
    if module == "audit":
        return audit_payload(RESEARCH_BOUNDARY)
    if module == "reports":
        return reports_payload(RESEARCH_BOUNDARY)
    if module == "simulation":
        return simulation_payload(RESEARCH_BOUNDARY)
    if module == "ops":
        return build_ops_deployment_artifacts()
    if module == "orchestration":
        payload = build_ops_deployment_artifacts()
        return {"status": "ops_deployment_orchestration_ready", "version": payload["version"], "research_boundary": RESEARCH_BOUNDARY, **payload["orchestration"]}
    if module == "backfill":
        payload = build_ops_deployment_artifacts()
        return {"status": "ops_deployment_backfill_dry_run_ready", "version": payload["version"], "research_boundary": RESEARCH_BOUNDARY, "backfill_request": payload["backfill_request"], "dataset_snapshot_manifest": payload["dataset_snapshot_manifest"]}
    if module == "observability":
        payload = build_ops_deployment_artifacts()
        return {"status": "ops_deployment_observability_ready", "version": payload["version"], "research_boundary": RESEARCH_BOUNDARY, **payload["observability"]}
    if module == "deployment":
        payload = build_ops_deployment_artifacts()
        return {"status": "ops_deployment_deployment_backup_ready", "version": payload["version"], "research_boundary": RESEARCH_BOUNDARY, "ci_cd": payload["ci_cd"], **payload["deployment"]}
    if module == "final-acceptance":
        return build_final_acceptance_final_artifacts()
    if module == "lakehouse":
        return lakehouse_payload(RESEARCH_BOUNDARY)
    if module == "data-quality":
        return data_quality_payload(RESEARCH_BOUNDARY)
    if module == "lineage":
        return lineage_payload(RESEARCH_BOUNDARY)
    if module == "factors":
        return factor_payload(RESEARCH_BOUNDARY)
    if module == "event-regime":
        return event_regime_payload(RESEARCH_BOUNDARY)
    if module == "graph":
        return relation_graph_payload(RESEARCH_BOUNDARY)
    if module == "features":
        return feature_payload(RESEARCH_BOUNDARY)
    if module == "spark-jobs":
        return spark_jobs_payload(RESEARCH_BOUNDARY)
    if module == "realtime":
        return realtime_payload(RESEARCH_BOUNDARY)
    if module == "flink-jobs":
        return flink_jobs_payload(RESEARCH_BOUNDARY)
    if module == "scores":
        return scores_payload(RESEARCH_BOUNDARY)
    if module == "backtests":
        return backtests_payload(RESEARCH_BOUNDARY)
    if module == "experiments":
        return experiments_payload(RESEARCH_BOUNDARY)
    if module == "models":
        return advanced_models_payload(RESEARCH_BOUNDARY)
    if module == "rag":
        return rag_payload(RESEARCH_BOUNDARY)
    return {
        "module": module,
        "status": "lakehouse_contract_ready" if module in {"overview", "spark-jobs", "reports"} else "foundation_placeholder_ready",
        "description": ROUTE_MODULES[module],
        "maturity": "L1-contract-and-route-stub",
        "research_boundary": RESEARCH_BOUNDARY,
    }


for module_name in ROUTE_MODULES:
    async def endpoint(module: str = module_name) -> dict[str, Any]:  # type: ignore[misc]
        return route_payload(module)

    app.add_api_route(f"/api/{module_name}", endpoint, methods=["GET"], name=f"get_{module_name}")
    app.add_api_route(f"/api/{module_name}/status", endpoint, methods=["GET"], name=f"get_{module_name}_status")
