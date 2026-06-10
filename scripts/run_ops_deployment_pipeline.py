from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ops.ops_deployment_ops import build_ops_deployment_artifacts


def main() -> int:
    parser = argparse.ArgumentParser(description="ops_deployment local operational dry-run pipeline")
    parser.add_argument("--dry-run", action="store_true", help="Run deterministic local smoke without external side effects")
    parser.add_argument("--data-version")
    parser.add_argument("--run-id")
    parser.add_argument("--trade-date")
    parser.add_argument("--replay-offset")
    parser.add_argument("--model-version")
    parser.add_argument("--rag-index-version")
    args = parser.parse_args()
    payload = build_ops_deployment_artifacts()
    result = {
        "status": "dry_run_passed" if args.dry_run else "completed",
        "mode": "local_deterministic_no_external_side_effects",
        "config_hash": payload["config"]["config_hash"],
        "requested_restore_keys": {k: v for k, v in vars(args).items() if v and k != "dry_run"},
        "mvp_task_count": len(payload["orchestration"]["mvp_dag"]),
        "extended_task_count": len(payload["orchestration"]["extended_dag"]),
    }
    out = ROOT / "reports" / "ops_deployment" / "ops_deployment_pipeline_cli_result.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
