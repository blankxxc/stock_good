from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

import yaml
from fastapi.testclient import TestClient

PROJECT_ROOT = Path(__file__).resolve().parents[1]
FRONTEND_APP = PROJECT_ROOT / "frontend" / "src" / "app"
REQUIRED_CONFIGS = [
    "configs/base.yaml",
    "configs/env/local.yaml",
    "configs/env/staging.yaml",
    "configs/universe/csi800.yaml",
    "configs/data/daily_mvp.yaml",
    "configs/factor/alpha_mvp_v001.yaml",
    "configs/label/label_5d_10d_v001.yaml",
    "configs/model/lightgbm_baseline.yaml",
    "configs/backtest/top50_weekly_vwap.yaml",
    "configs/streaming/flink_realtime_poc.yaml",
    "configs/spark/spark_local.yaml",
]
MVP_DAG = [
    "ingest_daily_market",
    "validate_market_daily",
    "ingest_reference_data",
    "validate_reference_data",
    "spark_bronze_to_silver",
    "spark_materialize_factor_daily",
    "build_labels",
    "leakage_check",
    "point_in_time_join",
    "build_training_matrix",
    "train_lightgbm",
    "run_backtest",
    "generate_risk_report",
    "build_rag_index",
    "publish_to_research_console",
]
EXTENDED_DAG = [
    "replay_minute_data",
    "kafka_produce_raw_topics",
    "flink_realtime_factor_jobs",
    "compare_realtime_offline_factors",
    "update_online_features",
    "update_graph",
    "run_advanced_model_small_sample",
    "run_simulation",
    "export_reports",
]
CI_GATES = [
    "ruff",
    "black_check",
    "pytest",
    "schema_validation",
    "leakage_tests",
    "synthetic_mini_market_tests",
    "spark_job_smoke",
    "flink_job_smoke",
    "small_sample_training_smoke",
    "small_sample_backtest_smoke",
    "rag_citation_rule_test",
    "frontend_lint",
    "frontend_build",
    "api_smoke",
    "docker_build",
    "database_migration_dry_run",
]
BACKUP_ASSETS = [
    "raw_data",
    "cleaned_data",
    "factor_panel",
    "label_table",
    "experiment_metadata",
    "model_files",
    "backtest_reports",
    "rag_documents_and_index",
    "config_files",
    "database_migrations",
]
FORBIDDEN_SECRET_PATTERNS = [r"sk-[A-Za-z0-9]", r"ghp_[A-Za-z0-9]", r"Bearer\s+[A-Za-z0-9]", r"password:\s*[^<]", r"api_key:\s*[^<]"]


def test_day13_config_hash_orchestration_backfill_and_observability_contracts_are_ready():
    from ops.day13_ops import build_day13_artifacts

    payload = build_day13_artifacts()
    assert payload["status"] == "day13_ops_deployment_ready"
    assert payload["version"] == "0.1.0-day13"

    for rel in REQUIRED_CONFIGS:
        path = PROJECT_ROOT / rel
        assert path.is_file(), rel
        text = path.read_text(encoding="utf-8")
        assert yaml.safe_load(text), rel
        for pattern in FORBIDDEN_SECRET_PATTERNS:
            assert not re.search(pattern, text, flags=re.IGNORECASE), rel

    config = payload["config"]
    assert config["orchestrator"] == "prefect-local"
    assert config["resolved_config_path"].endswith("resolved_config.yaml")
    assert re.fullmatch(r"[0-9a-f]{64}", config["config_hash"])
    resolved = yaml.safe_load((PROJECT_ROOT / config["resolved_config_path"]).read_text(encoding="utf-8"))
    assert resolved["research_boundary"] == "research_signals_only_not_investment_advice"
    assert "api_key" not in json.dumps(resolved).lower()
    assert "token" not in json.dumps(resolved).lower()
    assert "password" not in json.dumps(resolved).lower()

    orchestration = payload["orchestration"]
    assert orchestration["orchestrator"] == "prefect-local"
    assert [task["task_id"] for task in orchestration["mvp_dag"]] == MVP_DAG
    assert [task["task_id"] for task in orchestration["extended_dag"]] == EXTENDED_DAG
    assert all(task["status"] in {"ready", "deferred_l1_poc"} for task in orchestration["mvp_dag"] + orchestration["extended_dag"])
    assert orchestration["one_click_pipeline"]["command"] == "python scripts/run_day13_pipeline.py --dry-run"

    backfill = payload["backfill_request"]
    for key in ["backfill_id", "dataset_name", "partition_start", "partition_end", "reason", "source_correction_id", "requested_by", "approved_by", "dry_run_result", "affected_downstream", "new_snapshot_id", "status", "created_at", "finished_at"]:
        assert key in backfill
    assert backfill["status"] == "dry_run_passed"
    assert backfill["dry_run_result"]["would_overwrite_formal_report_snapshot"] is False
    assert backfill["dry_run_result"]["leakage_check_required"] is True
    assert "train_lightgbm" in backfill["affected_downstream"]
    assert backfill["new_snapshot_id"].startswith("snapshot_day13_")

    snapshot_manifest = payload["dataset_snapshot_manifest"]
    assert snapshot_manifest["status"] == "recoverable_snapshot_manifest_ready"
    assert snapshot_manifest["data_version"].startswith("data_v")
    assert {item["restore_key"] for item in snapshot_manifest["snapshots"]} >= {"data_version", "run_id", "trade_date", "kafka_offset", "model_version", "rag_index_version"}

    observability = payload["observability"]
    for section in ["data_metrics", "task_metrics", "model_metrics", "system_metrics"]:
        assert section in observability and observability[section], section
    assert {component["component"] for component in observability["component_health"]} >= {"spark", "flink", "kafka", "clickhouse", "postgresql", "redis"}
    assert observability["component_health"][0]["observable"] is True


