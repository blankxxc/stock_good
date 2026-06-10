from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml


def project_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _read_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def _read_json(path: Path) -> Any:
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def license_payload(research_boundary: str) -> dict[str, Any]:
    root = project_root()
    registry = _read_yaml(root / "configs" / "data" / "source_license_registry.yaml")
    sources = registry.get("sources", [])
    counts: dict[str, int] = {}
    for source in sources:
        status = str(source.get("license_status", "unknown"))
        counts[status] = counts.get(status, 0) + 1
    counts["restricted_or_blocked"] = sum(counts.get(key, 0) for key in ("restricted", "not_authorized", "adapter_pending"))
    return {
        "module": "licenses",
        "status": "lakehouse_license_registry_ready" if sources else "lakehouse_license_registry_missing",
        "maturity": "L2-local-registry-and-license-gate",
        "research_boundary": research_boundary,
        "summary": counts,
        "sources": sources,
    }


def lakehouse_payload(research_boundary: str) -> dict[str, Any]:
    root = project_root()
    report = _read_json(root / "reports" / "lakehouse" / "lakehouse_pipeline_report.json") or {}
    manifest = _read_json(root / "data" / "snapshots" / "dataset_snapshot_manifest_lakehouse.json") or []
    return {
        "module": "lakehouse",
        "status": "lakehouse_lakehouse_ready" if report.get("status") == "ok" else "lakehouse_lakehouse_pending",
        "maturity": "L2-parquet-duckdb-spark-boundary",
        "research_boundary": research_boundary,
        "data_version": report.get("data_version"),
        "snapshot_count": len(manifest),
        "tables": [row.get("dataset_name") for row in manifest],
        "report": report,
    }


def data_quality_payload(research_boundary: str) -> dict[str, Any]:
    root = project_root()
    data_trust = _read_json(root / "reports" / "data_trust" / "data_trust_data_trust_report.json") or {}
    quality = _read_json(root / "reports" / "data_quality_report.json") or {}
    leakage = _read_json(root / "reports" / "data_trust" / "leakage_report.json") or {}
    if data_trust.get("status") == "ok" and quality:
        return {
            "module": "data-quality",
            "status": "data_trust_data_trust_ready",
            "maturity": "L2-data-trust-quality-lineage-leakage",
            "research_boundary": research_boundary,
            "data_version": data_trust.get("data_version"),
            "quality_status": quality.get("status"),
            "leakage_check_status": leakage.get("leakage_check_status", data_trust.get("leakage_check_status")),
            "summary": quality.get("summary", {}),
            "checks": quality.get("checks", []),
            "thresholds": quality.get("thresholds", {}),
            "quarantine": {
                "record_count": quality.get("summary", {}).get("quarantined_records", 0),
                "path": "data/quarantine/data_trust_synthetic_market",
                "reasons": quality.get("summary", {}).get("quarantined_reasons", []),
            },
            "reports": {
                "json": "reports/data_quality_report.json",
                "html": "reports/data_quality_report.html",
                "leakage_json": "reports/data_trust/leakage_report.json",
                "synthetic_json": "reports/data_trust/synthetic_mini_market_report.json",
            },
        }

    report = _read_json(root / "reports" / "lakehouse" / "lakehouse_pipeline_report.json") or {}
    return {
        "module": "data-quality",
        "status": "lakehouse_ads_quality_summary_ready" if report.get("status") == "ok" else "lakehouse_quality_pending",
        "maturity": "L1-ads-summary",
        "research_boundary": research_boundary,
        "data_version": report.get("data_version"),
        "gold_ads_tables": report.get("gold_ads_tables", {}),
        "license_status_counts": report.get("license_status_counts", {}),
    }


def lineage_payload(research_boundary: str) -> dict[str, Any]:
    root = project_root()
    data_trust = _read_json(root / "reports" / "data_trust" / "data_trust_data_trust_report.json") or {}
    lineage = _read_json(root / "reports" / "lineage_report.json") or {}
    if data_trust.get("status") == "ok" and lineage:
        return {
            "module": "lineage",
            "status": "data_trust_lineage_ready",
            "maturity": "L2-lightweight-lineage-source-job-snapshot-report",
            "research_boundary": research_boundary,
            "data_version": lineage.get("data_version"),
            "node_count": lineage.get("node_count", 0),
            "edge_count": lineage.get("edge_count", 0),
            "nodes": lineage.get("nodes", [])[:80],
            "edges": lineage.get("edges", [])[:120],
            "reports": {
                "json": "reports/lineage_report.json",
                "html": "reports/lineage_report.html",
            },
        }
    return {
        "module": "lineage",
        "status": "foundation_placeholder_ready",
        "maturity": "L1-contract-and-route-stub",
        "research_boundary": research_boundary,
        "description": "ODS/DWD/DWS/ADS、Spark/Flink job 到结果快照的血缘",
    }
