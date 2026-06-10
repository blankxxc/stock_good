from __future__ import annotations

import json

from models.advanced_models_advanced_models import run_single_model_cli

if __name__ == "__main__":
    print(json.dumps(run_single_model_cli("MASTER"), ensure_ascii=False, indent=2))
