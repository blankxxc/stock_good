from __future__ import annotations

from datetime import datetime, timezone
from html import escape
from typing import Any, Callable

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.middleware.cors import CORSMiddleware

from backend.app.routers.auth import get_auth_service, optional_principal, require_admin, router as auth_router
from backend.app.services.auth_service import configured_allowed_origins
from backend.app.services.lakehouse_catalog import data_quality_payload, lakehouse_payload, license_payload, lineage_payload
from backend.app.services.factor_store_catalog import factor_payload, feature_payload, spark_jobs_payload
from backend.app.services.research_loop_catalog import backtests_payload, condition_screen_payload, dashboard_research_loop_payload, experiments_payload, market_overview_payload, scores_payload, stock_detail_payload
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
    allow_origins=list(configured_allowed_origins()),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)


def _requires_no_store(path: str) -> bool:
    if path == "/admin" or path.startswith(("/api/auth", "/api/watchlist", "/api/admin")):
        return True
    if not path.startswith("/api/"):
        return False
    module = path.removeprefix("/api/").split("/", 1)[0]
    return module in ROUTE_MODULES and module not in PUBLIC_API_MODULES


@app.middleware("http")
async def prevent_private_response_caching(request: Request, call_next: Callable[..., Any]):
    response = await call_next(request)
    if _requires_no_store(request.url.path):
        response.headers["Cache-Control"] = "no-store"
        response.headers["Pragma"] = "no-cache"
    return response


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
            "condition_screen": "research_loop_condition_screen_ready",
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
    "condition-screen": "自定义条件选股测试：沪深300全量最新截面、条件是/否判断、可扩展技术与金融因子列",
    "market": "沪深300股票全景、最新行情、涨跌幅、成交额和个股详情入口",
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


def _ops_section_payload(status: str, *sections: str, flatten_single: bool = False) -> dict[str, Any]:
    payload = build_ops_deployment_artifacts()
    base = {"status": status, "version": payload["version"], "research_boundary": RESEARCH_BOUNDARY}
    if flatten_single and len(sections) == 1:
        return {**base, **payload[sections[0]]}
    return {**base, **{key: payload[key] for key in sections}}


def _deployment_payload() -> dict[str, Any]:
    payload = build_ops_deployment_artifacts()
    return {
        "status": "ops_deployment_deployment_backup_ready",
        "version": payload["version"],
        "research_boundary": RESEARCH_BOUNDARY,
        "ci_cd": payload["ci_cd"],
        **payload["deployment"],
    }


ROUTE_PAYLOAD_FACTORIES: dict[str, Callable[[], dict[str, Any]]] = {
    "site": lambda: site_payload(RESEARCH_BOUNDARY),
    "dashboard": lambda: dashboard_research_loop_payload(RESEARCH_BOUNDARY),
    "overview": lambda: dashboard_research_loop_payload(RESEARCH_BOUNDARY),
    "licenses": lambda: licenses_governance_simulation_payload(RESEARCH_BOUNDARY),
    "admin": lambda: admin_payload(RESEARCH_BOUNDARY),
    "audit": lambda: audit_payload(RESEARCH_BOUNDARY),
    "reports": lambda: reports_payload(RESEARCH_BOUNDARY),
    "simulation": lambda: simulation_payload(RESEARCH_BOUNDARY),
    "ops": build_ops_deployment_artifacts,
    "orchestration": lambda: _ops_section_payload("ops_deployment_orchestration_ready", "orchestration", flatten_single=True),
    "backfill": lambda: _ops_section_payload("ops_deployment_backfill_dry_run_ready", "backfill_request", "dataset_snapshot_manifest"),
    "observability": lambda: _ops_section_payload("ops_deployment_observability_ready", "observability", flatten_single=True),
    "deployment": _deployment_payload,
    "final-acceptance": build_final_acceptance_final_artifacts,
    "lakehouse": lambda: lakehouse_payload(RESEARCH_BOUNDARY),
    "data-quality": lambda: data_quality_payload(RESEARCH_BOUNDARY),
    "lineage": lambda: lineage_payload(RESEARCH_BOUNDARY),
    "factors": lambda: factor_payload(RESEARCH_BOUNDARY),
    "event-regime": lambda: event_regime_payload(RESEARCH_BOUNDARY),
    "graph": lambda: relation_graph_payload(RESEARCH_BOUNDARY),
    "features": lambda: feature_payload(RESEARCH_BOUNDARY),
    "spark-jobs": lambda: spark_jobs_payload(RESEARCH_BOUNDARY),
    "realtime": lambda: realtime_payload(RESEARCH_BOUNDARY),
    "flink-jobs": lambda: flink_jobs_payload(RESEARCH_BOUNDARY),
    "scores": lambda: scores_payload(RESEARCH_BOUNDARY),
    "condition-screen": lambda: condition_screen_payload(RESEARCH_BOUNDARY),
    "market": lambda: market_overview_payload(RESEARCH_BOUNDARY),
    "backtests": lambda: backtests_payload(RESEARCH_BOUNDARY),
    "experiments": lambda: experiments_payload(RESEARCH_BOUNDARY),
    "models": lambda: advanced_models_payload(RESEARCH_BOUNDARY),
    "rag": lambda: rag_payload(RESEARCH_BOUNDARY),
}


