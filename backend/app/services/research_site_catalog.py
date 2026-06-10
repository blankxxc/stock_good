from __future__ import annotations

from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[3]
FRONTEND_APP = PROJECT_ROOT / "frontend" / "src" / "app"

PUBLIC_ROUTES = ["capabilities", "methodology", "data-security", "backtest-risk", "rag-evidence", "architecture-roadmap", "login"]
CONSOLE_ROUTES = [
    "dashboard", "scores", "candidates", "backtests", "factors", "experiments", "rag", "data-quality", "lineage", "lakehouse",
    "spark-jobs", "realtime", "flink-jobs", "graph", "models", "simulation", "reports", "settings/licenses", "settings/users", "settings/audit"
]
FORBIDDEN_COPY = ["AI 荐股", "今日牛股", "稳赚", "买入卖出建议", "目标价", "一键跟投"]


def _page_text(route: str) -> str:
    path = FRONTEND_APP / route / "page.tsx" if route else FRONTEND_APP / "page.tsx"
    return path.read_text(encoding="utf-8")


def site_payload(research_boundary: str) -> dict[str, Any]:
    page_texts = [_page_text("")] + [_page_text(route) for route in PUBLIC_ROUTES + CONSOLE_ROUTES]
    extra_texts = [
        (FRONTEND_APP / "layout.tsx").read_text(encoding="utf-8"),
        (PROJECT_ROOT / "frontend" / "src" / "lib" / "researchConsoleData.ts").read_text(encoding="utf-8"),
    ]
    combined = "\n".join(page_texts + extra_texts)
    artifact_backed_pages = sum("ArtifactStatusCard" in _page_text(route) for route in CONSOLE_ROUTES)
    route_cards = [
        {"route": "/lakehouse", "api": "/api/lakehouse", "status": "lakehouse_snapshot_visible"},
        {"route": "/spark-jobs", "api": "/api/spark-jobs", "status": "spark_jobs_visible"},
        {"route": "/realtime", "api": "/api/realtime", "status": "realtime_status_visible"},
        {"route": "/flink-jobs", "api": "/api/flink-jobs", "status": "flink_jobs_visible"},
    ]
    return {
        "module": "site",
        "status": "research_site_site_productized_ready",
        "version": "0.1.0-research_site",
        "research_boundary": research_boundary,
        "visual_system": "professional_research_saas_light",
        "public_route_count": len(PUBLIC_ROUTES),
        "console_route_count": len(CONSOLE_ROUTES),
        "artifact_backed_pages": artifact_backed_pages,
        "spark_lakehouse_realtime_visible": all(card["route"] in combined and card["api"] in combined for card in route_cards),
        "route_cards": route_cards,
        "data_mode_policy": "synthetic/demo data must be labeled by data_mode; main cards bind /api/* and artifacts",
        "forbidden_copy_check": "failed" if any(word in combined for word in FORBIDDEN_COPY) else "passed",
        "fixed_disclaimer": "research_only_not_investment_advice",
    }
