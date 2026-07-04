from __future__ import annotations

import json
import math
from collections import Counter, defaultdict
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


def _safe_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(result) or math.isinf(result):
        return None
    return result


def _coverage(item: dict[str, Any]) -> float | None:
    coverage_by_year = item.get("coverage_by_year") or {}
    return _safe_float(coverage_by_year.get("all"))


def _missing_rate(item: dict[str, Any]) -> float | None:
    missing_rate_by_year = item.get("missing_rate_by_year") or {}
    return _safe_float(missing_rate_by_year.get("all"))


def _admission_status(name: str, category: str, metrics: dict[str, Any], point_in_time_violations: int | None) -> str:
    coverage = _coverage(metrics)
    icir = _safe_float(metrics.get("ICIR"))
    cost_adjusted_spread = _safe_float(metrics.get("cost_adjusted_spread"))
    if category in {"style_proxy"} or name.endswith("_proxy") or "proxy" in name:
        return "proxy_only"
    if point_in_time_violations not in {0, None}:
        return "blocked_pit"
    if coverage is not None and coverage < 0.80:
        return "needs_data"
    if icir is not None and abs(icir) >= 1.0 and (cost_adjusted_spread is None or cost_adjusted_spread > -0.002):
        return "research_ready"
    return "needs_review"


def _build_factor_catalog(
    factor_spec: dict[str, Any],
    registry: dict[str, Any],
    report: dict[str, Any],
    point_in_time: dict[str, Any],
) -> dict[str, Any]:
    specs = factor_spec.get("factors", {}) or {}
    report_by_name = {item.get("factor_name"): item for item in report.get("single_factor_reports", []) if item.get("factor_name")}
    registry_by_name = {item.get("feature_name"): item for item in registry.get("features", []) if item.get("feature_name")}
    pit_violations = point_in_time.get("point_in_time_violations")
    category_counts: Counter[str] = Counter()
    category_metric_acc: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    catalog: list[dict[str, Any]] = []

    for name, spec in sorted(specs.items()):
        metrics = report_by_name.get(name, {})
        registry_item = registry_by_name.get(name, {})
        category = str(spec.get("category") or registry_item.get("feature_group") or metrics.get("category") or "uncategorized")
        category_counts[category] += 1
        coverage = _coverage(metrics)
        missing_rate = _missing_rate(metrics)
        icir = _safe_float(metrics.get("ICIR"))
        rank_ic = _safe_float(metrics.get("RankIC_mean"))
        ic_mean = _safe_float(metrics.get("IC_mean"))
        turnover = _safe_float(metrics.get("turnover"))
        capacity = _safe_float(metrics.get("capacity_estimate"))
        status = _admission_status(name, category, metrics, pit_violations)
        for metric_name, metric_value in {
            "coverage": coverage,
            "missing_rate": missing_rate,
            "icir": icir,
            "rank_ic_mean": rank_ic,
            "turnover": turnover,
        }.items():
            if metric_value is not None:
                category_metric_acc[category][metric_name].append(metric_value)
        risks = [str(item) for item in spec.get("known_risks", [])]
        if status == "proxy_only" and not any("proxy" in item.lower() for item in risks):
            risks.append("proxy_only_until_real_fundamental_or_fund_flow_data")
        catalog.append(
            {
                "factor_name": name,
                "category": category,
                "formula": spec.get("formula"),
                "economic_hypothesis": spec.get("economic_hypothesis") or registry_item.get("description"),
                "expected_decay": spec.get("expected_decay") or registry_item.get("lookback_window"),
                "coverage": coverage,
                "missing_rate": missing_rate,
                "outlier_rate": _safe_float(metrics.get("outlier_rate")),
                "ic_mean": ic_mean,
                "rank_ic_mean": rank_ic,
                "icir": icir,
                "turnover": turnover,
                "top_bottom_spread": _safe_float(metrics.get("top_bottom_spread")),
                "cost_adjusted_spread": _safe_float(metrics.get("cost_adjusted_spread")),
                "capacity_estimate": capacity,
                "quantile_return_monotonicity": metrics.get("quantile_return_monotonicity"),
                "correlation_with_existing_factors": metrics.get("correlation_with_existing_factors", {}),
                "multiple_testing_risk": metrics.get("multiple_testing_risk", {}),
                "admission_status": status,
                "risk_notes": risks[:5],
                "time_semantics": spec.get("time_semantics", {}),
                "prediction_time_rule": spec.get("prediction_time") or registry_item.get("available_time_rule"),
                "detail_anchor": f"factor-{name.replace('_', '-')}",
            }
        )

    def avg(values: list[float]) -> float | None:
        return None if not values else sum(values) / len(values)

    category_summary = []
    for category, count in sorted(category_counts.items()):
        metrics = category_metric_acc[category]
        category_summary.append(
            {
                "category": category,
                "factor_count": count,
                "avg_coverage": avg(metrics.get("coverage", [])),
                "avg_missing_rate": avg(metrics.get("missing_rate", [])),
                "avg_icir": avg(metrics.get("icir", [])),
                "avg_abs_rank_ic": avg([abs(v) for v in metrics.get("rank_ic_mean", [])]),
                "avg_turnover": avg(metrics.get("turnover", [])),
            }
        )

    top_factors_by_icir = sorted(
        [item for item in catalog if item.get("icir") is not None],
        key=lambda item: abs(item["icir"]),
        reverse=True,
    )[:10]
    admission_counts = Counter(item["admission_status"] for item in catalog)
    return {
        "factor_catalog": catalog,
        "category_summary": category_summary,
        "top_factors_by_icir": top_factors_by_icir,
        "factor_catalog_summary": {
            "total_factors": len(catalog),
            "category_count": len(category_summary),
            "evaluated_factor_count": len(report_by_name),
            "admission_ready_count": admission_counts.get("research_ready", 0),
            "needs_review_count": admission_counts.get("needs_review", 0),
            "proxy_only_count": admission_counts.get("proxy_only", 0),
            "point_in_time_violations": pit_violations,
            "grain": registry.get("grain", "symbol + trade_date + prediction_time"),
        },
        "factor_ui_hints": {
            "default_sort": "ICIR_desc",
            "search_fields": ["factor_name", "category", "economic_hypothesis", "formula"],
            "status_labels": {
                "research_ready": "研究可复核",
                "needs_review": "需要复核",
                "needs_data": "数据不足",
                "proxy_only": "代理因子",
                "blocked_pit": "点时间阻断",
            },
        },
    }


