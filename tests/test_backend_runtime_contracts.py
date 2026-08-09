from __future__ import annotations

import inspect
import os
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

import pandas as pd
import pytest
import yaml


def _write_daily_snapshot(path: Path, end_date: str, symbol_count: int = 20) -> None:
    dates = pd.date_range(end=end_date, periods=30, freq="D")
    symbols = [f"{index:06d}.SZ" for index in range(1, symbol_count + 1)]
    rows: list[dict[str, object]] = []
    for day_index, trade_date in enumerate(dates):
        for symbol_index, symbol in enumerate(symbols):
            rows.append(
                {
                    "trade_date": trade_date,
                    "symbol": symbol,
                    "stock_name": f"测试股票{symbol_index + 1}",
                    "name": f"测试股票{symbol_index + 1}",
                    "industry_name": f"测试行业{symbol_index % 4}",
                    "close": 10.0 + symbol_index * 0.2 + day_index * (0.01 + symbol_index * 0.0001),
                }
            )
    path.parent.mkdir(parents=True, exist_ok=True)
    columns = ["trade_date", "symbol", "stock_name", "name", "industry_name", "close"]
    pd.DataFrame(rows, columns=columns).to_parquet(path, index=False)


def _write_relation_edges(path: Path, rows: list[dict[str, object]]) -> None:
    columns = [
        "src_symbol",
        "dst_symbol",
        "relation_type",
        "relation_weight",
        "confidence",
        "direction",
        "as_of_date",
        "start_time",
        "end_time",
        "available_time",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows, columns=columns).to_parquet(path, index=False)


def test_dynamic_catalog_routes_do_not_run_blocking_factories_on_event_loop() -> None:
    from backend.app.main import ROUTE_PAYLOAD_FACTORIES, app

    route_by_path = {getattr(route, "path", ""): route for route in app.routes}
    for module in ROUTE_PAYLOAD_FACTORIES:
        route = route_by_path[f"/api/{module}"]
        assert not inspect.iscoroutinefunction(route.endpoint), (
            f"/api/{module} wraps synchronous catalog work in async def and can block the event loop"
        )


def test_public_catalog_route_cannot_override_module_and_bypass_admin_dependency() -> None:
    from fastapi.testclient import TestClient

    from backend.app.main import app

    route = next(route for route in app.routes if getattr(route, "path", "") == "/api/site")
    assert "module" not in inspect.signature(route.endpoint).parameters

    response = TestClient(app).get("/api/site", params={"module": "dashboard"})
    assert response.status_code == 200
    assert response.json()["module"] == "site"


def test_app_import_fails_fast_for_https_origin_without_secure_cookie() -> None:
    project_root = Path(__file__).resolve().parents[1]
    environment = os.environ.copy()
    environment["STOCK_GOOD_ALLOWED_ORIGINS"] = "https://stocks.example.com"
    environment["STOCK_GOOD_SECURE_COOKIE"] = "false"

    result = subprocess.run(
        [sys.executable, "-c", "import backend.app.main"],
        cwd=project_root,
        env=environment,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )

    assert result.returncode != 0
    assert "STOCK_GOOD_SECURE_COOKIE" in result.stderr


def test_auth_service_accepts_matching_unicode_passwords(tmp_path: Path) -> None:
    from backend.app.services.auth_service import AuthRuntime, AuthService

    service = AuthService(
        AuthRuntime(
            db_path=tmp_path / "auth.db",
            bootstrap_token_path=tmp_path / "bootstrap.txt",
            allowed_origins=("http://testserver",),
            secure_cookie=False,
        )
    )
    password = "安全SecurePass123!"

    result = service.register(
        "unicode.user",
        "Unicode User",
        password,
        password,
        client_key="test-client",
    )
    bootstrap_token = service.runtime.bootstrap_token_path.read_text(encoding="utf-8").strip()
    admin_result = service.setup_admin(
        bootstrap_token,
        "unicode.admin",
        "Unicode Admin",
        password,
        password,
        client_key="test-client",
    )

    assert result["user"]["username"] == "unicode.user"
    assert admin_result["user"]["role"] == "admin"


def test_relation_network_cache_invalidates_when_daily_snapshot_changes(tmp_path: Path) -> None:
    from backend.app.services.relation_graph_network import relation_network_payload

    daily_path = tmp_path / "data" / "real" / "csi300_daily" / "part-000.parquet"
    _write_daily_snapshot(daily_path, "2026-01-30")
    first = relation_network_payload(str(tmp_path))

    previous_mtime = daily_path.stat().st_mtime_ns
    _write_daily_snapshot(daily_path, "2026-02-28")
    os.utime(daily_path, ns=(previous_mtime + 1_000_000_000, previous_mtime + 1_000_000_000))
    second = relation_network_payload(str(tmp_path))

    assert first["as_of_date"] != second["as_of_date"]
    assert second["as_of_date"] > first["as_of_date"]


