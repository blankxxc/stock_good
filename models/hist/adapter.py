from __future__ import annotations

from models.advanced_models_advanced_models import advanced_modelsAdvancedModelAdapter, MODEL_SPECS

MODEL_NAME = "HIST"
SPEC = MODEL_SPECS[MODEL_NAME]


def build_adapter(seed: int = 42) -> advanced_modelsAdvancedModelAdapter:
    """Return the advanced_models local small-sample HIST adapter."""
    return advanced_modelsAdvancedModelAdapter(SPEC, seed=seed)
