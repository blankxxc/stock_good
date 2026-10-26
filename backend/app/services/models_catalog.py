from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any


def project_root() -> Path:
    return Path(__file__).resolve().parents[3]


MODEL_DEFINITIONS = (
    ("cograsp", "COGRASP", "价格序列与收益相关性图，预测下一交易日相对涨跌。", "live_predictions"),
    ("sentiment_event", "情绪融合 LightGBM", "融合股票时序、市场情绪代理与可选新闻事件。", "sentiment_event_predictions"),
)


def _number(value: Any) -> float | None:
    return float(value) if isinstance(value, (int, float)) and math.isfinite(value) else None


def models_payload(research_boundary: str, *, root: Path | None = None) -> dict[str, Any]:
    root = project_root() if root is None else root
    models = []
    for model_id, label, description, stem in MODEL_DEFINITIONS:
        report_path = root / "reports" / "research_loop" / f"{stem}_report.json"
        predictions_path = report_path.with_name(f"{stem}.parquet")
        report = json.loads(report_path.read_text(encoding="utf-8")) if report_path.exists() else {}
        methodology = report.get("model_methodology") or {}
        metrics = report.get("test_metrics") or methodology.get("test_metrics") or {}
        split = methodology.get("chronological_split") or {}
        models.append({
            "id": model_id,
            "label": label,
            "description": description,
            "status": "ready" if report.get("status") == "ok" and predictions_path.exists() else "pending",
            "model_version": report.get("model_version"),
            "latest_trade_date": report.get("latest_trade_date"),
            "prediction_target_date": report.get("prediction_target_date"),
            "prediction_rows": report.get("prediction_rows", 0),
            "training_sample_count": report.get("training_sample_count"),
            "test_start_date": split.get("test_start_date"),
            "test_end_date": split.get("test_end_date"),
            "test_metrics": {name: _number(metrics.get(name)) for name in ("mae", "mse", "ic_mean", "rank_ic_mean")},
        })
    return {
        "module": "models",
        "status": "daily_models_ready" if all(model["status"] == "ready" for model in models) else "daily_models_pending",
        "model_count": len(models),
        "models": models,
        "research_boundary": research_boundary,
    }
