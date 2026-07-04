from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

PROJECT_ROOT = Path(__file__).resolve().parents[1]
FRONTEND_APP = PROJECT_ROOT / "frontend" / "src" / "app"
USER_VISIBLE_ROUTES = ["scores", "condition-screen", "backtests", "factors"]
INTERNAL_DATA_FABRIC_ROUTES = ["dashboard", "data-quality", "lineage", "lakehouse", "spark-jobs", "realtime", "flink-jobs", "ops"]
INTERNAL_GOVERNANCE_ROUTES = ["rag", "simulation", "reports", "settings/licenses", "settings/users", "settings/audit"]
PUBLIC_ROUTES = ["capabilities", "methodology", "data-security", "backtest-risk", "login"]
FORBIDDEN_COPY = ["AI 荐股", "今日牛股", "稳赚", "买入卖出建议", "目标价", "一键跟投"]
FORBIDDEN_USER_NAV = ["Data Fabric", "数据工程", "/dashboard", "/data-quality", "/lineage", "/lakehouse", "/spark-jobs", "/realtime", "/flink-jobs", "/ops", "Research Console"]


def _read_page(route: str) -> str:
    return (FRONTEND_APP / route / "page.tsx").read_text(encoding="utf-8")


def test_public_stock_selection_site_hides_internal_data_fabric_from_user_navigation():
    home = (FRONTEND_APP / "page.tsx").read_text(encoding="utf-8")
    layout = (FRONTEND_APP / "layout.tsx").read_text(encoding="utf-8")
    css = (FRONTEND_APP / "globals.css").read_text(encoding="utf-8")
    combined = home + layout + css

    for route in PUBLIC_ROUTES:
        path = FRONTEND_APP / route / "page.tsx"
        assert path.is_file(), route
        combined += path.read_text(encoding="utf-8")

    assert "MarketOverviewBoard" in home
    assert "智能选股平台" not in home
    assert "简单选股" not in home
    assert "选股辅助" not in home
    assert "智能选股研究平台" not in home
    assert "量化研究控制台" not in home
    assert "投研实验工作台" not in home
    assert "Research Console" not in layout
    assert "fixed-disclaimer" in layout
    assert "沪深300 · 概率评分 · 条件筛选 · 回测风险" in layout
    assert "CSI300 · Stock Selection · Multi-Horizon Scores · Risk Check" not in layout
    assert "position: sticky; bottom: 0" not in css
    assert "professional-shell" in css
    assert "artifact-backed" in combined
    for route in USER_VISIBLE_ROUTES:
        assert f"/{route}" in layout
    for forbidden in FORBIDDEN_USER_NAV:
        assert forbidden not in layout
    for forbidden in FORBIDDEN_COPY:
        assert forbidden not in combined


def test_internal_data_fabric_pages_exist_but_are_not_user_navigation_items():
    layout = (FRONTEND_APP / "layout.tsx").read_text(encoding="utf-8")
    proxy = (PROJECT_ROOT / "frontend" / "src" / "proxy.ts").read_text(encoding="utf-8")
    for route in INTERNAL_DATA_FABRIC_ROUTES + INTERNAL_GOVERNANCE_ROUTES:
        assert (FRONTEND_APP / route / "page.tsx").is_file(), route
        assert f"/{route}" not in layout, route
    for route in INTERNAL_DATA_FABRIC_ROUTES:
        assert f"/{route}" in proxy, route
    assert "127.0.0.1:8000/admin" in proxy


def test_user_visible_pages_have_safe_stock_selection_positioning():
    assert (PROJECT_ROOT / "frontend" / "src" / "components" / "ArtifactStatusCard.tsx").is_file()
    assert (PROJECT_ROOT / "frontend" / "src" / "lib" / "researchConsoleData.ts").is_file()
    for route in USER_VISIBLE_ROUTES:
        page = _read_page(route)
        assert "artifact-backed" in page or "/api/" in page, route
        for forbidden in FORBIDDEN_COPY:
            assert forbidden not in page, route

    validate_script = (PROJECT_ROOT / "frontend" / "scripts" / "validate_routes.mjs").read_text(encoding="utf-8")
    for route in PUBLIC_ROUTES + USER_VISIBLE_ROUTES:
        assert f"{route}/page.tsx" in validate_script
    assert "internalBackendOnlyRoutes" in validate_script
    assert "data_fabric_policy" in validate_script


def test_scores_page_surfaces_multi_horizon_probability_table_contract():
    page = _read_page("scores")
    component = (PROJECT_ROOT / "frontend" / "src" / "components" / "HorizonProbabilityTable.tsx").read_text(encoding="utf-8")
    combined = page + component
    config = (PROJECT_ROOT / "frontend" / "src" / "lib" / "researchConsoleData.ts").read_text(encoding="utf-8")
    assert "HorizonProbabilityTable" in page
    assert "未来1d" in combined and "未来5d" in combined and "未来14d" in combined
    assert "available_horizons" in component
    assert "horizon_rankings" in component
    assert "probability_up" in component
    assert "section-heading-row" not in page
    assert "上涨概率排行与研究候选池" not in page
    assert "查看未来1d、未来5d、未来14d 的上涨概率 Top10" not in page
    assert "terminal-strip" not in page
    assert "验收兼容说明" not in page
    assert "API path prefix" not in page
    assert "保留5d兼容口径" not in page
    assert "1d" in config and "5d" in config and "14d" in config


def test_research_site_site_api_acceptance_and_status_payload_are_ready():
    from backend.app.main import app
    from scripts.check_research_site_acceptance import run_acceptance

    client = TestClient(app)
    site = client.get("/api/site")
    health = client.get("/health")
    assert site.status_code == 200
    payload = site.json()
    assert payload["status"] == "research_site_site_productized_ready"
    assert payload["public_route_count"] >= len(PUBLIC_ROUTES)
    assert payload["user_visible_route_count"] >= len(USER_VISIBLE_ROUTES)
    assert payload["frontend_data_fabric_visible"] is False
    assert payload["backend_data_fabric_location"] == "/admin"
    assert payload["public_positioning"] == "user_stock_selection_platform"
    assert payload["forbidden_copy_check"] == "passed"
    assert payload["visual_system"] == "securities_style_stock_selection_light"
    assert health.status_code == 200
    assert health.json()["modules"]["site"] == "research_site_productized_research_console_ready"

    acceptance = run_acceptance()
    assert acceptance["status"] == "ok"
    assert acceptance["checks"] >= 16
    assert acceptance["failed"] == []
    assert json.loads((PROJECT_ROOT / "reports" / "research_site" / "acceptance_report.json").read_text(encoding="utf-8"))["status"] == "ok"
