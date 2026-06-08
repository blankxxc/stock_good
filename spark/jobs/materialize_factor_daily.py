from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from spark.jobs.day4_factor_materialization import run_job  # noqa: E402


def main() -> None:
    report = run_job()
    materialization_report = {
        "status": report.get("status"),
        "runtime": report.get("runtime"),
        "job_name": "materialize_factor_daily",
        "factor_daily_panel_output": report.get("factor_daily_panel_output"),
        "factor_daily_panel_row_count": report.get("factor_daily_panel_row_count"),
        "feature_matrix_output": report.get("output"),
        "feature_matrix_row_count": report.get("row_count"),
        "factor_version": report.get("factor_version"),
        "feature_set_version": report.get("feature_set_version"),
        "research_boundary": report.get("research_boundary"),
    }
    path = ROOT / "reports" / "day4" / "spark_factor_daily_panel_report.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(materialization_report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(materialization_report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
