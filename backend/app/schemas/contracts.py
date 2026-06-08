from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class ContractField(BaseModel):
    name: str
    type: str
    nullable: bool
    primary_key: bool = False
    unique_key: bool = False
    time_semantic: str | None = None
    unit: str | None = None
    range: str | None = None
    anomaly_rule: str | None = None
    backfill_allowed: bool = True


class DataContract(BaseModel):
    table: str
    layer: Literal["ODS", "DWD", "DWS", "ADS", "RAG"]
    schema_version: str = Field(pattern=r"^v")
    primary_key: list[str]
    unique_key: list[str]
    fields: list[ContractField]