def test_relation_network_reads_all_edge_parts_and_enforces_as_of_contract(tmp_path: Path) -> None:
    from backend.app.services.relation_graph_network import relation_network_payload

    daily_path = tmp_path / "data" / "real" / "csi300_daily" / "part-000.parquet"
    edge_dir = tmp_path / "data" / "gold" / "stock_relation_edge"
    _write_daily_snapshot(daily_path, "2026-02-28")
    _write_relation_edges(
        edge_dir / "part-000.parquet",
        [
            {
                "src_symbol": "000001.SZ",
                "dst_symbol": "000002.SZ",
                "relation_type": "supply_chain",
                "relation_weight": 0.95,
                "confidence": 0.9,
                "direction": "undirected",
                "as_of_date": "2026-02-10",
                "start_time": "2026-02-01",
                "end_time": "2026-02-15",
                "available_time": "2026-02-10",
            },
            {
                "src_symbol": "000002.SZ",
                "dst_symbol": "000003.SZ",
                "relation_type": "news_cooccur",
                "relation_weight": 0.99,
                "confidence": 0.9,
                "direction": "undirected",
                "as_of_date": "2026-03-10",
                "start_time": "2026-03-10",
                "end_time": None,
                "available_time": "2026-03-10",
            },
        ],
    )
    _write_relation_edges(
        edge_dir / "part-001.parquet",
        [
            {
                "src_symbol": "000001.SZ",
                "dst_symbol": "000002.SZ",
                "relation_type": "supply_chain",
                "relation_weight": 0.35,
                "confidence": 0.85,
                "direction": "undirected",
                "as_of_date": "2026-02-28",
                "start_time": "2026-02-16",
                "end_time": None,
                "available_time": "2026-02-28",
            },
            {
                "src_symbol": "000003.SZ",
                "dst_symbol": "000004.SZ",
                "relation_type": "concept_same",
                "relation_weight": 0.45,
                "confidence": 0.8,
                "direction": "undirected",
                "as_of_date": "2026-02-28",
                "start_time": "2026-02-01",
                "end_time": None,
                "available_time": "2026-02-28",
            },
        ],
    )

    payload = relation_network_payload(str(tmp_path))
    existing_edges = {
        (edge["source"], edge["target"], edge["relation_type"]): edge
        for edge in payload["edges"]
    }

    assert existing_edges[("000001.SZ", "000002.SZ", "supply_chain")]["weight"] == 0.35
    assert ("000003.SZ", "000004.SZ", "concept_same") in existing_edges
    assert all(edge["relation_type"] != "news_cooccur" for edge in payload["edges"])
    assert payload["snapshot"]["edge_file_count"] == 2


@pytest.mark.parametrize("symbol_count", [0, 1, 3, 9, 10])
def test_relation_network_handles_empty_and_small_universes(tmp_path: Path, symbol_count: int) -> None:
    from backend.app.services.relation_graph_network import relation_network_payload

    daily_path = tmp_path / "data" / "real" / "csi300_daily" / "part-000.parquet"
    _write_daily_snapshot(daily_path, "2026-02-28", symbol_count=symbol_count)

    payload = relation_network_payload(str(tmp_path))

    assert len(payload["nodes"]) == symbol_count
    assert payload["available_community_counts"] == (
        [count for count in [2, 4, 6, 8, 10] if count <= symbol_count]
        if symbol_count >= 2
        else ([1] if symbol_count == 1 else [])
    )
    assert all(node["community_id"] >= 0 for node in payload["nodes"])


def test_backend_container_manifest_is_complete_and_secret_safe() -> None:
    project_root = Path(__file__).resolve().parents[1]
    dockerfile = (project_root / "deploy" / "docker" / "Dockerfile.backend").read_text(encoding="utf-8")
    requirements = (project_root / "deploy" / "docker" / "requirements.backend.txt").read_text(encoding="utf-8")
    dockerignore = (project_root / ".dockerignore").read_text(encoding="utf-8")
    compose = yaml.safe_load(
        (project_root / "deploy" / "docker" / "docker-compose.yml").read_text(encoding="utf-8")
    )

    copy_sources = [
        line.split()[1]
        for line in dockerfile.splitlines()
        if line.startswith("COPY ")
    ]
    assert copy_sources
    assert all((project_root / source).exists() for source in copy_sources)

    for dependency in (
        "fastapi",
        "uvicorn",
        "duckdb",
        "numpy",
        "pandas",
        "pyarrow",
        "networkx",
        "sqlalchemy",
        "alembic",
    ):
        assert dependency in requirements.lower()
    for runtime_source in ("COPY ops ./ops", "COPY simulation ./simulation", "COPY frontend/src ./frontend/src"):
        assert runtime_source in dockerfile
    assert "USER appuser" in dockerfile
    assert "HEALTHCHECK" in dockerfile

    backend = compose["services"]["backend"]
    assert "auth-secrets:/app/.secrets" in backend["volumes"]
    assert "auth-secrets" in compose["volumes"]

    for secret_pattern in (".secrets/**", ".env.*", "*.pem", "*.key", ".venv/**"):
        assert secret_pattern in dockerignore


def test_rag_records_keep_nested_values_and_normalize_missing_values() -> None:
    from backend.app.services.rag_evidence_catalog import _safe_records

    records = _safe_records(pd.DataFrame([{"items": [1, 2], "missing": float("nan")}]))

    assert records == [{"items": [1, 2], "missing": None}]


def test_operational_get_payloads_do_not_materialize_reports(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import ops.final_acceptance_final as final_module
    import ops.ops_deployment_ops as ops_module

    from backend.app.main import route_payload

    ops_report_dir = tmp_path / "ops"
    final_report_dir = tmp_path / "final"
    monkeypatch.setattr(ops_module, "REPORT_DIR", ops_report_dir)
    monkeypatch.setattr(final_module, "REPORT_DIR", final_report_dir)
    monkeypatch.setattr(
        ops_module,
        "resolve_config",
        lambda **_: (
            SimpleNamespace(orchestrator="prefect-local"),
            "a" * 64,
            "reports/ops_deployment/resolved_config.yaml",
        ),
    )

    for module in ("ops", "orchestration", "backfill", "observability", "deployment", "final-acceptance"):
        assert route_payload(module)["status"]

    assert not ops_report_dir.exists()
    assert not final_report_dir.exists()
