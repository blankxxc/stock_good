"""Day 1 metadata registry scaffold.

Revision ID: 0001_day1_metadata
Revises:
Create Date: 2026-06-07
"""
from __future__ import annotations

from typing import Iterable

import sqlalchemy as sa
from alembic import op

revision = "0001_day1_metadata"
down_revision = None
branch_labels = None
depends_on = None

TABLES: dict[str, list[sa.Column]] = {
    "users": [],
    "roles": [],
    "permissions": [],
    "audit_log": [
        sa.Column("actor", sa.String(length=128)),
        sa.Column("action", sa.String(length=128)),
        sa.Column("resource_type", sa.String(length=128)),
        sa.Column("resource_id", sa.String(length=128)),
        sa.Column("trace_id", sa.String(length=128)),
    ],
    "data_license_registry": [],
    "data_snapshot_registry": [],
    "dataset_snapshot_manifest": [
        sa.Column("snapshot_id", sa.String(length=128), unique=True),
        sa.Column("data_version", sa.String(length=64)),
        sa.Column("source", sa.String(length=128)),
        sa.Column("license_id", sa.String(length=128)),
        sa.Column("manifest_hash", sa.String(length=128)),
        sa.Column("status", sa.String(length=64)),
        sa.Column("as_of", sa.String(length=64)),
    ],
    "schema_registry": [
        sa.Column("schema_name", sa.String(length=128)),
        sa.Column("schema_version", sa.String(length=64)),
        sa.Column("layer", sa.String(length=64)),
        sa.Column("contract_path", sa.String(length=512)),
    ],
    "factor_registry": [],
    "feature_registry": [],
    "model_registry": [],
    "experiment_run": [],
    "pipeline_task_run": [],
    "spark_job_run": [
        sa.Column("run_id", sa.String(length=128), unique=True),
        sa.Column("job_name", sa.String(length=128)),
        sa.Column("input_snapshot_id", sa.String(length=128)),
        sa.Column("output_snapshot_id", sa.String(length=128)),
        sa.Column("config_hash", sa.String(length=128)),
        sa.Column("status", sa.String(length=64)),
    ],
    "flink_job_run": [
        sa.Column("run_id", sa.String(length=128), unique=True),
        sa.Column("job_name", sa.String(length=128)),
        sa.Column("input_topics", sa.Text()),
        sa.Column("output_topics", sa.Text()),
        sa.Column("checkpoint_path", sa.String(length=512)),
        sa.Column("status", sa.String(length=64)),
    ],
    "report_registry": [],
    "rag_document": [],
    "rag_chunk": [],
    "rag_claim": [
        sa.Column("claim_id", sa.String(length=128), unique=True),
        sa.Column("document_id", sa.String(length=128)),
        sa.Column("citation_span", sa.Text()),
        sa.Column("evidence_direction", sa.String(length=64)),
        sa.Column("evidence_strength", sa.String(length=64)),
        sa.Column("as_of", sa.String(length=64)),
    ],
    "graph_node": [],
    "graph_edge": [],
    "simulation_account": [],
    "simulation_order": [],
    "simulation_position": [],
    "export_manifest": [
        sa.Column("export_id", sa.String(length=128), unique=True),
        sa.Column("report_id", sa.String(length=128)),
        sa.Column("license_gate_status", sa.String(length=64)),
        sa.Column("file_hash", sa.String(length=128)),
        sa.Column("status", sa.String(length=64)),
    ],
    "backfill_request": [],
    "adr_record": [],
    "risk_register_item": [
        sa.Column("risk_id", sa.String(length=128), unique=True),
        sa.Column("title", sa.String(length=256)),
        sa.Column("severity", sa.String(length=64)),
        sa.Column("mitigation", sa.Text()),
        sa.Column("owner", sa.String(length=128)),
        sa.Column("status", sa.String(length=64)),
    ],
}


def base_columns() -> list[sa.Column]:
    return [
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True)),
    ]


def table_definition(name: str, extra_columns: Iterable[sa.Column]) -> sa.Table:
    return sa.Table(name, sa.MetaData(), *base_columns(), *list(extra_columns))


def upgrade() -> None:
    bind = op.get_bind()
    for table_name, extra_columns in TABLES.items():
        table_definition(table_name, extra_columns).create(bind=bind, checkfirst=True)


def downgrade() -> None:
    bind = op.get_bind()
    for table_name, extra_columns in reversed(TABLES.items()):
        table_definition(table_name, extra_columns).drop(bind=bind, checkfirst=True)
