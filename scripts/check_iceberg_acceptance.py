from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
PROJECT_PYTHON = (ROOT / ".venv" / "Scripts" / "python.exe") if (ROOT / ".venv" / "Scripts" / "python.exe").exists() else Path(sys.executable)
REPORT = ROOT / "reports" / "lakehouse" / "iceberg_table_format_acceptance.json"
ACCEPTANCE_REPORT = ROOT / "reports" / "lakehouse" / "iceberg_acceptance_report.json"


def _run_job() -> dict[str, Any]:
    proc = subprocess.run(
        [str(PROJECT_PYTHON), "spark/jobs/write_iceberg_table_poc.py"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
        timeout=600,
    )
    return {
        "cmd": f"{PROJECT_PYTHON} spark/jobs/write_iceberg_table_poc.py",
        "returncode": proc.returncode,
        "stdout": (proc.stdout or "")[-6000:],
        "stderr": (proc.stderr or "")[-6000:],
    }


def _load_report() -> dict[str, Any]:
    if not REPORT.is_file():
        raise AssertionError(f"Missing Iceberg report: {REPORT}")
    return json.loads(REPORT.read_text(encoding="utf-8"))


def _validate(report: dict[str, Any]) -> list[str]:
    failed: list[str] = []

    def check(name: str, condition: bool) -> None:
        if not condition:
            failed.append(name)

    check("status_ok", report.get("status") == "ok")
    check("table_format_iceberg", report.get("table_format") == "iceberg")
    check("connector_package_present", "org.apache.iceberg:iceberg-spark-runtime-3.5_2.12" in str(report.get("connector_package", "")))
    check("fallback_not_used", report.get("fallback_used") is False)
    check("row_count_positive", int(report.get("row_count", 0)) > 0)
    check("read_back_matches", report.get("read_back_row_count") == report.get("row_count"))
    check("schema_evolution_checked", report.get("schema_evolution_checked") is True)
    check("metadata_files_present", int(report.get("metadata_file_count", 0)) > 0)
    check("snapshots_present", int(report.get("snapshots_count", 0)) > 0)
    check("files_present", int(report.get("files_count", 0)) > 0)
    return failed


def main() -> None:
    job = _run_job()
    report: dict[str, Any] = {}
    failed: list[str] = []
    if job["returncode"] != 0:
        failed.append("iceberg_job_returncode")
    try:
        report = _load_report()
        failed.extend(_validate(report))
    except Exception as exc:
        failed.append(f"report_validation_error:{exc!r}")

    result = {
        "status": "ok" if not failed else "failed",
        "failed": failed,
        "job": job,
        "iceberg_report": report,
    }
    ACCEPTANCE_REPORT.parent.mkdir(parents=True, exist_ok=True)
    ACCEPTANCE_REPORT.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    sys.exit(0 if not failed else 1)


if __name__ == "__main__":
    main()
