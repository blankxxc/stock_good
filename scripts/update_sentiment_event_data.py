from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from data.adapters.sentiment_event_data import update_sentiment_event_data


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build market-sentiment proxies and optionally incrementally fetch real CSI300 news."
    )
    parser.add_argument(
        "--fetch-news",
        action="store_true",
        help="Fetch recent Eastmoney stock news through AkShare; omitted means market proxies only.",
    )
    parser.add_argument("--symbols", nargs="*", default=None, help="Optional stock symbols/codes.")
    parser.add_argument("--max-symbols", type=int, default=None)
    parser.add_argument("--lookback-days", type=int, default=30)
    parser.add_argument("--request-delay-seconds", type=float, default=0.05)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    report = update_sentiment_event_data(
        fetch_news=args.fetch_news,
        symbols=args.symbols,
        max_symbols=args.max_symbols,
        lookback_days=args.lookback_days,
        request_delay_seconds=args.request_delay_seconds,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
