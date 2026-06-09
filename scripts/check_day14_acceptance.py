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
REPORT_DIR = ROOT / "reports" / "day14"


def run_acceptance() -> dict[str, Any]:
    from backend.app.main import app
    from ops.day14_final import DEMO_ASSETS, REQUIRED_DOCS, build_day14_final_artifacts

    checks: list[dict[str, Any]] = []

    def check(name: str, ok: bool, detail: Any = None) -> None:
        checks.append({"name": name, "status": "passed" if ok else "failed", "detail": detail})

    payload = build_day14_final_artifacts(write_report=True)
    check("payload_status", payload["status"] == "day14_final_acceptance_ready", payload.get("status"))
    check("completed_days", payload["completed_days"] == 14, payload.get("completed_days"))
    check("coverage_area_count", payload["coverage_area_count"] >= 30, payload.get("coverage_area_count"))
    check("release_gate_status", payload["release_gate_status"] == "passed", payload.get("release_gate_status"))
    check("blocked_reasons_present", payload["blocked_reason_count"] >= 1, payload.get("blocked_reasons"))
    check("artifact_hash", len(payload["artifact_hash"]) == 64, payload.get("artifact_hash"))

    area_names = {item["area"] for item in payload["coverage_matrix"]}
    required_areas = {
        "data_ingestion", "spark_batch", "lakehouse_format", "lakehouse_layers", "clickhouse_olap",
        "kafka_redpanda", "flink_realtime", "online_feature_store", "offline_factors", "realtime_factors",
        "event_factors", "market_regime", "relation_graph", "propagation_factors", "labels", "leakage_check",
        "baseline_model", "advanced_models", "backtest", "risk_attribution", "rag_evidence", "website",
        "simulation", "rbac", "audit", "license_gate", "report_export", "observability", "deployment", "documentation",
    }
    check("coverage_matrix_required_areas", required_areas.issubset(area_names), sorted(required_areas - area_names))
    check("coverage_matrix_status_values", all(item["status"] in {"passed", "partial", "research_candidate_only"} for item in payload["coverage_matrix"]), payload["coverage_matrix"])

    missing_docs = [rel for rel in REQUIRED_DOCS if not (ROOT / rel).is_file()]
    missing_demo = [rel for rel in DEMO_ASSETS if not (ROOT / rel).is_file()]
    check("required_docs", not missing_docs, missing_docs)
    check("demo_assets", not missing_demo, missing_demo)

    final_report = (ROOT / "docs/final_acceptance_report.md").read_text(encoding="utf-8")
    for token in ["Day 1", "Day 14", "完成状态", "成熟度", "剩余风险", "blocked reason", "不是 AI 荐股网站"]:
        check(f"final_report_token_{token}", token in final_report, token)
    coverage_doc = (ROOT / "docs/demo/coverage_matrix.md").read_text(encoding="utf-8")
    for token in ["Spark", "Lakehouse", "Flink", "RAG", "风险归因", "导出合规"]:
        check(f"coverage_doc_token_{token}", token in coverage_doc, token)
    risk_doc = (ROOT / "docs/risk_register.md").read_text(encoding="utf-8")
    for token in ["Spark", "Flink", "高级模型", "许可证", "实盘"]:
        check(f"risk_register_token_{token}", token in risk_doc, token)

    gates = payload["release_gates"]
    for gate in ["no_broker_integration", "no_trading_advice_wording", "license_gate_before_export", "rag_citation_required", "point_in_time_required", "manual_review_required_before_real_use"]:
        check(f"release_gate_{gate}", gates.get(gate) == "passed", gates.get(gate))

    client = TestClient(app)
    endpoints = {
        "/health": "ok",
        "/api/final-acceptance": "day14_final_acceptance_ready",
        "/api/ops": "day13_ops_deployment_ready",
        "/api/reports": "day12_report_export_ready",
        "/api/rag": "day10_rag_evidence_ready",
        "/api/site": "day11_site_productized_ready",
    }
    for path, expected in endpoints.items():
        response = client.get(path)
        body = response.json() if response.status_code == 200 else {"text": response.text}
        check(f"api_{path}", response.status_code == 200 and body.get("status") == expected, body)
    health = client.get("/health").json()
    check("health_day14", health.get("version") == "0.1.0-day14" and health.get("modules", {}).get("final_acceptance") == "day14_final_acceptance_ready", health)

    route = subprocess.run("npm run validate:routes", cwd=ROOT / "frontend", text=True, capture_output=True, timeout=120, shell=True)
    check("frontend_route_validation", route.returncode == 0 and '"route_count": 29' in route.stdout, route.stderr + route.stdout)
    compose = subprocess.run(["docker", "compose", "-f", "deploy/docker/docker-compose.yml", "config", "--services"], cwd=ROOT, text=True, capture_output=True, timeout=120)
    check("docker_compose_config", compose.returncode == 0 and "backend" in compose.stdout and "prometheus" in compose.stdout, compose.stderr + compose.stdout)
    backup = subprocess.run(["sh", "deploy/backup/backup_day13.sh", "--smoke"], cwd=ROOT, text=True, capture_output=True, timeout=120)
    restore = subprocess.run(["sh", "deploy/backup/restore_day13.sh", "--smoke"], cwd=ROOT, text=True, capture_output=True, timeout=120)
    check("backup_smoke", backup.returncode == 0 and "backup_smoke_passed" in backup.stdout, backup.stderr + backup.stdout)
    check("restore_smoke", restore.returncode == 0 and "restore_smoke_passed" in restore.stdout, restore.stderr + restore.stdout)

    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    for token in ["Day 14", "final_acceptance_report.md", "/api/final-acceptance"]:
        check(f"readme_token_{token}", token in readme, token)

    failed = [item for item in checks if item["status"] != "passed"]
    report = {
        "status": "ok" if not failed else "failed",
        "checks": len(checks),
        "failed": failed,
        "final_status": payload["status"],
        "completed_days": payload["completed_days"],
        "coverage_area_count": payload["coverage_area_count"],
        "document_count": payload["document_count"],
        "demo_asset_count": payload["demo_asset_count"],
        "release_gate_status": payload["release_gate_status"],
        "blocked_reason_count": payload["blocked_reason_count"],
    }
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    (REPORT_DIR / "acceptance_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return report


if __name__ == "__main__":
    raise SystemExit(0 if run_acceptance()["status"] == "ok" else 1)
