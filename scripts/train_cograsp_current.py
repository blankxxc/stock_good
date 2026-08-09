from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pandas as pd

from models.cograsp_current import CURRENT_DAILY, train_current_cograsp


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Train the official COGRASP architecture on the latest local CSI300 universe."
    )
    parser.add_argument("--epochs", type=int, default=60)
    parser.add_argument("--patience", type=int, default=12)
    parser.add_argument(
        "--batch-size",
        type=int,
        default=1,
        help="The unmodified upstream COGRASP forward pass requires batch size 1.",
    )
    parser.add_argument("--top-k", type=int, default=8)
    parser.add_argument("--learning-rate", type=float, default=1e-3)
    parser.add_argument("--weight-decay", type=float, default=1e-4)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if not CURRENT_DAILY.exists():
        raise FileNotFoundError(
            "Current CSI300 daily data is missing; run scripts/update_daily_market_data.py first"
        )
    market = pd.read_parquet(CURRENT_DAILY)
    metadata = train_current_cograsp(
        market,
        epochs=args.epochs,
        patience=args.patience,
        batch_size=args.batch_size,
        top_k=args.top_k,
        learning_rate=args.learning_rate,
        weight_decay=args.weight_decay,
    )
    print(json.dumps(metadata, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
