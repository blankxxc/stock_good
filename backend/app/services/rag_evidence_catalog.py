from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd


def project_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _safe_records(frame: pd.DataFrame, limit: int = 5) -> list[dict[str, Any]]:
    if frame.empty:
        return []
    records: list[dict[str, Any]] = []
    for raw in frame.head(limit).to_dict(orient="records"):
        row: dict[str, Any] = {}
        for key, value in raw.items():
            try:
                if pd.isna(value):
                    row[key] = None
                    continue
            except (TypeError, ValueError):
                row[key] = value
                continue
            row[key] = value
        records.append(row)

    return records


def rag_evidence_report() -> dict[str, Any]:
    root = project_root()
    report_path = root / "reports" / "rag_evidence" / "rag_evidence_report.json"
    if not report_path.exists():
        from rag.rag_evidence_evidence_system import run_rag_evidence_rag_pipeline

        run_rag_evidence_rag_pipeline(write_outputs=True)
    return _read_json(report_path)


def rag_payload(research_boundary: str) -> dict[str, Any]:
    root = project_root()
    report = rag_evidence_report()
    if report.get("status") != "ok":
        return {
            "module": "rag",
            "status": "rag_evidence_rag_evidence_pending",
            "maturity": "L1-route-stub",
            "research_boundary": research_boundary,
        }
    claims_path = root / report["artifacts"]["rag_claims"]
    answer_path = root / report["artifacts"]["rag_answer_cards"]
    eval_path = root / report["artifacts"]["rag_eval_report"]
    claims = pd.read_parquet(claims_path) if claims_path.exists() else pd.DataFrame()
    answer = _read_json(answer_path)
    eval_report = _read_json(eval_path)
    citation_cards = answer.get("citations", [])[:5]
    evidence_rows = []
    if not claims.empty:
        evidence_rows = _safe_records(
            claims[
                [
                    "claim_id",
                    "doc_type",
                    "claim_type",
                    "citation_span",
                    "source_title",
                    "evidence_direction",
                    "evidence_strength",
                    "license_id",
                    "redisplay_allowed",
                    "available_time",
                    "index_version",
                ]
            ].sort_values(["evidence_direction", "claim_id"]),
            limit=8,
        )
    return {
        "module": "rag",
        "status": "rag_evidence_rag_evidence_ready",
        "maturity": report.get("maturity"),
        "research_boundary": research_boundary,
        "document_types_supported": report.get("document_types_supported", []),
        "document_count": report.get("document_count"),
        "chunk_count": report.get("chunk_count"),
        "claim_count": report.get("claim_count"),
        "retrieval_modes": report.get("retrieval_modes", []),
        "retrieval_components": report.get("retrieval_components", []),
        "license_gate_status": report.get("license_gate_status"),
        "eval_status": report.get("eval_status"),
        "eval_metrics": {
            "time_leakage_rate": eval_report.get("time_leakage_rate"),
            "forbidden_wording_rate": eval_report.get("forbidden_wording_rate"),
            "no_citation_answer_rate": eval_report.get("no_citation_answer_rate"),
            "abstention_accuracy": eval_report.get("abstention_accuracy"),
            "citation_support_rate": eval_report.get("citation_support_rate"),
            "recall_at_5": eval_report.get("recall_at_5"),
        },
        "sample_citation_cards": citation_cards,
        "sample_claim_rows": evidence_rows,
        "artifacts": report.get("artifacts", {}),
        "api_note": "RAG outputs cite claim_id/citation_span and abstain when evidence or license gates fail; no trading instructions are produced.",
    }