def test_day13_deployment_ci_backup_assets_and_api_are_ready():
    from backend.app.main import app
    from scripts.check_day13_acceptance import run_acceptance

    required_files = [
        ".github/workflows/ci.yml",
        "deploy/docker/docker-compose.yml",
        "deploy/docker/.env.example",
        "deploy/proxy/Caddyfile",
        "deploy/k8s/day13-platform.yaml",
        "deploy/backup/backup_day13.sh",
        "deploy/backup/restore_day13.sh",
        "deploy/monitoring/prometheus.yml",
        "deploy/monitoring/grafana/day13_ops_dashboard.json",
        "scripts/run_day13_pipeline.py",
        "scripts/check_day13_acceptance.py",
        "ops/day13_ops.py",
    ]
    for rel in required_files:
        path = PROJECT_ROOT / rel
        assert path.is_file(), rel
        text = path.read_text(encoding="utf-8")
        assert text.strip(), rel
        for pattern in FORBIDDEN_SECRET_PATTERNS:
            assert not re.search(pattern, text, flags=re.IGNORECASE), rel

    ci = (PROJECT_ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    for gate in CI_GATES:
        assert gate in ci, gate
    assert "pytest" in ci and "npm run build" in ci and "docker compose" in ci

    env_example = (PROJECT_ROOT / "deploy" / "docker" / ".env.example").read_text(encoding="utf-8")
    assert "CHANGE_ME_LOCAL_ONLY" in env_example
    assert "POSTGRES_PASSWORD" in env_example
    assert "SECRET" not in env_example

    compose_config = subprocess.run(
        ["docker", "compose", "-f", "deploy/docker/docker-compose.yml", "config", "--services"],
        cwd=PROJECT_ROOT,
        text=True,
        capture_output=True,
        timeout=120,
    )
    assert compose_config.returncode == 0, compose_config.stderr + compose_config.stdout
    services = set(compose_config.stdout.splitlines())
    assert {"postgres", "redis", "redpanda", "flink-jobmanager", "spark-master", "clickhouse", "backend", "frontend", "prometheus", "grafana", "backup"}.issubset(services)

    backup_smoke = subprocess.run(
        ["sh", "deploy/backup/backup_day13.sh", "--smoke"],
        cwd=PROJECT_ROOT,
        text=True,
        capture_output=True,
        timeout=120,
    )
    assert backup_smoke.returncode == 0, backup_smoke.stderr + backup_smoke.stdout
    restore_smoke = subprocess.run(
        ["sh", "deploy/backup/restore_day13.sh", "--smoke"],
        cwd=PROJECT_ROOT,
        text=True,
        capture_output=True,
        timeout=120,
    )
    assert restore_smoke.returncode == 0, restore_smoke.stderr + restore_smoke.stdout

    client = TestClient(app)
    endpoints = {
        "/api/ops": "day13_ops_deployment_ready",
        "/api/orchestration": "day13_orchestration_ready",
        "/api/backfill": "day13_backfill_dry_run_ready",
        "/api/observability": "day13_observability_ready",
        "/api/deployment": "day13_deployment_backup_ready",
    }
    for path, expected_status in endpoints.items():
        response = client.get(path)
        assert response.status_code == 200, path
        assert response.json()["status"] == expected_status, response.json()
    health = client.get("/health").json()
    assert health["version"] == "0.1.0-day13"
    assert health["modules"]["orchestration"] == "day13_prefect_local_dag_ready"
    assert health["modules"]["observability"] == "day13_ops_metrics_ready"
    assert health["modules"]["backup_restore"] == "day13_backup_restore_smoke_ready"

    acceptance = run_acceptance()
    assert acceptance["status"] == "ok"
    assert acceptance["checks"] >= 28
    assert acceptance["failed"] == []


def test_day13_research_console_ops_page_and_route_validation_are_ready():
    ops_page = FRONTEND_APP / "ops" / "page.tsx"
    assert ops_page.is_file()
    page = ops_page.read_text(encoding="utf-8")
    assert "ArtifactStatusCard" in page
    assert "/api/ops" in page
    assert "prefect-local" in page
    assert "backfill dry-run" in page
    assert "Spark/Flink/Kafka/ClickHouse/PostgreSQL/Redis" in page
    assert "backup/restore" in page
    assert "research_signals_only_not_investment_advice" in page

    registry = (PROJECT_ROOT / "frontend" / "src" / "lib" / "researchConsoleData.ts").read_text(encoding="utf-8")
    assert "ops" in registry
    assert "reports/day13/day13_ops_acceptance_report.json" in registry
    assert "config_hash" in registry and "dataset_snapshot_manifest" in registry

    validate_script = (PROJECT_ROOT / "frontend" / "scripts" / "validate_routes.mjs").read_text(encoding="utf-8")
    assert "ops/page.tsx" in validate_script
