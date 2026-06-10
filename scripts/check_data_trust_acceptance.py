from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def run_acceptance() -> dict[str, Any]:
    from quality.data_trust_data_trust import run_data_trust_data_trust

    pipeline = run_data_trust_data_trust()
    failed: list[str] = []

    def check(name: str, condition: bool) -> None:
        if not condition:
            failed.append(name)

    quality_path = ROOT / "reports" / "data_quality_report.json"
    lineage_path = ROOT / "reports" / "lineage_report.json"
    leakage_path = ROOT / "reports" / "data_trust" / "leakage_report.json"
    synthetic_path = ROOT / "reports" / "data_trust" / "synthetic_mini_market_report.json"
    quarantine_root = ROOT / "data" / "quarantine" / "data_trust_synthetic_market"
    frontend_dq = ROOT / "frontend" / "src" / "app" / "data-quality" / "page.tsx"
    frontend_lineage = ROOT / "frontend" / "src" / "app" / "lineage" / "page.tsx"

    check("pipeline_status_ok", pipeline.get("status") == "ok")
    check("quality_json_html_exist", quality_path.is_file() and (ROOT / "reports" / "data_quality_report.html").is_file())
    check("lineage_json_html_exist", lineage_path.is_file() and (ROOT / "reports" / "lineage_report.html").is_file())
    check("leakage_report_passed", leakage_path.is_file() and _read_json(leakage_path).get("status") == "passed")
    check("synthetic_mini_market_passed", synthetic_path.is_file() and _read_json(synthetic_path).get("row_count") == 2000)
    check("quarantine_written", quarantine_root.exists() and any(quarantine_root.glob("**/*.parquet")))
    if quality_path.is_file():
        quality = _read_json(quality_path)
        check("quality_checks_passed", quality.get("status") == "passed" and quality.get("summary", {}).get("quarantined_records", 0) >= 5)
        check("quality_thresholds_present", quality.get("thresholds", {}).get("daily_coverage_min") == 0.99)
    if lineage_path.is_file():
        lineage = _read_json(lineage_path)
        check("lineage_edges_present", lineage.get("edge_count", 0) >= 30)
    check("frontend_pages_data_trust_ready", "data_trust" in frontend_dq.read_text(encoding="utf-8") and "data_trust" in frontend_lineage.read_text(encoding="utf-8"))

    result = {
        "status": "ok" if not failed else "failed",
        "checks": 10,
        "failed": failed,
        "pipeline": pipeline,
    }
    report_path = ROOT / "reports" / "data_trust" / "acceptance_report.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return result


if __name__ == "__main__":
    print(json.dumps(run_acceptance(), ensure_ascii=False, indent=2))
