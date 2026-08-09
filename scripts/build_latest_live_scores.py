from __future__ import annotations

import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from models.cograsp_current import (
    CURRENT_DAILY,
    MODEL_FAMILY,
    predict_current_cograsp,
)

INPUT = CURRENT_DAILY
OUTPUT = ROOT / "reports" / "research_loop" / "live_predictions.parquet"
REPORT = ROOT / "reports" / "research_loop" / "live_predictions_report.json"
RUN_ID = "cograsp_current_csi300_inference_v001"
EXPERIMENT_ID = "exp_cograsp_current_csi300_retrained_v001"
RESEARCH_BOUNDARY = "research_signals_only_not_investment_advice"


def _json_default(value: Any) -> Any:
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        number = float(value)
        return None if math.isnan(number) or math.isinf(number) else number
    if isinstance(value, (pd.Timestamp, datetime, Path)):
        return str(value)
    return value


def build_latest_live_scores() -> dict[str, Any]:
    if not INPUT.exists():
        raise FileNotFoundError(
            "Current CSI300 daily input is missing; run: "
            "uv run python scripts/update_daily_market_data.py"
        )
    market = pd.read_parquet(INPUT)
    predictions, metadata = predict_current_cograsp(market)
    input_date = str(metadata["latest_input_date"])
    prediction_target_date = str(metadata["prediction_target_date"])
    model_version = str(metadata["model_version"])

    predictions["trade_date"] = input_date
    predictions["prediction_target_date"] = prediction_target_date
    predictions["horizon"] = "1d"
    predictions["model_name"] = MODEL_FAMILY
    predictions["model_family"] = MODEL_FAMILY
    predictions["model_version"] = model_version
    predictions["run_id"] = RUN_ID
    predictions["experiment_id"] = EXPERIMENT_ID
    predictions["probability_up"] = np.nan
    predictions["probability_down"] = np.nan
    predictions["confidence"] = np.nan
    predictions["signal_direction"] = np.where(
        predictions["predicted_relative_change_pct"].ge(0), "up", "down"
    )
    predictions["information_source"] = "current_market_return_correlation_graph"
    predictions["sentiment_polarity_used"] = False
    predictions["inference_mode"] = "current_universe_locally_retrained_checkpoint"
    predictions["leakage_check_status"] = "chronological_train_validation_test_then_full_retrain"
    predictions["research_boundary"] = RESEARCH_BOUNDARY
    predictions = predictions.sort_values(["rank", "symbol"]).reset_index(drop=True)

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    predictions.to_parquet(OUTPUT, index=False)
    report = {
        "status": "ok",
        "run_id": RUN_ID,
        "experiment_id": EXPERIMENT_ID,
        "model_family": MODEL_FAMILY,
        "model_version": model_version,
        "model_methodology": metadata,
        "latest_trade_date": input_date,
        "prediction_target_date": prediction_target_date,
        "prediction_target_date_is_estimated": metadata.get("prediction_target_date_is_estimated"),
        "horizon": "1d",
        "prediction_rows": int(len(predictions)),
        "model_output_rows": int(len(predictions)),
        "display_overlap_rows": int(len(predictions)),
        "display_policy": "model and website both use the latest complete 300-stock universe",
        "probability_calibration": "none; locally retrained raw regression output is shown",
        "sentiment_status": "not_used_insufficient_current_universe_news_coverage",
        "text_sentiment_coverage": 10,
        "relationship_graph": metadata.get("graph_method"),
        "training_sample_count": metadata.get("sample_count"),
        "latest_training_label_date": metadata.get("latest_training_label_date"),
        "test_metrics": metadata.get("test_metrics"),
        "architecture_modified": metadata.get("architecture_modified"),
        "data_pipeline_adapted": metadata.get("data_pipeline_adapted"),
        "algorithm_modified": False,
        "artifact": str(OUTPUT.relative_to(ROOT)).replace("\\", "/"),
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "research_boundary": RESEARCH_BOUNDARY,
    }
    REPORT.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, default=_json_default),
        encoding="utf-8",
    )
    return report


if __name__ == "__main__":
    print(json.dumps(build_latest_live_scores(), ensure_ascii=False, indent=2, default=_json_default))