def factor_payload(research_boundary: str) -> dict[str, Any]:
    from backend.app.services.event_regime_catalog import event_regime_payload
    from backend.app.services.relation_graph_catalog import relation_graph_payload

    root = project_root()
    report = _read_json(root / "reports" / "factor_store" / "factor_store_factor_report.json") or {}
    point_in_time = _read_json(root / "reports" / "factor_store" / "point_in_time_join_report.json") or {}
    spark = _read_json(root / "reports" / "factor_store" / "spark_factor_materialization_report.json") or {}
    registry = _read_yaml(root / "feature_store" / "feature_registry.yaml")
    factor_spec = _read_yaml(root / "configs" / "factor" / "factor_spec.yaml")
    event_regime_event_regime = event_regime_payload(research_boundary)
    relation_graph_relation_graph = relation_graph_payload(research_boundary)

    if report.get("status") == "ok":
        catalog_payload = _build_factor_catalog(factor_spec, registry, report, point_in_time)
        return {
            "module": "factors",
            "status": "factor_store_factor_store_ready",
            "maturity": "L2-offline-factor-store-polars-spark-feature-registry-with-event_regime-event-regime-and-relation_graph-relation-graph-extension",
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
            "event_regime": event_regime_event_regime,
            "relation_graph": relation_graph_relation_graph,
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
            **catalog_payload,
            "artifacts": report.get("artifacts", {}),
        }

    return {
        "module": "factors",
        "status": "factor_store_factor_store_pending",
        "maturity": "L1-contract-and-route-stub",
        "research_boundary": research_boundary,
        "description": "离线/实时/事件/市场环境/关系因子库",
    }


def feature_payload(research_boundary: str) -> dict[str, Any]:
    root = project_root()
    report = _read_json(root / "reports" / "factor_store" / "factor_store_factor_report.json") or {}
    point_in_time = _read_json(root / "reports" / "factor_store" / "point_in_time_join_report.json") or {}
    registry = _read_yaml(root / "feature_store" / "feature_registry.yaml")
    return {
        "module": "features",
        "status": "factor_store_feature_registry_ready" if registry.get("features") and point_in_time.get("status") == "ok" else "factor_store_feature_registry_pending",
        "maturity": "L2-feature-registry-and-point-in-time-join",
        "research_boundary": research_boundary,
        "feature_set_version": report.get("feature_set_version", point_in_time.get("feature_set_version")),
        "feature_count": len(registry.get("features", [])),
        "feature_matrix_rows": point_in_time.get("output_rows", report.get("feature_matrix_rows", 0)),
        "point_in_time_violations": point_in_time.get("point_in_time_violations"),
        "registry_path": "feature_store/feature_registry.yaml",
        "feature_view_path": "feature_store/feature_views/factor_store_factor_daily_view.yaml",
        "materialization_job_path": "feature_store/materialization_jobs/factor_store_materialize_feature_matrix.yaml",
    }


def spark_jobs_payload(research_boundary: str) -> dict[str, Any]:
    root = project_root()
    factor_store = _read_json(root / "reports" / "factor_store" / "spark_factor_materialization_report.json") or {}
    lakehouse = _read_json(root / "reports" / "lakehouse" / "spark_bronze_to_silver_market_daily_report.json") or {}
    if factor_store.get("status") == "ok":
        return {
            "module": "spark-jobs",
            "status": "factor_store_spark_factor_materialization_ready",
            "maturity": "L2-pyspark-factor-materialization-consistency-check",
            "research_boundary": research_boundary,
            "jobs": [
                factor_store,
                lakehouse,
            ],
        }
    return {
        "module": "spark-jobs",
        "status": "lakehouse_spark_boundary_ready" if lakehouse.get("status") == "ok" else "foundation_placeholder_ready",
        "maturity": "L1-contract-and-route-stub",
        "research_boundary": research_boundary,
        "description": "Spark 离线 ETL、批量因子、标签和训练样本 job 状态",
    }
