from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from models.finmamba_official_adapter import (
    CHECKPOINT_DIR,
    CHECKPOINT_PATH,
    CURRENT_DAILY,
    DATA_DIR,
    RELATION_DIR,
    SCORES_PATH,
    UPSTREAM_ROOT,
    publish_latest_predictions,
    runtime_status,
    write_official_inputs,
    write_runtime_report,
)


def _run(command: list[str], *, cwd: Path) -> None:
    environment = os.environ.copy()
    existing = environment.get("PYTHONPATH", "")
    environment["PYTHONPATH"] = str(UPSTREAM_ROOT) + (os.pathsep + existing if existing else "")
    subprocess.run(command, cwd=cwd, env=environment, check=True)


def train_official_finmamba(*, device: str, epochs: int) -> dict[str, Any]:
    if not CURRENT_DAILY.exists():
        raise FileNotFoundError(
            "Current CSI300 data is missing; run scripts/update_daily_market_data.py first"
        )
    preparation = write_official_inputs(pd.read_parquet(CURRENT_DAILY))
    runtime = runtime_status()
    if runtime["status"] != "ready":
        return write_runtime_report(preparation=preparation)

    RELATION_DIR.mkdir(parents=True, exist_ok=True)
    CHECKPOINT_DIR.mkdir(parents=True, exist_ok=True)
    _run(
        [
            sys.executable,
            str(UPSTREAM_ROOT / "genRelation.py"),
            "--stock",
            "csi300_all",
            "--data-dir",
            str(DATA_DIR),
            "--output-dir",
            str(RELATION_DIR),
            "--lookback",
            "20",
            "--method",
            "spearman",
            "--device",
            device,
        ],
        cwd=UPSTREAM_ROOT,
    )
    split = preparation["split"]
    _run(
        [
            sys.executable,
            str(UPSTREAM_ROOT / "train_finmamba.py"),
            "--stock",
            "csi300",
            "--data-dir",
            str(DATA_DIR),
            "--relation-dir",
            str(RELATION_DIR),
            "--train-start",
            split["train_start"],
            "--train-end",
            split["train_end"],
            "--valid-start",
            split["valid_start"],
            "--valid-end",
            split["valid_end"],
            "--test-start",
            split["test_start"],
            "--test-end",
            split["test_end"],
            "--seq-len",
            "20",
            "--epochs",
            str(epochs),
            "--device",
            device,
            "--output-dir",
            str(CHECKPOINT_DIR),
            "--checkpoint-name",
            CHECKPOINT_PATH.name,
            "--scores-name",
            SCORES_PATH.name,
            "--prediction-name",
            "test_predictions.csv",
            "--prediction-layout",
            "date-major",
        ],
        cwd=UPSTREAM_ROOT,
    )
    return publish_latest_predictions(device_spec=device)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Prepare current CSI300 data and optionally run the unmodified FinMamba author code."
    )
    parser.add_argument("--train", action="store_true", help="Generate relations, train, and publish latest scores.")
    parser.add_argument("--device", default="auto", help="auto, cuda:0, ...")
    parser.add_argument("--epochs", type=int, default=5)
    args = parser.parse_args()

    if args.train:
        report = train_official_finmamba(device=args.device, epochs=args.epochs)
    else:
        if not CURRENT_DAILY.exists():
            raise FileNotFoundError(CURRENT_DAILY)
        preparation = write_official_inputs(pd.read_parquet(CURRENT_DAILY))
        report = write_runtime_report(preparation=preparation)
    print(json.dumps(report, ensure_ascii=False, indent=2, default=str))
    raise SystemExit(0 if report.get("status") in {"ok", "blocked_runtime"} else 1)


if __name__ == "__main__":
    main()
