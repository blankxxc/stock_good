from __future__ import annotations

from models.day9_advanced_models import Day9AdvancedModelAdapter, MODEL_SPECS

MODEL_NAME = "TRSR"
SPEC = MODEL_SPECS[MODEL_NAME]


def build_adapter(seed: int = 42) -> Day9AdvancedModelAdapter:
    """Return the Day 9 local small-sample TRSR adapter."""
    return Day9AdvancedModelAdapter(SPEC, seed=seed)
