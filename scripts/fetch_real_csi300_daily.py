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
    parser = argparse.ArgumentParser(description="Incrementally fetch CSI300 daily bars via BaoStock/AkShare into data/real/csi300_daily.")
    parser.add_argument("--max-symbols", type=int, default=None, help="Diagnostic smoke limit; validates a subset without publishing production Parquet.")
    parser.add_argument("--start-date", default=None, help="YYYYMMDD; defaults to about 3 years ago.")
    parser.add_argument("--end-date", default=None, help="YYYYMMDD; defaults to today.")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--full-refresh", action="store_true", help="Replace the local three-year dataset; the default is incremental.")
    mode.add_argument("--incremental", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--use-snapshot", action="store_true", help="Also save a separate intraday snapshot; it is never merged into official adjusted daily bars.")
    parser.add_argument("--overlap-days", type=int, default=7, help="Calendar-day overlap used to detect upstream corrections.")
    args = parser.parse_args()
    report = write_real_csi300_daily(
        max_symbols=args.max_symbols,
        start_date=args.start_date,
        end_date=args.end_date,
        incremental=not args.full_refresh,
        overlap_days=args.overlap_days,
        use_snapshot=args.use_snapshot,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2, default=_json_default))
    raise SystemExit(0 if report.get("status") in {"ok", "no_change"} else 1)


if __name__ == "__main__":
    main()
