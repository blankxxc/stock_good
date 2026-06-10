from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from quality.data_trust_data_trust import run_data_trust_data_trust


if __name__ == "__main__":
    print(json.dumps(run_data_trust_data_trust(), ensure_ascii=False, indent=2))
