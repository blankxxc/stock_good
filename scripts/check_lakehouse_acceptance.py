from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROJECT_PYTHON = (ROOT / ".venv" / "Scripts" / "python.exe") if (ROOT / ".venv" / "Scripts" / "python.exe").exists() else Path(sys.executable)


def run(cmd: list[str], cwd: Path = ROOT, timeout: int = 600) -> dict:
    use_shell = cmd and cmd[0].lower() in {"npm", "npx"}
    invocation = " ".join(cmd) if use_shell else cmd
    proc = subprocess.run(invocation, cwd=cwd, text=True, capture_output=True, shell=use_shell, encoding="utf-8", errors="replace", timeout=timeout)
    return {"cmd": " ".join(cmd), "returncode": proc.returncode, "stdout": (proc.stdout or "")[-3000:], "stderr": (proc.stderr or "")[-3000:]}


checks = [
    run([str(PROJECT_PYTHON), "scripts/run_lakehouse_pipeline.py"]),
    run([str(PROJECT_PYTHON), "spark/jobs/bronze_to_silver_market_daily.py"]),
    run([str(PROJECT_PYTHON), "spark/jobs/bronze_to_silver_reference.py"]),
    run([str(PROJECT_PYTHON), "spark/jobs/silver_to_gold_base_panels.py"]),
    run([str(PROJECT_PYTHON), "scripts/check_iceberg_acceptance.py"]),
    run([str(PROJECT_PYTHON), "-m", "pytest", "tests/test_foundation_scaffold.py", "tests/test_lakehouse_batch_lakehouse.py", "tests/test_iceberg_table_format.py", "-q"]),
    run(["npm", "run", "build"], cwd=ROOT / "frontend"),
]

required_ok = all(c["returncode"] == 0 for c in checks)
report = {"status": "ok" if required_ok else "failed", "checks": checks}
out = ROOT / "reports" / "lakehouse" / "acceptance_report.json"
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps(report, ensure_ascii=False, indent=2))
sys.exit(0 if required_ok else 1)
