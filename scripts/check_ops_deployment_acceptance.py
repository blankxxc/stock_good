from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
REPORT_DIR = ROOT / "reports" / "ops_deployment"


def run_acceptance() -> dict[str, Any]:
    from backend.app.main import app
    from ops.ops_deployment_ops import build_ops_deployment_artifacts

    checks: list[dict[str, Any]] = []

    def check(name: str, ok: bool, detail: Any = None) -> None:
        checks.append({"name": name, "status": "passed" if ok else "failed", "detail": detail})

    payload = build_ops_deployment_artifacts()
    check("payload_status", payload["status"] == "ops_deployment_ops_deployment_ready", payload.get("status"))
    check("config_hash", len(payload["config"]["config_hash"]) == 64, payload["config"].get("config_hash"))
    check("resolved_config_written", (ROOT / payload["config"]["resolved_config_path"]).is_file(), payload["config"].get("resolved_config_path"))
    resolved_text = (ROOT / payload["config"]["resolved_config_path"]).read_text(encoding="utf-8")
    check("resolved_config_no_secret_tokens", all(token not in resolved_text.lower() for token in ["api_key", "password", "bearer", "ghp_", "sk-"]), None)
    check("single_orchestrator", payload["orchestration"]["orchestrator"] == "prefect-local", payload["orchestration"].get("orchestrator"))
    check("mvp_dag_count", len(payload["orchestration"]["mvp_dag"]) == 15, len(payload["orchestration"]["mvp_dag"]))
    check("extended_dag_count", len(payload["orchestration"]["extended_dag"]) == 9, len(payload["orchestration"]["extended_dag"]))
    check("backfill_dry_run", payload["backfill_request"]["status"] == "dry_run_passed", payload["backfill_request"])
    check("backfill_no_overwrite", payload["backfill_request"]["dry_run_result"]["would_overwrite_formal_report_snapshot"] is False, payload["backfill_request"]["dry_run_result"])
    check("snapshot_manifest_ready", payload["dataset_snapshot_manifest"]["status"] == "recoverable_snapshot_manifest_ready", payload["dataset_snapshot_manifest"])
    check("observability_sections", all(payload["observability"].get(key) for key in ["data_metrics", "task_metrics", "model_metrics", "system_metrics"]), payload["observability"].keys())
    check("component_health", len(payload["observability"]["component_health"]) >= 6, payload["observability"].get("component_health"))
    check("ci_gates", len(payload["ci_cd"]["gates"]) >= 16, payload["ci_cd"].get("gates"))
    check("backup_assets", len(payload["deployment"]["backup_assets"]) >= 10, payload["deployment"].get("backup_assets"))

    required_files = [
        ".github/workflows/ci.yml",
        "deploy/docker/docker-compose.yml",
        "deploy/docker/.env.example",
        "deploy/proxy/Caddyfile",
        "deploy/k8s/ops_deployment-platform.yaml",
        "deploy/backup/backup_ops_deployment.sh",
        "deploy/backup/restore_ops_deployment.sh",
        "deploy/monitoring/prometheus.yml",
        "deploy/monitoring/grafana/ops_deployment_ops_dashboard.json",
        "frontend/src/app/ops/page.tsx",
    ]
    missing = [rel for rel in required_files if not (ROOT / rel).is_file()]
    check("deployment_files", not missing, missing)

    pipeline = subprocess.run([sys.executable, "scripts/run_ops_deployment_pipeline.py", "--dry-run"], cwd=ROOT, text=True, capture_output=True, timeout=180)
    check("one_click_pipeline_dry_run", pipeline.returncode == 0 and "dry_run_passed" in pipeline.stdout, pipeline.stderr + pipeline.stdout)
    compose = subprocess.run(["docker", "compose", "-f", "deploy/docker/docker-compose.yml", "config", "--services"], cwd=ROOT, text=True, capture_output=True, timeout=120)
    check("docker_compose_config", compose.returncode == 0 and "backend" in compose.stdout and "grafana" in compose.stdout, compose.stderr + compose.stdout)
    backup = subprocess.run(["sh", "deploy/backup/backup_ops_deployment.sh", "--smoke"], cwd=ROOT, text=True, capture_output=True, timeout=120)
    restore = subprocess.run(["sh", "deploy/backup/restore_ops_deployment.sh", "--smoke"], cwd=ROOT, text=True, capture_output=True, timeout=120)
    check("backup_smoke", backup.returncode == 0 and "backup_smoke_passed" in backup.stdout, backup.stderr + backup.stdout)
    check("restore_smoke", restore.returncode == 0 and "restore_smoke_passed" in restore.stdout, restore.stderr + restore.stdout)

    client = TestClient(app)
    endpoints = {
        "/health": "ok",
        "/api/ops": "ops_deployment_ops_deployment_ready",
        "/api/orchestration": "ops_deployment_orchestration_ready",
        "/api/backfill": "ops_deployment_backfill_dry_run_ready",
        "/api/observability": "ops_deployment_observability_ready",
        "/api/deployment": "ops_deployment_deployment_backup_ready",
    }
    for path, expected in endpoints.items():
        resp = client.get(path)
        check(f"api_{path}", resp.status_code == 200 and resp.json().get("status") == expected, resp.json() if resp.status_code == 200 else resp.text)
    health = client.get("/health").json()
    check("health_ops_deployment_modules", health.get("version") in {"0.1.0-ops_deployment", "0.1.0-final_acceptance"} and health.get("modules", {}).get("orchestration") == "ops_deployment_prefect_local_dag_ready", health)

    page = (ROOT / "frontend" / "src" / "app" / "ops" / "page.tsx").read_text(encoding="utf-8")
    registry = (ROOT / "frontend" / "src" / "lib" / "researchConsoleData.ts").read_text(encoding="utf-8")
    check("ops_page", "/api/ops" in page and "backfill dry-run" in page and "backup/restore" in page, page[:300])
    check("ops_registry", "reports/ops_deployment/ops_deployment_ops_acceptance_report.json" in registry and "config_hash" in registry, None)

    failed = [item for item in checks if item["status"] != "passed"]
    report = {
        "status": "ok" if not failed else "failed",
        "checks": len(checks),
        "failed": failed,
        "orchestrator": payload["orchestration"]["orchestrator"],
        "mvp_task_count": len(payload["orchestration"]["mvp_dag"]),
        "extended_task_count": len(payload["orchestration"]["extended_dag"]),
        "config_hash": payload["config"]["config_hash"],
        "backfill_status": payload["backfill_request"]["status"],
        "component_count": len(payload["observability"]["component_health"]),
        "ci_gate_count": len(payload["ci_cd"]["gates"]),
        "backup_asset_count": len(payload["deployment"]["backup_assets"]),
    }
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    (REPORT_DIR / "acceptance_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return report


if __name__ == "__main__":
    raise SystemExit(0 if run_acceptance()["status"] == "ok" else 1)
