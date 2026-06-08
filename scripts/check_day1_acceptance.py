from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROJECT_PYTHON = (ROOT / ".venv" / "Scripts" / "python.exe") if (ROOT / ".venv" / "Scripts" / "python.exe").exists() else Path(sys.executable)
DOCKER = Path(r"C:\Program Files\Docker\Docker\resources\bin\docker.exe")
DOCKER_CMD = str(DOCKER) if DOCKER.exists() else "docker"

def run(cmd: list[str], cwd: Path = ROOT) -> dict:
    # Windows Python does not always resolve .cmd shims (for example npm.cmd)
    # when subprocess is called with a list. shell=True for npm keeps the
    # acceptance script portable between Git Bash, cmd.exe, and native Python.
    use_shell = cmd and cmd[0].lower() in {"npm", "npx"}
    invocation = " ".join(cmd) if use_shell else cmd
    proc = subprocess.run(
        invocation,
        cwd=cwd,
        text=True,
        capture_output=True,
        shell=use_shell,
        encoding="utf-8",
        errors="replace",
    )
    stdout = proc.stdout or ""
    stderr = proc.stderr or ""
    return {"cmd": " ".join(cmd), "returncode": proc.returncode, "stdout": stdout[-2000:], "stderr": stderr[-2000:]}

checks = [
    run([str(PROJECT_PYTHON), "-m", "pytest", "tests/test_day1_scaffold.py", "-q"]),
    run([str(PROJECT_PYTHON), "backend/app/db/run_day1_migration.py"]),
    run([str(PROJECT_PYTHON), "-m", "alembic", "-c", "alembic.ini", "upgrade", "head"]),
    run([str(PROJECT_PYTHON), "spark/jobs/day1_spark_smoke.py"]),
    run([str(PROJECT_PYTHON), "streaming/flink/day1_flink_job_graph.py"]),
    run(["npm", "run", "validate:routes"], cwd=ROOT / "frontend"),
    run(["npm", "run", "build"], cwd=ROOT / "frontend"),
    run([DOCKER_CMD, "compose", "-f", "deploy/docker/docker-compose.yml", "config", "--services"]),
]
report = {"status": "ok" if all(c["returncode"] == 0 for c in checks) else "failed", "checks": checks}
out = ROOT / "reports" / "day1" / "acceptance_report.json"
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps(report, ensure_ascii=False, indent=2))
sys.exit(0 if report["status"] == "ok" else 1)
