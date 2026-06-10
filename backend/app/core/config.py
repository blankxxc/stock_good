from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    project_name: str = "stock-research-platform"
    environment: str = "local"
    research_boundary: str = "research_signals_only_not_investment_advice"
    project_root: Path = Path(__file__).resolve().parents[3]
    default_data_version: str = "foundation-sample-v0"
    default_schema_version: str = "v0.1.0"


settings = Settings()