def route_payload(module: str) -> dict[str, Any]:
    factory = ROUTE_PAYLOAD_FACTORIES.get(module)
    if factory:
        return factory()
    return {
        "module": module,
        "status": "foundation_placeholder_ready",
        "description": ROUTE_MODULES[module],
        "maturity": "L1-contract-and-route-stub",
        "research_boundary": RESEARCH_BOUNDARY,
    }


def admin_overview_payload() -> dict[str, Any]:
    health_payload = health()
    modules = health_payload["modules"]
    ready_modules = [name for name, status in modules.items() if str(status).endswith("ready")]
    factor_data = factor_payload(RESEARCH_BOUNDARY)
    critical_routes = [
        {"path": "/health", "label": "服务健康", "method": "GET"},
        {"path": "/api/site", "label": "用户站点边界", "method": "GET"},
        {"path": "/api/factors", "label": "因子库", "method": "GET"},
        {"path": "/api/scores", "label": "股票评分", "method": "GET"},
        {"path": "/api/condition-screen", "label": "条件选股", "method": "GET"},
        {"path": "/api/backtests", "label": "回测风险", "method": "GET"},
        {"path": "/api/admin", "label": "RBAC 治理", "method": "GET"},
        {"path": "/api/audit", "label": "审计日志", "method": "GET"},
    ]
    data_fabric_routes = [
        {"path": "/api/dashboard", "label": "内部总览", "method": "GET"},
        {"path": "/api/data-quality", "label": "数据质量", "method": "GET"},
        {"path": "/api/lineage", "label": "数据血缘", "method": "GET"},
        {"path": "/api/lakehouse", "label": "Lakehouse", "method": "GET"},
        {"path": "/api/spark-jobs", "label": "Spark Jobs", "method": "GET"},
        {"path": "/api/realtime", "label": "Realtime", "method": "GET"},
        {"path": "/api/flink-jobs", "label": "Flink Jobs", "method": "GET"},
        {"path": "/api/ops", "label": "Ops / 运行维护", "method": "GET"},
    ]
    return {
        "status": "backend_admin_console_ready",
        "framework": {
            "name": "FastAPI",
            "selection_reason": "项目已采用 FastAPI；它适合 Python 量化/AI 后端的 async API、自动 OpenAPI 文档、类型校验和快速管理控制台落地。",
            "api_docs": "/docs",
            "openapi_schema": "/openapi.json",
        },
        "service": {
            "name": SERVICE_NAME,
            "version": health_payload["version"],
            "time": health_payload["time"],
            "research_boundary": RESEARCH_BOUNDARY,
        },
        "module_summary": {
            "total_modules": len(modules),
            "ready_modules": len(ready_modules),
            "pending_modules": len(modules) - len(ready_modules),
        },
        "factor_summary": {
            "status": factor_data.get("status"),
            "factor_count": factor_data.get("factor_count", 0),
            "catalog_count": len(factor_data.get("factor_catalog", [])),
            "category_count": len(factor_data.get("category_summary", [])),
            "point_in_time_violations": factor_data.get("point_in_time_join", {}).get("point_in_time_violations"),
            "admission_ready_count": factor_data.get("factor_catalog_summary", {}).get("admission_ready_count"),
        },
        "critical_routes": critical_routes,
        "data_fabric": {
            "visibility": "backend_admin_only",
            "policy": "Data Fabric、数据质量、数据血缘、湖仓、Spark/Flink/Realtime 和运维信息只在后端管理界面展示，不进入用户选股导航。",
            "internal_routes": data_fabric_routes,
        },
        "frontend_policy": {
            "public_positioning": "user_stock_selection_platform",
            "hide_data_fabric_from_user_nav": True,
            "show_only_user_safe_selection_data": True,
            "security_focus": ["最小暴露内部链路", "用户侧不展示血缘/湖仓/任务明细", "后台承接审计与权限控制"],
        },
        "documentation_links": [
            {"path": "/docs", "label": "Swagger UI"},
            {"path": "/redoc", "label": "ReDoc"},
            {"path": "/openapi.json", "label": "OpenAPI Schema"},
        ],
        "module_statuses": modules,
        "research_boundary_label": "仅研究排序、因子诊断、回测和治理监控；非投资建议。",
    }


