from pathlib import Path

import yaml


PROJECT_ROOT = Path(__file__).resolve().parents[1]

REQUIRED_DIRS = [
    "backend/app/api",
    "backend/app/core",
    "backend/app/db",
    "backend/app/services",
    "backend/app/schemas",
    "backend/app/workers",
    "backend/app/security",
    "frontend/src/app",
    "data/raw",
    "data/bronze",
    "data/silver",
    "data/gold",
    "data/ads",
    "data/quarantine",
    "data/snapshots",
    "data/samples",
    "data_contracts",
    "warehouse_schema/tables",
    "warehouse_schema/migrations",
    "lakehouse/iceberg",
    "lakehouse/hudi",
    "lakehouse/delta",
    "lakehouse/catalogs",
    "spark/jobs",
    "spark/libs",
    "spark/tests",
    "spark/conf",
    "streaming/kafka",
    "streaming/flink",
    "streaming/producers",
    "streaming/jobs",
    "streaming/schemas",
    "factors/offline",
    "factors/realtime",
    "factors/event",
    "factors/regime",
    "factors/relation",
    "factors/specs",
    "factors/reports",
    "feature_store/feature_views",
    "feature_store/materialization_jobs",
    "feature_store/point_in_time_join",
    "graph/builders",
    "graph/adapters",
    "graph/reports",
    "rag/ingestion",
    "rag/retrieval",
    "rag/evidence",
    "rag/evals",
    "rag/schemas",
    "models/qlib",
    "models/lightgbm",
    "models/master",
    "models/stockmixer",
    "models/hist",
    "models/trsr",
    "models/text",
    "models/adapters",
    "backtest/engine",
    "backtest/metrics",
    "backtest/attribution",
    "backtest/risk",
    "simulation",
    "reports",
    "configs/env",
    "configs/universe",
    "configs/data",
    "configs/factor",
    "configs/label",
    "configs/model",
    "configs/backtest",
    "tests/unit",
    "tests/data",
    "tests/leakage",
    "tests/smoke",
    "tests/e2e",
    "deploy/docker",
    "deploy/k8s",
    "deploy/monitoring",
    "deploy/backup",
    "docs/adr",
]

SCHEMA_FILES = [
    "market_daily.schema.yaml",
    "market_minute.schema.yaml",
    "market_tick.schema.yaml",
    "trade.schema.yaml",
    "orderbook.schema.yaml",
    "financial_statement.schema.yaml",
    "announcement_event.schema.yaml",
    "news_event.schema.yaml",
    "macro_event.schema.yaml",
    "stock_relation_edge.schema.yaml",
    "factor_daily_panel.schema.yaml",
    "factor_intraday_panel.schema.yaml",
    "label_cross_sectional_return.schema.yaml",
    "model_training_sample.schema.yaml",
    "model_signal_cross_sectional.schema.yaml",
    "portfolio_backtest_result.schema.yaml",
    "rag_claim.schema.yaml",
]

REQUIRED_METADATA_FIELDS = {
    "source",
    "license_id",
    "data_version",
    "schema_version",
    "trace_id",
}

REQUIRED_TABLES = [
    "users",
    "roles",
    "permissions",
    "audit_log",
    "data_license_registry",
    "data_snapshot_registry",
    "dataset_snapshot_manifest",
    "schema_registry",
    "factor_registry",
    "feature_registry",
    "model_registry",
    "experiment_run",
    "pipeline_task_run",
    "spark_job_run",
    "flink_job_run",
    "report_registry",
    "rag_document",
    "rag_chunk",
    "rag_claim",
    "graph_node",
    "graph_edge",
    "simulation_account",
    "simulation_order",
    "simulation_position",
    "export_manifest",
    "backfill_request",
    "adr_record",
    "risk_register_item",
]

BACKEND_ROUTE_PREFIXES = [
    "/health",
    "/api/auth",
    "/api/overview",
    "/api/data-quality",
    "/api/lineage",
    "/api/lakehouse",
    "/api/spark-jobs",
    "/api/realtime",
    "/api/flink-jobs",
    "/api/factors",
    "/api/features",
    "/api/graph",
    "/api/models",
    "/api/experiments",
    "/api/backtests",
    "/api/rag",
    "/api/reports",
    "/api/simulation",
    "/api/admin",
    "/api/audit",
    "/api/licenses",
]

FRONTEND_ROUTES = [
    "page.tsx",
    "dashboard/page.tsx",
    "scores/page.tsx",
    "candidates/page.tsx",
    "backtests/page.tsx",
    "factors/page.tsx",
    "experiments/page.tsx",
    "rag/page.tsx",
    "data-quality/page.tsx",
    "lineage/page.tsx",
    "lakehouse/page.tsx",
    "spark-jobs/page.tsx",
    "realtime/page.tsx",
    "flink-jobs/page.tsx",
    "graph/page.tsx",
    "models/page.tsx",
    "simulation/page.tsx",
    "reports/page.tsx",
    "settings/licenses/page.tsx",
    "settings/users/page.tsx",
    "settings/audit/page.tsx",
]

