from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

PROJECT_ROOT = Path(__file__).resolve().parents[1]
FRONTEND_APP = PROJECT_ROOT / "frontend" / "src" / "app"
CONSOLE_ROUTES = [
    "dashboard",
    "scores",
    "candidates",
    "backtests",
    "factors",
    "experiments",
    "rag",
    "data-quality",
    "lineage",
    "lakehouse",
    "spark-jobs",
    "realtime",
    "flink-jobs",
    "graph",
    "models",
    "simulation",
    "reports",
    "settings/licenses",
    "settings/users",
    "settings/audit",
]
PUBLIC_ROUTES = [
    "capabilities",
    "methodology",
    "data-security",
    "backtest-risk",
    "rag-evidence",
    "architecture-roadmap",
    "login",
]
FORBIDDEN_COPY = ["AI 荐股", "今日牛股", "稳赚", "买入卖出建议", "目标价", "一键跟投"]


def _read_page(route: str) -> str:
    return (FRONTEND_APP / route / "page.tsx").read_text(encoding="utf-8")


def test_day11_public_website_layer_routes_and_compliance_copy_are_ready():
    home = (FRONTEND_APP / "page.tsx").read_text(encoding="utf-8")
    layout = (FRONTEND_APP / "layout.tsx").read_text(encoding="utf-8")
    css = (FRONTEND_APP / "globals.css").read_text(encoding="utf-8")
    combined = home + layout + css

    for route in PUBLIC_ROUTES:
        path = FRONTEND_APP / route / "page.tsx"
        assert path.is_file(), route
        combined += path.read_text(encoding="utf-8")

    assert "智能选股研究平台" in home
    assert "量化研究控制台" in home
    assert "投研实验工作台" in home
    assert "横截面评分与回测分析平台" in home
    assert "官网层" in home
    assert "Research Console" in layout
    assert "fixed-disclaimer" in layout
    assert "professional-shell" in css
    assert "artifact-backed" in combined
    assert "/dashboard" in layout and "/spark-jobs" in layout and "/lakehouse" in layout and "/realtime" in layout
    for forbidden in FORBIDDEN_COPY:
        assert forbidden not in combined


def test_day11_research_console_pages_have_artifact_backed_main_cards():
    assert (PROJECT_ROOT / "frontend" / "src" / "components" / "ArtifactStatusCard.tsx").is_file()
    assert (PROJECT_ROOT / "frontend" / "src" / "lib" / "researchConsoleData.ts").is_file()
    for route in CONSOLE_ROUTES:
        page = _read_page(route)
        assert "ArtifactStatusCard" in page, route
        assert "data_mode" in page or "artifact-backed" in page, route
        assert "/api/" in page, route
        for forbidden in FORBIDDEN_COPY:
            assert forbidden not in page, route

    validate_script = (PROJECT_ROOT / "frontend" / "scripts" / "validate_routes.mjs").read_text(encoding="utf-8")
    for route in PUBLIC_ROUTES:
        assert f"{route}/page.tsx" in validate_script


def test_day11_site_api_acceptance_and_status_payload_are_ready():
    from backend.app.main import app
    from scripts.check_day11_acceptance import run_acceptance

    client = TestClient(app)
    site = client.get("/api/site")
    health = client.get("/health")
    assert site.status_code == 200
    payload = site.json()
    assert payload["status"] == "day11_site_productized_ready"
    assert payload["public_route_count"] >= len(PUBLIC_ROUTES)
    assert payload["console_route_count"] >= len(CONSOLE_ROUTES)
    assert payload["artifact_backed_pages"] >= len(CONSOLE_ROUTES)
    assert payload["spark_lakehouse_realtime_visible"] is True
    assert payload["forbidden_copy_check"] == "passed"
    assert payload["visual_system"] == "professional_research_saas_light"
    assert health.status_code == 200
    assert health.json()["modules"]["site"] == "day11_productized_research_console_ready"

    acceptance = run_acceptance()
    assert acceptance["status"] == "ok"
    assert acceptance["checks"] >= 16
    assert acceptance["failed"] == []
    assert json.loads((PROJECT_ROOT / "reports" / "day11" / "acceptance_report.json").read_text(encoding="utf-8"))["status"] == "ok"
