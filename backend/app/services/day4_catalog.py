from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml


def project_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _read_json(path: Path) -> Any:
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _read_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def factor_payload(research_boundary: str) -> dict[str, Any]:
    from backend.app.services.day7_catalog import event_regime_payload
    from backend.app.services.day8_catalog import relation_graph_payload

    root = project_root()
    report = _read_json(root / "reports" / "day4" / "day4_factor_report.json") or {}
    point_in_time = _read_json(root / "reports" / "day4" / "point_in_time_join_report.json") or {}
    spark = _read_json(root / "reports" / "day4" / "spark_factor_materialization_report.json") or {}
    registry = _read_yaml(root / "feature_store" / "feature_registry.yaml")
    factor_spec = _read_yaml(root / "configs" / "factor" / "factor_spec.yaml")
    day7_event_regime = event_regime_payload(research_boundary)
    day8_relation_graph = relation_graph_payload(research_boundary)

    if report.get("status") == "ok":
        return {
            "module": "factors",
            "status": "day4_factor_store_ready",
            "maturity": "L2-offline-factor-store-polars-spark-feature-registry-with-day7-event-regime-and-day8-relation-graph-extension",
            "research_boundary": research_boundary,
            "data_version": report.get("data_version"),
            "factor_version": report.get("factor_version"),
            "feature_set_version": report.get("feature_set_version"),
            "engine": report.get("engine"),
            "factor_count": report.get("factor_count", 0),
            "factor_rows": report.get("factor_rows", 0),
            "feature_matrix_rows": report.get("feature_matrix_rows", 0),
            "feature_registry_count": len(registry.get("features", [])),
            "factor_spec_count": len(factor_spec.get("factors", {})),
            "single_factor_report_count": report.get("single_factor_report_count", 0),
            "single_factor_reports": report.get("single_factor_reports", [])[:12],
            "risk_outputs": report.get("risk_outputs", {}),
            "event_regime": day7_event_regime,
            "relation_graph": day8_relation_graph,
            "point_in_time_join": {
                "status": point_in_time.get("status"),
                "feature_count": point_in_time.get("feature_count"),
                "point_in_time_violations": point_in_time.get("point_in_time_violations"),
            },
            "spark_consistency": {
                "status": spark.get("status"),
                "consistency_status": spark.get("consistency_status"),
                "compared_factor_count": spark.get("compared_factor_count"),
                "failed_factors": spark.get("failed_factors", []),
            },
            "artifacts": report.get("artifacts", {}),
        }

    return {
        "module": "factors",
        "status": "day4_factor_store_pending",
        "maturity": "L1-contract-and-route-stub",
        "research_boundary": research_boundary,
        "description": "离线/实时/事件/市场环境/关系因子库",
    }


def feature_payload(research_boundary: str) -> dict[str, Any]:
    root = project_root()
    report = _read_json(root / "reports" / "day4" / "day4_factor_report.json") or {}
    point_in_time = _read_json(root / "reports" / "day4" / "point_in_time_join_report.json") or {}
    registry = _read_yaml(root / "feature_store" / "feature_registry.yaml")
    return {
        "module": "features",
        "status": "day4_feature_registry_ready" if registry.get("features") and point_in_time.get("status") == "ok" else "day4_feature_registry_pending",
        "maturity": "L2-feature-registry-and-point-in-time-join",
        "research_boundary": research_boundary,
        "feature_set_version": report.get("feature_set_version", point_in_time.get("feature_set_version")),
        "feature_count": len(registry.get("features", [])),
        "feature_matrix_rows": point_in_time.get("output_rows", report.get("feature_matrix_rows", 0)),
        "point_in_time_violations": point_in_time.get("point_in_time_violations"),
        "registry_path": "feature_store/feature_registry.yaml",
        "feature_view_path": "feature_store/feature_views/day4_factor_daily_view.yaml",
        "materialization_job_path": "feature_store/materialization_jobs/day4_materialize_feature_matrix.yaml",
    }


def spark_jobs_payload(research_boundary: str) -> dict[str, Any]:
    root = project_root()
    day4 = _read_json(root / "reports" / "day4" / "spark_factor_materialization_report.json") or {}
    day2 = _read_json(root / "reports" / "day2" / "spark_bronze_to_silver_market_daily_report.json") or {}
    if day4.get("status") == "ok":
        return {
            "module": "spark-jobs",
            "status": "day4_spark_factor_materialization_ready",
            "maturity": "L2-pyspark-factor-materialization-consistency-check",
            "research_boundary": research_boundary,
            "jobs": [
                day4,
                day2,
            ],
        }
    return {
        "module": "spark-jobs",
        "status": "day2_spark_boundary_ready" if day2.get("status") == "ok" else "day1_placeholder_ready",
        "maturity": "L1-contract-and-route-stub",
        "research_boundary": research_boundary,
        "description": "Spark 离线 ETL、批量因子、标签和训练样本 job 状态",
    }
