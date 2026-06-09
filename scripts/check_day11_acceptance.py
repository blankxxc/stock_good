from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
FRONTEND_APP = ROOT / "frontend" / "src" / "app"
REPORT_DIR = ROOT / "reports" / "day11"
PUBLIC_ROUTES = ["capabilities", "methodology", "data-security", "backtest-risk", "rag-evidence", "architecture-roadmap", "login"]
CONSOLE_ROUTES = [
    "dashboard", "scores", "candidates", "backtests", "factors", "experiments", "rag", "data-quality", "lineage", "lakehouse",
    "spark-jobs", "realtime", "flink-jobs", "graph", "models", "simulation", "reports", "settings/licenses", "settings/users", "settings/audit"
]
FORBIDDEN_COPY = ["AI 荐股", "今日牛股", "稳赚", "买入卖出建议", "目标价", "一键跟投"]


def _page_path(route: str) -> Path:
    return FRONTEND_APP / route / "page.tsx" if route else FRONTEND_APP / "page.tsx"


def _read(route: str) -> str:
    return _page_path(route).read_text(encoding="utf-8")


def run_acceptance() -> dict[str, Any]:
    from backend.app.main import app

    checks: list[dict[str, Any]] = []

    def check(name: str, ok: bool, detail: Any = None) -> None:
        checks.append({"name": name, "status": "passed" if ok else "failed", "detail": detail})

    all_routes = [""] + PUBLIC_ROUTES + CONSOLE_ROUTES
    missing = [route or "home" for route in all_routes if not _page_path(route).is_file()]
    check("all_pages_openable_by_route_files", not missing, missing)
    check("public_and_console_route_counts", len(PUBLIC_ROUTES) == 7 and len(CONSOLE_ROUTES) == 20, {"public": len(PUBLIC_ROUTES), "console": len(CONSOLE_ROUTES)})

    extra_texts = [
        (FRONTEND_APP / "layout.tsx").read_text(encoding="utf-8"),
        (ROOT / "frontend" / "src" / "lib" / "researchConsoleData.ts").read_text(encoding="utf-8"),
    ]
    combined = "\n".join([_read(route) for route in all_routes] + extra_texts)
    check("required_public_positioning_copy", all(text in _read("") for text in ["智能选股研究平台", "量化研究控制台", "投研实验工作台", "横截面评分与回测分析平台"]), None)
    check("forbidden_copy_absent", not any(word in combined for word in FORBIDDEN_COPY), [w for w in FORBIDDEN_COPY if w in combined])
    check("visual_system_css_ready", "professional-shell" in (FRONTEND_APP / "globals.css").read_text(encoding="utf-8"), None)
    check("fixed_disclaimer_visible", "fixed-disclaimer" in (FRONTEND_APP / "layout.tsx").read_text(encoding="utf-8"), None)
    check("artifact_status_component_ready", (ROOT / "frontend" / "src" / "components" / "ArtifactStatusCard.tsx").is_file(), None)
    check("research_console_data_registry_ready", (ROOT / "frontend" / "src" / "lib" / "researchConsoleData.ts").is_file(), None)

    artifact_pages = [route for route in CONSOLE_ROUTES if "ArtifactStatusCard" in _read(route) and "/api/" in _read(route) and ("data_mode" in _read(route) or "artifact-backed" in _read(route))]
    check("console_pages_artifact_backed", len(artifact_pages) == len(CONSOLE_ROUTES), {"actual": len(artifact_pages), "expected": len(CONSOLE_ROUTES)})
    check("spark_lakehouse_realtime_entries", all(token in combined for token in ["/spark-jobs", "/api/spark-jobs", "/lakehouse", "/api/lakehouse", "/realtime", "/api/realtime", "/flink-jobs", "/api/flink-jobs"]), None)

    client = TestClient(app)
    api_paths = ["/health", "/api/site", "/api/dashboard", "/api/lakehouse", "/api/spark-jobs", "/api/realtime", "/api/flink-jobs", "/api/rag", "/api/models"]
    responses = {path: client.get(path).status_code for path in api_paths}
    check("api_smoke_status_200", all(code == 200 for code in responses.values()), responses)
    site_payload = client.get("/api/site").json()
    health = client.get("/health").json()
    check("site_payload_ready", site_payload.get("status") == "day11_site_productized_ready", site_payload)
    check("health_site_module_ready", health.get("modules", {}).get("site") == "day11_productized_research_console_ready", health.get("modules", {}).get("site"))
    check("site_forbidden_copy_gate", site_payload.get("forbidden_copy_check") == "passed", site_payload.get("forbidden_copy_check"))
    check("site_counts", site_payload.get("public_route_count", 0) >= len(PUBLIC_ROUTES) and site_payload.get("console_route_count", 0) >= len(CONSOLE_ROUTES), site_payload)
    check("site_state_entries", site_payload.get("spark_lakehouse_realtime_visible") is True, site_payload.get("route_cards"))

    failed = [item for item in checks if item["status"] != "passed"]
    report = {
        "status": "ok" if not failed else "failed",
        "checks": len(checks),
        "failed": failed,
        "public_route_count": len(PUBLIC_ROUTES),
        "console_route_count": len(CONSOLE_ROUTES),
        "artifact_backed_pages": len(artifact_pages),
        "api_paths_checked": api_paths,
        "visual_system": "professional_research_saas_light",
    }
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    (REPORT_DIR / "acceptance_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return report


if __name__ == "__main__":
    raise SystemExit(0 if run_acceptance()["status"] == "ok" else 1)