ADR_FILES = [
    "ADR-001-scope-full-two-week-demo.md",
    "ADR-002-point-in-time-time-semantics.md",
    "ADR-003-spark-flink-responsibility-boundary.md",
    "ADR-004-lakehouse-format-choice.md",
]

COMPOSE_SERVICES = {
    "postgres",
    "redis",
    "qdrant",
    "redpanda",
    "flink-jobmanager",
    "flink-taskmanager",
    "spark-master",
    "spark-worker",
    "clickhouse",
    "backend",
    "worker",
    "frontend",
    "prometheus",
    "grafana",
    "backup",
}

ALEMBIC_FILES = [
    "alembic.ini",
    "backend/app/db/alembic/env.py",
    "backend/app/db/alembic/script.py.mako",
    "backend/app/db/alembic/versions/0001_day1_metadata.py",
]


def test_required_day1_directory_structure_exists():
    missing = [path for path in REQUIRED_DIRS if not (PROJECT_ROOT / path).is_dir()]
    assert missing == []


def test_data_contracts_exist_and_have_required_metadata():
    missing = [name for name in SCHEMA_FILES if not (PROJECT_ROOT / "data_contracts" / name).is_file()]
    assert missing == []

    for name in SCHEMA_FILES:
        content = yaml.safe_load((PROJECT_ROOT / "data_contracts" / name).read_text(encoding="utf-8"))
        assert content["schema_version"].startswith("v")
        assert content["table"]
        assert content["layer"] in {"ODS", "DWD", "DWS", "ADS", "RAG"}
        assert content["primary_key"]
        assert content["unique_key"]
        fields = content["fields"]
        assert isinstance(fields, list) and fields
        names = {field["name"] for field in fields}
        assert REQUIRED_METADATA_FIELDS.issubset(names), name
        assert any(field.get("time_semantic") for field in fields), name
        assert all("nullable" in field for field in fields), name
        assert all("backfill_allowed" in field for field in fields), name


def test_metadata_migration_contains_all_day1_tables():
    migration = PROJECT_ROOT / "warehouse_schema" / "migrations" / "0001_day1_metadata.sql"
    assert migration.is_file()
    text = migration.read_text(encoding="utf-8").lower()
    missing = [table for table in REQUIRED_TABLES if f"create table if not exists {table}" not in text]
    assert missing == []


def test_backend_health_and_route_placeholders():
    from fastapi.testclient import TestClient
    from backend.app.main import app

    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["service"] == "stock-research-platform"
    assert payload["research_boundary"] == "research_signals_only_not_investment_advice"

    paths = {route.path for route in app.routes}
    missing = [prefix for prefix in BACKEND_ROUTE_PREFIXES if not any(path.startswith(prefix) for path in paths)]
    assert missing == []


def test_frontend_routes_and_governance_docs_are_stubbed():
    missing_routes = [route for route in FRONTEND_ROUTES if not (PROJECT_ROOT / "frontend" / "src" / "app" / route).is_file()]
    assert missing_routes == []

    missing_adrs = [name for name in ADR_FILES if not (PROJECT_ROOT / "docs" / "adr" / name).is_file()]
    assert missing_adrs == []
    assert (PROJECT_ROOT / "docs" / "risk_register.md").is_file()
    assert (PROJECT_ROOT / "feature_store" / "feature_registry.yaml").is_file()
    assert (PROJECT_ROOT / "deploy" / "docker" / "docker-compose.yml").is_file()
    assert (PROJECT_ROOT / "README.md").is_file()


def test_compose_manifest_contains_all_day1_services():
    compose_path = PROJECT_ROOT / "deploy" / "docker" / "docker-compose.yml"
    compose = yaml.safe_load(compose_path.read_text(encoding="utf-8"))
    services = set(compose["services"])
    missing_services = sorted(COMPOSE_SERVICES - services)
    assert missing_services == []


def test_alembic_day1_migration_scaffold_exists():
    missing_alembic_files = [path for path in ALEMBIC_FILES if not (PROJECT_ROOT / path).is_file()]
    assert missing_alembic_files == []

    migration_text = (PROJECT_ROOT / "backend" / "app" / "db" / "alembic" / "versions" / "0001_day1_metadata.py").read_text(encoding="utf-8")
    missing_tables = [table for table in REQUIRED_TABLES if f'"{table}"' not in migration_text]
    assert missing_tables == []


def test_spark_and_flink_smoke_artifacts_exist():
    assert (PROJECT_ROOT / "spark" / "jobs" / "day1_spark_smoke.py").is_file()
    assert (PROJECT_ROOT / "spark" / "conf" / "spark-defaults.conf").is_file()
    assert (PROJECT_ROOT / "streaming" / "flink" / "day1_flink_job_graph.py").is_file()
    assert (PROJECT_ROOT / "streaming" / "kafka" / "topics.yaml").is_file()
