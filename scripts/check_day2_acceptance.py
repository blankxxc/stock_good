from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROJECT_PYTHON = (ROOT / ".venv" / "Scripts" / "python.exe") if (ROOT / ".venv" / "Scripts" / "python.exe").exists() else Path(sys.executable)
DOCKER = Path(r"C:\Program Files\Docker\Docker\resources\bin\docker.exe")
DOCKER_CMD = str(DOCKER) if DOCKER.exists() else "docker"


def run(cmd: list[str], cwd: Path = ROOT, timeout: int = 600, optional: bool = False) -> dict:
    use_shell = cmd and cmd[0].lower() in {"npm", "npx"}
    invocation = " ".join(cmd) if use_shell else cmd
    proc = subprocess.run(invocation, cwd=cwd, text=True, capture_output=True, shell=use_shell, encoding="utf-8", errors="replace", timeout=timeout)
    return {"cmd": " ".join(cmd), "returncode": proc.returncode, "optional": optional, "stdout": (proc.stdout or "")[-3000:], "stderr": (proc.stderr or "")[-3000:]}


def docker_ready() -> bool:
    proc = subprocess.run([DOCKER_CMD, "info", "--format", "{{.ServerVersion}} {{.OSType}}"], cwd=ROOT, text=True, capture_output=True, encoding="utf-8", errors="replace", timeout=40)
    return proc.returncode == 0 and "linux" in proc.stdout


checks = [
    run([str(PROJECT_PYTHON), "scripts/run_day2_pipeline.py"]),
    run([str(PROJECT_PYTHON), "spark/jobs/bronze_to_silver_market_daily.py"]),
    run([str(PROJECT_PYTHON), "spark/jobs/bronze_to_silver_reference.py"]),
    run([str(PROJECT_PYTHON), "spark/jobs/silver_to_gold_base_panels.py"]),
    run([str(PROJECT_PYTHON), "spark/jobs/write_iceberg_or_delta_poc.py"]),
    run([str(PROJECT_PYTHON), "-m", "pytest", "tests/test_day1_scaffold.py", "tests/test_day2_batch_lakehouse.py", "-q"]),
    run(["npm", "run", "build"], cwd=ROOT / "frontend"),
    run([DOCKER_CMD, "compose", "-f", "deploy/docker/docker-compose.yml", "config", "--quiet"]),
]

if docker_ready():
    checks.append(run([str(PROJECT_PYTHON), "scripts/load_day2_clickhouse.py"], timeout=180))
    checks.append(run([DOCKER_CMD, "exec", "stock-good-day1-clickhouse-1", "clickhouse-client", "--query", "SELECT count() FROM ads_dashboard_summary"], timeout=120))
else:
    checks.append({"cmd": "docker info", "returncode": 0, "optional": True, "stdout": "Docker engine unavailable; ClickHouse live load skipped by script.", "stderr": ""})

required_ok = all(c["returncode"] == 0 for c in checks if not c.get("optional"))
report = {"status": "ok" if required_ok else "failed", "checks": checks}
out = ROOT / "reports" / "day2" / "acceptance_report.json"
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps(report, ensure_ascii=False, indent=2))
sys.exit(0 if required_ok else 1)
