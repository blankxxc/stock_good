from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from spark.jobs.factor_store_factor_materialization import run_job  # noqa: E402


def main() -> None:
    report = run_job()
    validation_report = {
        "status": report.get("status"),
        "runtime": report.get("runtime"),
        "job_name": "validate_spark_polars_factor_consistency",
        "consistency_status": report.get("consistency_status"),
        "compared_factor_count": report.get("compared_factor_count"),
        "compare_factors": report.get("compare_factors"),
        "failed_factors": report.get("failed_factors"),
        "max_abs_diff_by_factor": report.get("max_abs_diff_by_factor"),
        "research_boundary": report.get("research_boundary"),
    }
    path = ROOT / "reports" / "factor_store" / "spark_polars_consistency_report.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(validation_report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(validation_report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