def _render_admin_console(payload: dict[str, Any]) -> str:
    modules = payload["module_statuses"]
    critical_routes = payload["critical_routes"]
    docs = payload["documentation_links"]
    data_fabric_routes = payload["data_fabric"]["internal_routes"]
    module_rows = "".join(
        f"<tr><td>{escape(name)}</td><td><span class='status'>{escape(str(status))}</span></td></tr>"
        for name, status in sorted(modules.items())
    )
    route_cards = "".join(
        f"<a class='route-card' href='{escape(route['path'])}'><b>{escape(route['label'])}</b><span>{escape(route['method'])} {escape(route['path'])}</span></a>"
        for route in critical_routes
    )
    data_fabric_cards = "".join(
        f"<a class='route-card internal-card' href='{escape(route['path'])}'><b>{escape(route['label'])}</b><span>{escape(route['method'])} {escape(route['path'])}</span></a>"
        for route in data_fabric_routes
    )
    doc_links = "".join(
        f"<a href='{escape(item['path'])}'>{escape(item['label'])}</a>"
        for item in docs
    )
    factor = payload["factor_summary"]
    module_summary = payload["module_summary"]
    service = payload["service"]
    framework = payload["framework"]
    auth_summary = payload.get("auth_summary", {"total_users": 0, "active_users": 0, "active_sessions": 0, "watchlist_items": 0})
    admin_user = payload.get("admin_user", {"id": -1, "display_name": "管理员"})
    auth_users = payload.get("auth_users", [])
    user_rows = "".join(
        "<tr>"
        f"<td><b>{escape(str(user['display_name']))}</b><br><span>@{escape(str(user['username']))}</span></td>"
        f"<td>{escape('管理员' if user['role'] == 'admin' else '普通用户')}</td>"
        f"<td><span class='status'>{escape('启用' if user['is_active'] else '禁用')}</span></td>"
        f"<td>{escape(str(user.get('watchlist_count', 0)))}</td>"
        f"<td>{escape(str(user.get('active_sessions', 0)))}</td>"
        f"<td><button class='user-toggle' data-user-id='{int(user['id'])}' data-active='{1 if user['is_active'] else 0}' "
        f"{'disabled' if int(user['id']) == int(admin_user['id']) else ''}>"
        f"{escape('禁用' if user['is_active'] else '启用')}</button></td>"
        "</tr>"
        for user in auth_users
    )
    return f"""
<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>FastAPI 后端控制台 · Stock Research Platform</title>
  <style>
    :root {{ color-scheme: dark; --bg:#050816; --panel:#0b1224; --line:#1f2a44; --text:#e5edf7; --muted:#94a3b8; --cyan:#38bdf8; --green:#22c55e; --gold:#fbbf24; --purple:#a78bfa; }}
    * {{ box-sizing: border-box; }} body {{ margin:0; font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background: radial-gradient(circle at 20% 0%, rgba(56,189,248,.15), transparent 28%), radial-gradient(circle at 85% 10%, rgba(167,139,250,.18), transparent 30%), var(--bg); color:var(--text); }}
    .shell {{ width:min(1280px, calc(100vw - 32px)); margin:0 auto; padding:32px 0 48px; }}
    .hero, .card {{ border:1px solid rgba(148,163,184,.18); background:rgba(11,18,36,.82); border-radius:24px; box-shadow:0 18px 50px rgba(0,0,0,.28); }}
    .hero {{ padding:28px; display:grid; grid-template-columns: minmax(0, 1.3fr) minmax(280px, .7fr); gap:20px; align-items:stretch; }}
    .badge {{ display:inline-flex; align-items:center; gap:8px; padding:7px 10px; border:1px solid rgba(56,189,248,.28); color:#bae6fd; background:rgba(56,189,248,.10); border-radius:999px; font-weight:800; font-size:12px; letter-spacing:.08em; text-transform:uppercase; }}
    h1 {{ margin:16px 0 10px; font-size:clamp(34px, 5vw, 68px); line-height:.95; letter-spacing:-.06em; }}
    p {{ color:var(--muted); line-height:1.7; }}
    .status-main {{ padding:22px; border-radius:20px; background:linear-gradient(145deg, rgba(34,197,94,.14), rgba(56,189,248,.08)); border:1px solid rgba(34,197,94,.25); }}
    .status-main strong {{ display:block; margin:8px 0; color:#bbf7d0; font-size:28px; }}
    .grid {{ display:grid; grid-template-columns:repeat(auto-fit, minmax(220px, 1fr)); gap:14px; margin-top:18px; }}
    .card {{ padding:20px; }} .card span {{ color:var(--muted); font-size:12px; }} .card strong {{ display:block; margin-top:8px; font-size:30px; font-family:ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; }}
    .section {{ margin-top:20px; }} .section h2 {{ margin:0 0 12px; }}
    .route-grid {{ display:grid; grid-template-columns:repeat(auto-fit, minmax(230px, 1fr)); gap:12px; }}
    .route-card {{ display:block; padding:16px; border-radius:18px; border:1px solid rgba(56,189,248,.20); background:rgba(56,189,248,.07); color:var(--text); text-decoration:none; }} .route-card:hover {{ border-color:var(--cyan); transform:translateY(-1px); }} .route-card span {{ display:block; margin-top:8px; color:var(--muted); font-family:ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; font-size:12px; }}
    .internal-card {{ border-color:rgba(251,191,36,.24); background:rgba(251,191,36,.08); }}
    table {{ width:100%; border-collapse:collapse; overflow:hidden; }} th, td {{ padding:12px 10px; border-bottom:1px solid rgba(148,163,184,.14); text-align:left; }} th {{ color:#cbd5e1; font-size:12px; text-transform:uppercase; letter-spacing:.12em; }} .status {{ color:#bbf7d0; font-family:ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; }}
    .docs {{ display:flex; gap:10px; flex-wrap:wrap; }} .docs a {{ color:#dbeafe; text-decoration:none; padding:10px 12px; border-radius:999px; border:1px solid rgba(167,139,250,.28); background:rgba(167,139,250,.10); }}
    .admin-actions {{ display:flex; align-items:center; gap:8px; flex-wrap:wrap; margin-top:16px; }} .admin-actions a, .admin-actions button, .user-toggle {{ border:1px solid rgba(56,189,248,.24); border-radius:10px; padding:8px 11px; color:#dbeafe; background:rgba(56,189,248,.08); font:inherit; text-decoration:none; cursor:pointer; }} .admin-actions button {{ border-color:rgba(248,113,113,.24); color:#fecaca; background:rgba(127,29,29,.12); }} .user-toggle:disabled {{ opacity:.4; cursor:not-allowed; }}
    .warning {{ border-color:rgba(251,191,36,.26); background:rgba(251,191,36,.08); color:#fde68a; }}
    @media (max-width: 900px) {{ .hero {{ grid-template-columns:1fr; }} }}
  </style>
</head>
<body>
  <main class="shell">
    <section class="hero">
      <div>
        <span class="badge">{escape(framework['name'])} · backend admin</span>
        <h1>FastAPI 后端控制台</h1>
        <p>{escape(framework['selection_reason'])}</p>
        <p>{escape(payload['research_boundary_label'])}</p>
        <div class="admin-actions"><span>当前管理员：{escape(str(admin_user['display_name']))}</span><a href="/">返回前台</a><button id="admin-logout" type="button">安全退出</button></div>
      </div>
      <div class="status-main">
        <span>console status</span>
        <strong>{escape(payload['status'])}</strong>
        <p>{escape(service['name'])} · {escape(service['version'])}</p>
      </div>
    </section>

    <section class="grid">
      <div class="card"><span>模块健康</span><strong>{module_summary['ready_modules']}/{module_summary['total_modules']}</strong><p>ready modules</p></div>
      <div class="card"><span>因子总数</span><strong>{factor['factor_count']}</strong><p>factor catalog {factor['catalog_count']}</p></div>
      <div class="card"><span>因子分类</span><strong>{factor['category_count']}</strong><p>category summary</p></div>
      <div class="card"><span>点时间违规</span><strong>{factor['point_in_time_violations']}</strong><p>available_time ≤ prediction_time</p></div>
    </section>

    <section class="grid">
      <div class="card"><span>注册用户</span><strong>{auth_summary['total_users']}</strong><p>启用 {auth_summary['active_users']}</p></div>
      <div class="card"><span>活跃会话</span><strong>{auth_summary['active_sessions']}</strong><p>可撤销服务端会话</p></div>
      <div class="card"><span>自选记录</span><strong>{auth_summary['watchlist_items']}</strong><p>按用户严格隔离</p></div>
    </section>

    <section class="section card">
      <h2>用户与权限</h2>
      <p>公开注册仅能创建普通用户；禁用用户会立即撤销其全部登录会话。</p>
      <table><thead><tr><th>账号</th><th>角色</th><th>状态</th><th>自选数</th><th>活跃会话</th><th>操作</th></tr></thead><tbody>{user_rows}</tbody></table>
    </section>

    <section class="section card">
      <h2>关键后端入口</h2>
      <div class="route-grid">{route_cards}</div>
    </section>

    <section class="section card">
      <h2>Data Fabric 内部管理</h2>
      <p>{escape(payload['data_fabric']['policy'])}</p>
      <div class="route-grid">{data_fabric_cards}</div>
    </section>

    <section class="section grid">
      <div class="card">
        <h2>因子库摘要</h2>
        <p>状态：<span class="status">{escape(str(factor['status']))}</span></p>
        <p>研究可复核因子：{escape(str(factor['admission_ready_count']))}</p>
        <p>非投资建议：所有信号仅用于研究排序、回测和人工复核。</p>
      </div>
      <div class="card">
        <h2>文档入口</h2>
        <div class="docs">{doc_links}</div>
        <p>FastAPI 自动生成 Swagger / ReDoc / OpenAPI，适合后端调试和接口验收。</p>
      </div>
    </section>

    <section class="section card">
      <h2>模块健康</h2>
      <table><thead><tr><th>module</th><th>status</th></tr></thead><tbody>{module_rows}</tbody></table>
    </section>

    <section class="section card warning">
      <b>研究边界</b>
      <p>这是智能选股平台的后台管理区，不面向普通用户展示；正式对外使用前需要权限控制、审计、数据脱敏和人工复核。所有页面均为选股辅助，非投资建议。</p>
    </section>
  </main>
  <script>
    function cookieValue(name) {{
      const item = document.cookie.split('; ').find((value) => value.startsWith(name + '='));
      return item ? decodeURIComponent(item.slice(name.length + 1)) : '';
    }}
    document.querySelectorAll('.user-toggle').forEach((button) => {{
      button.addEventListener('click', async () => {{
        if (button.disabled) return;
        button.disabled = true;
        const nextActive = button.dataset.active !== '1';
        const response = await fetch('/api/admin/users/' + button.dataset.userId, {{
          method: 'PATCH',
          headers: {{ 'Content-Type': 'application/json', 'X-CSRF-Token': cookieValue('oa_csrf') }},
          credentials: 'same-origin',
          body: JSON.stringify({{ is_active: nextActive }}),
        }});
        if (response.ok) window.location.reload();
        else {{ alert('用户状态更新失败，请刷新后重试。'); button.disabled = false; }}
      }});
    }});
    document.getElementById('admin-logout').addEventListener('click', async () => {{
      const response = await fetch('/api/auth/logout', {{
        method: 'POST',
        headers: {{ 'X-CSRF-Token': cookieValue('oa_csrf') }},
        credentials: 'same-origin',
      }});
      if (response.ok) window.location.assign('/login');
    }});
  </script>
</body>
</html>
"""


