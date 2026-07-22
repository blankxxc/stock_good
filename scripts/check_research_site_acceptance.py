from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient
from scripts._authenticated_client import acceptance_admin_client

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
FRONTEND_APP = ROOT / "frontend" / "src" / "app"
REPORT_DIR = ROOT / "reports" / "research_site"
PUBLIC_ROUTES = ["capabilities", "methodology", "data-security", "backtest-risk", "login"]
USER_VISIBLE_ROUTES = ["scores", "condition-screen", "backtests", "factors", "models", "graph"]
INTERNAL_DATA_FABRIC_ROUTES = ["dashboard", "data-quality", "lineage", "lakehouse", "spark-jobs", "realtime", "flink-jobs", "ops"]
FORBIDDEN_COPY = ["AI 荐股", "今日牛股", "稳赚", "买入卖出建议", "目标价", "一键跟投"]
FORBIDDEN_USER_NAV = ["Data Fabric", "数据工程", "/dashboard", "/data-quality", "/lineage", "/lakehouse", "/spark-jobs", "/realtime", "/flink-jobs", "/ops", "Research Console"]


def _page_path(route: str) -> Path:
    return FRONTEND_APP / route / "page.tsx" if route else FRONTEND_APP / "page.tsx"


def _read(route: str) -> str:
    return _page_path(route).read_text(encoding="utf-8")


def run_acceptance() -> dict[str, Any]:
    from backend.app.main import app

    checks: list[dict[str, Any]] = []

    def check(name: str, ok: bool, detail: Any = None) -> None:
        checks.append({"name": name, "status": "passed" if ok else "failed", "detail": detail})

    user_routes = [""] + PUBLIC_ROUTES + USER_VISIBLE_ROUTES
    internal_routes = INTERNAL_DATA_FABRIC_ROUTES
    missing_user = [route or "home" for route in user_routes if not _page_path(route).is_file()]
    missing_internal = [route for route in internal_routes if not _page_path(route).is_file()]
    check("user_visible_pages_exist", not missing_user, missing_user)
    check("internal_data_fabric_pages_still_exist_for_compatibility", not missing_internal, missing_internal)
    check("route_counts", len(PUBLIC_ROUTES) == 5 and len(USER_VISIBLE_ROUTES) >= 4 and len(INTERNAL_DATA_FABRIC_ROUTES) >= 7, None)

    layout = (FRONTEND_APP / "layout.tsx").read_text(encoding="utf-8")
    combined_public = "\n".join([_read(route) for route in user_routes] + [layout])
    home = _read("")
    redundant_home_copy = [
        "智能选股平台",
        "简单选股",
        "选股辅助",
        "智能选股研究平台",
        "量化研究控制台",
        "投研实验工作台",
        "market overview binds",
    ]
    check("home_uses_market_overview_without_intro_shell", "MarketOverviewBoard" in home and "home-intro" not in home and "alpha-command-deck" not in home, None)
    check("redundant_home_copy_removed", all(text not in home for text in redundant_home_copy), [text for text in redundant_home_copy if text in home])
    check("data_fabric_not_in_user_navigation", not any(token in layout for token in FORBIDDEN_USER_NAV), [token for token in FORBIDDEN_USER_NAV if token in layout])
    check("forbidden_copy_absent", not any(word in combined_public for word in FORBIDDEN_COPY), [w for w in FORBIDDEN_COPY if w in combined_public])
    check("visual_system_css_ready", "professional-shell" in (FRONTEND_APP / "globals.css").read_text(encoding="utf-8"), None)
    check("fixed_disclaimer_visible", "fixed-disclaimer" in layout and "选股辅助" in layout, None)

    client = acceptance_admin_client(app)
    api_paths = ["/health", "/api/site", "/api/factors", "/api/scores", "/api/condition-screen", "/api/backtests", "/api/admin/overview", "/api/data-quality", "/api/lineage", "/api/lakehouse"]
    responses = {path: client.get(path).status_code for path in api_paths}
    check("api_smoke_status_200", all(code == 200 for code in responses.values()), responses)
    site_payload = client.get("/api/site").json()
    admin_payload = client.get("/api/admin/overview").json()
    admin_html = client.get("/admin").text
    health = client.get("/health").json()
    check("site_payload_ready", site_payload.get("status") == "research_site_site_productized_ready", site_payload)
    check("health_site_module_ready", health.get("modules", {}).get("site") == "research_site_productized_research_console_ready", health.get("modules", {}).get("site"))
    check("site_forbidden_copy_gate", site_payload.get("forbidden_copy_check") == "passed", site_payload.get("forbidden_copy_hits"))
    check("site_user_boundary", site_payload.get("public_positioning") == "user_stock_selection_platform" and site_payload.get("frontend_data_fabric_visible") is False, site_payload)
    check("backend_admin_owns_data_fabric", site_payload.get("backend_data_fabric_location") == "/admin" and admin_payload.get("data_fabric", {}).get("visibility") == "backend_admin_only", admin_payload.get("data_fabric"))
    check("admin_html_shows_data_fabric_internal_management", "Data Fabric 内部管理" in admin_html and "/api/lineage" in admin_html and "/api/lakehouse" in admin_html, None)

    failed = [item for item in checks if item["status"] != "passed"]
    report = {
        "status": "ok" if not failed else "failed",
        "checks": len(checks),
        "failed": failed,
        "public_route_count": len(PUBLIC_ROUTES),
        "user_visible_route_count": len(USER_VISIBLE_ROUTES),
        "internal_data_fabric_route_count": len(INTERNAL_DATA_FABRIC_ROUTES),
        "api_paths_checked": api_paths,
        "visual_system": "securities_style_stock_selection_light",
        "data_fabric_policy": "backend_admin_only",
    }
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    (REPORT_DIR / "acceptance_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return report


if __name__ == "__main__":
    raise SystemExit(0 if run_acceptance()["status"] == "ok" else 1)
