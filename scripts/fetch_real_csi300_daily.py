from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from data.adapters.real_csi300_akshare import write_real_csi300_daily, _json_default


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch recent 3-year real CSI300 daily data via akshare into data/real/csi300_daily.")
    parser.add_argument("--max-symbols", type=int, default=None, help="Optional smoke limit; omit for full CSI300.")
    parser.add_argument("--start-date", default=None, help="YYYYMMDD; defaults to about 3 years ago.")
    parser.add_argument("--end-date", default=None, help="YYYYMMDD; defaults to today.")
    args = parser.parse_args()
    report = write_real_csi300_daily(max_symbols=args.max_symbols, start_date=args.start_date, end_date=args.end_date)
    print(json.dumps(report, ensure_ascii=False, indent=2, default=_json_default))


if __name__ == "__main__":
    main()
