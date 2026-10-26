from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from data.adapters.benchmark_daily import update_benchmark_daily


if __name__ == "__main__":
    daily = pd.read_parquet(ROOT / "data/real/csi300_daily", columns=["trade_date"])
    report = update_benchmark_daily(str(daily.trade_date.min()), str(daily.trade_date.max()))
    print(json.dumps(report, ensure_ascii=False, indent=2))