@app.get("/api/admin/overview")
def get_admin_overview(
    request: Request,
    _: object = Depends(require_admin),
) -> JSONResponse:
    payload = admin_overview_payload()
    payload["auth_summary"] = get_auth_service(request).auth_summary()
    return JSONResponse(payload, headers={"Cache-Control": "no-store", "Pragma": "no-cache"})


@app.get("/admin", response_class=HTMLResponse)
def get_admin_console(request: Request) -> HTMLResponse:
    principal = optional_principal(request)
    if principal is None:
        return RedirectResponse(
            "/login?next=/backend-admin",
            status_code=307,
            headers={"Cache-Control": "no-store", "Pragma": "no-cache"},
        )
    if principal.role != "admin":
        raise HTTPException(status_code=403, detail="仅管理员可访问后台控制台。")
    payload = admin_overview_payload()
    service = get_auth_service(request)
    payload["auth_summary"] = service.auth_summary()
    payload["auth_users"] = service.list_users()
    payload["admin_user"] = principal.public_user()
    return HTMLResponse(_render_admin_console(payload), headers={"Cache-Control": "no-store"})


@app.get("/api/stocks/{symbol}")
def get_stock_detail(symbol: str) -> dict[str, Any]:
    return stock_detail_payload(symbol, RESEARCH_BOUNDARY)


PUBLIC_API_MODULES = {
    "site",
    "factors",
    "event-regime",
    "graph",
    "scores",
    "condition-screen",
    "market",
    "backtests",
    "experiments",
    "models",
}


for module_name in ROUTE_MODULES:
    async def endpoint(module: str = module_name) -> dict[str, Any]:  # type: ignore[misc]
        return route_payload(module)

    dependencies = [] if module_name in PUBLIC_API_MODULES else [Depends(require_admin)]
    app.add_api_route(
        f"/api/{module_name}", endpoint, methods=["GET"], name=f"get_{module_name}", dependencies=dependencies
    )
    app.add_api_route(
        f"/api/{module_name}/status",
        endpoint,
        methods=["GET"],
        name=f"get_{module_name}_status",
        dependencies=dependencies,
    )
