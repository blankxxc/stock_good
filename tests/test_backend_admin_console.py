from __future__ import annotations

from fastapi.testclient import TestClient

from tests.auth_helpers import authenticated_admin_client

from backend.app.main import app, should_expose_api_docs


def test_production_api_docs_are_closed_unless_explicitly_enabled(monkeypatch) -> None:
    monkeypatch.delenv("STOCK_GOOD_EXPOSE_API_DOCS", raising=False)
    assert should_expose_api_docs("local", None) is True
    assert should_expose_api_docs("production", None) is False
    assert should_expose_api_docs("production", "true") is True
    assert should_expose_api_docs("local", "false") is False


def test_fastapi_backend_admin_overview_api_exposes_control_plane_contract() -> None:
    client = authenticated_admin_client(app)

    response = client.get("/api/admin/overview")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "backend_admin_console_ready"
    assert payload["framework"]["name"] == "FastAPI"
    assert payload["framework"]["selection_reason"]
    assert payload["service"]["name"] == "stock-research-platform"
    assert payload["service"]["research_boundary"] == "research_signals_only_not_investment_advice"
    assert payload["module_summary"]["total_modules"] >= 20
    assert payload["module_summary"]["ready_modules"] >= 20
    assert payload["factor_summary"]["factor_count"] >= 70
    assert payload["factor_summary"]["catalog_count"] >= 70
    assert payload["factor_summary"]["category_count"] >= 6
    assert any(item["path"] == "/docs" for item in payload["documentation_links"])
    assert any(item["path"] == "/api/factors" for item in payload["critical_routes"])
    assert payload["data_fabric"]["visibility"] == "backend_admin_only"
    assert {"/api/data-quality", "/api/lineage", "/api/lakehouse", "/api/spark-jobs", "/api/realtime", "/api/flink-jobs"}.issubset(
        {item["path"] for item in payload["data_fabric"]["internal_routes"]}
    )
    assert payload["frontend_policy"]["public_positioning"] == "user_stock_selection_platform"
    assert payload["frontend_policy"]["hide_data_fabric_from_user_nav"] is True


def test_fastapi_backend_admin_console_renders_html_dashboard() -> None:
    client = authenticated_admin_client(app)

    response = client.get("/admin")

    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    html = response.text
    assert "FastAPI 后端控制台" in html
    assert "backend_admin_console_ready" in html
    assert "模块健康" in html
    assert "因子库摘要" in html
    assert "Data Fabric 内部管理" in html
    assert "/api/data-quality" in html
    assert "/api/lineage" in html
    assert "/api/lakehouse" in html
    assert "/docs" in html
    assert "/api/factors" in html
    assert "非投资建议" in html
