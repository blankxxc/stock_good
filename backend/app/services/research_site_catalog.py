from __future__ import annotations

from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[3]
FRONTEND_APP = PROJECT_ROOT / "frontend" / "src" / "app"

PUBLIC_ROUTES = ["capabilities", "methodology", "data-security", "backtest-risk", "login"]
USER_VISIBLE_ROUTES = ["scores", "condition-screen", "backtests", "factors", "models", "graph"]
INTERNAL_DATA_FABRIC_ROUTES = ["dashboard", "data-quality", "lineage", "lakehouse", "spark-jobs", "realtime", "flink-jobs", "ops"]
INTERNAL_GOVERNANCE_ROUTES = ["rag", "simulation", "reports", "settings/licenses", "settings/users", "settings/audit"]
FORBIDDEN_COPY = ["AI 荐股", "今日牛股", "稳赚", "买入卖出建议", "目标价", "一键跟投"]
FORBIDDEN_USER_NAV = ["Data Fabric", "数据工程", "/dashboard", "/data-quality", "/lineage", "/lakehouse", "/spark-jobs", "/realtime", "/flink-jobs", "/ops", "Research Console"]


def _page_text(route: str) -> str:
    path = FRONTEND_APP / route / "page.tsx" if route else FRONTEND_APP / "page.tsx"
    return path.read_text(encoding="utf-8")


def site_payload(research_boundary: str) -> dict[str, Any]:
    layout = (FRONTEND_APP / "layout.tsx").read_text(encoding="utf-8")
    page_texts = [_page_text("")] + [_page_text(route) for route in PUBLIC_ROUTES + USER_VISIBLE_ROUTES]
    combined_public = "\n".join(page_texts + [layout])
    user_nav_forbidden_hits = [token for token in FORBIDDEN_USER_NAV if token in layout]
    forbidden_copy_hits = [word for word in FORBIDDEN_COPY if word in combined_public]
    data_fabric_routes = [
        {"route": "/dashboard", "api": "/api/dashboard", "status": "backend_admin_only"},
        {"route": "/data-quality", "api": "/api/data-quality", "status": "backend_admin_only"},
        {"route": "/lineage", "api": "/api/lineage", "status": "backend_admin_only"},
        {"route": "/lakehouse", "api": "/api/lakehouse", "status": "backend_admin_only"},
        {"route": "/spark-jobs", "api": "/api/spark-jobs", "status": "backend_admin_only"},
        {"route": "/realtime", "api": "/api/realtime", "status": "backend_admin_only"},
        {"route": "/flink-jobs", "api": "/api/flink-jobs", "status": "backend_admin_only"},
        {"route": "/ops", "api": "/api/ops", "status": "backend_admin_only"},
    ]
    return {
        "module": "site",
        "status": "research_site_site_productized_ready",
        "version": "0.2.0-user_stock_selection_boundary",
        "research_boundary": research_boundary,
        "public_positioning": "user_stock_selection_platform",
        "visual_system": "securities_style_stock_selection_light",
        "public_route_count": len(PUBLIC_ROUTES),
        "user_visible_route_count": len(USER_VISIBLE_ROUTES),
        "internal_data_fabric_route_count": len(INTERNAL_DATA_FABRIC_ROUTES),
        "internal_governance_route_count": len(INTERNAL_GOVERNANCE_ROUTES),
        "frontend_data_fabric_visible": bool(user_nav_forbidden_hits),
        "backend_data_fabric_location": "/admin",
        "data_fabric_policy": "backend_admin_only_not_user_facing",
        "data_fabric_routes": data_fabric_routes,
        "data_security_policy": {
            "hide_internal_lineage_from_user_nav": True,
            "hide_lakehouse_streaming_ops_from_user_nav": True,
            "public_pages_show_only_user_safe_selection_data": True,
            "backend_admin_owns_data_fabric": True,
        },
        "forbidden_user_nav_hits": user_nav_forbidden_hits,
        "forbidden_copy_check": "failed" if forbidden_copy_hits else "passed",
        "forbidden_copy_hits": forbidden_copy_hits,
        "fixed_disclaimer": "selection_assist_not_investment_advice",
    }
