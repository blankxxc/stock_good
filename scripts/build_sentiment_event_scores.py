from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from models.sentiment_event_fusion import build_sentiment_event_scores


if __name__ == "__main__":
    print(json.dumps(build_sentiment_event_scores(), ensure_ascii=False, indent=2))
