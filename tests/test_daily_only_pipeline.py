from pathlib import Path

import pandas as pd
import pyarrow.parquet as pq
import pytest
from fastapi.testclient import TestClient

from lakehouse import lakehouse_pipeline


RETIRED_TABLES = {
    "ods_market_minute_raw", "ods_market_tick_raw", "ods_trade_raw",
    "ods_orderbook_raw", "dwd_stock_minute_bar", "factor_intraday_panel",
}


def test_daily_pipeline_materializes_only_supported_datasets(tmp_path, monkeypatch):
    monkeypatch.setattr(lakehouse_pipeline, "ROOT", tmp_path)
    report = lakehouse_pipeline.run_pipeline()
    tables = set(report["ods_tables"]) | set(report["dwd_tables"]) | set(report["gold_ads_tables"])
    assert tables.isdisjoint(RETIRED_TABLES)
    assert {"ods_market_daily_raw", "dwd_stock_daily_bar", "factor_daily_panel", "ads_score_latest"} <= tables
    manifest = pd.read_parquet(tmp_path / "data/snapshots/dataset_snapshot_manifest_lakehouse.parquet")
    assert set(manifest["dataset_name"]) == tables
    assert len(manifest) == report["snapshot_count"]
    snapshot_ids = set(manifest["snapshot_id"])
    assert all(set(upstream) <= snapshot_ids for upstream in manifest["upstream_snapshot_ids"])
    assert all(Path(path).is_dir() for path in manifest["physical_path"])

    # The open-to-close factor still uses only daily OHLCV.
    def read_partitions(rel):
        return pd.concat([pq.ParquetFile(path).read().to_pandas() for path in sorted((tmp_path / rel).rglob("*.parquet"))], ignore_index=True)

    daily = read_partitions("data/silver/dwd_stock_daily_bar")
    factors = read_partitions("data/gold/factor_daily_panel")
    observed = factors[factors["factor_name"] == "intraday_return"].merge(daily, on=["trade_date", "symbol"])
    assert len(observed) == len(daily)
    assert observed["factor_value"].tolist() == pytest.approx((observed["close"] / observed["open"] - 1).tolist())


def test_retired_apis_are_absent_from_routes_health_and_admin():
    from backend.app.main import app, admin_overview_payload

    client = TestClient(app)
    routes = {route.path for route in app.routes}
    for endpoint in ["/api/realtime", "/api/flink-jobs"]:
        assert endpoint not in routes
        assert client.get(endpoint).status_code == 404
    assert {"realtime", "flink", "redpanda_kafka"}.isdisjoint(client.get("/health").json()["modules"])
    assert "/api/realtime" not in str(admin_overview_payload())
    assert "/api/flink-jobs" not in str(admin_overview_payload())


def test_daily_config_and_deployment_have_no_streaming_dependencies():
    from ops.ops_deployment_ops import build_ops_deployment_artifacts, resolve_config

    root = Path(__file__).resolve().parents[1]
    config, _, _ = resolve_config(write_artifact=False)
    assert config.data["enabled_frequencies"] == ["daily"]
    assert "streaming" not in config.model_dump()
    payload = build_ops_deployment_artifacts(write_reports=False)
    components = {item["component"] for item in payload["observability"]["component_health"]}
    assert {"flink", "kafka", "redis"}.isdisjoint(components)
    assert payload["deployment"]["deployment_mode"] == "native_processes"
    assert (root / payload["deployment"]["deployment_guide"]).is_file()
