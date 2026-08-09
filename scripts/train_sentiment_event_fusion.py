from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from models.sentiment_event_fusion import CURRENT_DAILY, train_sentiment_event_fusion


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Train the CAMEF/CARAG-inspired CSI300 sentiment-event LightGBM model."
    )
    parser.add_argument("--max-estimators", type=int, default=450)
    args = parser.parse_args()
    if not CURRENT_DAILY.exists():
        raise FileNotFoundError("run scripts/update_daily_market_data.py first")
    report = train_sentiment_event_fusion(
        pd.read_parquet(CURRENT_DAILY), max_estimators=args.max_estimators
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
