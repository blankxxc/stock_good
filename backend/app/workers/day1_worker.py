from __future__ import annotations

import json
import os
import signal
import sys
import time
from datetime import datetime, timezone

RUNNING = True


def _stop(_signum: int, _frame: object) -> None:
    global RUNNING
    RUNNING = False


signal.signal(signal.SIGTERM, _stop)
signal.signal(signal.SIGINT, _stop)


def status_payload() -> dict[str, str]:
    return {
        "status": "ok",
        "service": "stock-good-day1-worker",
        "role": os.getenv("WORKER_ROLE", "day1-scaffold-worker"),
        "time": datetime.now(timezone.utc).isoformat(),
        "research_boundary": "research_signals_only_not_investment_advice",
    }


def main() -> int:
    print(json.dumps(status_payload(), ensure_ascii=False), flush=True)
    while RUNNING:
        time.sleep(30)
    print(json.dumps({"status": "stopped", "service": "stock-good-day1-worker"}), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
