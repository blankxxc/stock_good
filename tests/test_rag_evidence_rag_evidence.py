from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import yaml
from fastapi.testclient import TestClient

from tests.auth_helpers import authenticated_admin_client

PROJECT_ROOT = Path(__file__).resolve().parents[1]
RESEARCH_BOUNDARY = "research_signals_only_not_investment_advice"
REQUIRED_DOC_TYPES = {
    "paper",
    "factor_card",
    "strategy_card",
    "experiment_card",
    "backtest_report",
    "failure_case",
    "market_review",
    "announcement",
    "news",
    "research_note",
    "relation_case",
}
REQUIRED_CLAIM_FIELDS = {
    "claim_id",
    "doc_id",
    "chunk_id",
    "doc_type",
    "claim_type",
    "claim_text",
    "citation_span",
    "source_title",
    "source_url",
    "source_quality",
    "license_id",
    "redisplay_allowed",
    "export_allowed",
    "event_time",
    "publish_time",
    "ingest_time",
    "available_time",
    "valid_from",
    "valid_to",
    "symbols",
    "industries",
    "concepts",
    "related_factor_ids",
    "related_model_ids",
    "related_experiment_ids",
    "related_run_ids",
    "evidence_direction",
    "evidence_strength",
    "confidence",
    "status",
    "schema_version",
    "content_hash",
    "embedding_model",
    "index_version",
}


def _ensure_rag_evidence() -> dict:
    from rag.rag_evidence_evidence_system import run_rag_evidence_rag_pipeline

    return run_rag_evidence_rag_pipeline(write_outputs=True)


def test_rag_evidence_builds_claim_level_artifacts_and_complete_schema():
    report = _ensure_rag_evidence()
    assert report["status"] == "ok"
    assert report["maturity"] == "L1-L2-claim-evidence-rag"
    assert set(report["document_types_supported"]) == REQUIRED_DOC_TYPES
    assert report["document_count"] >= len(REQUIRED_DOC_TYPES)
    assert report["chunk_count"] >= report["document_count"]
    assert report["claim_count"] >= report["chunk_count"]
    assert report["license_gate_status"] == "passed"
    assert report["research_boundary"] == RESEARCH_BOUNDARY

    schema = yaml.safe_load((PROJECT_ROOT / "rag" / "schemas" / "rag_claim.schema.yaml").read_text(encoding="utf-8"))
    schema_fields = {field["name"] for field in schema["fields"]}
    assert REQUIRED_CLAIM_FIELDS.issubset(schema_fields)
    assert schema["primary_key"] == ["claim_id"]
    assert schema["layer"] == "RAG"

    claims_path = PROJECT_ROOT / report["artifacts"]["rag_claims"]
    chunks_path = PROJECT_ROOT / report["artifacts"]["rag_chunks"]
    docs_path = PROJECT_ROOT / report["artifacts"]["rag_documents"]
    claims = pd.read_parquet(claims_path)
    chunks = pd.read_parquet(chunks_path)
    docs = pd.read_parquet(docs_path)
    assert not claims.empty and not chunks.empty and not docs.empty
    assert REQUIRED_CLAIM_FIELDS.issubset(set(claims.columns))
    assert set(claims["doc_type"]).issubset(REQUIRED_DOC_TYPES)
    assert claims["claim_id"].is_unique
    assert claims["citation_span"].astype(str).str.len().gt(0).all()


def test_rag_evidence_as_of_present_retrospective_and_license_filters_work():
    _ensure_rag_evidence()
    from rag.rag_evidence_evidence_system import retrieve_claims

    early = retrieve_claims(
        "公告 情绪 因子 可用时间",
        mode="as_of",
        prediction_time="2026-01-04T15:00:00+00:00",
        display_context="redisplay",
        top_k=10,
    )
    assert early["mode"] == "as_of"
    assert early["time_leakage_count"] == 0
    assert early["license_block_count"] >= 1
    assert early["claims"]
    assert all(item["available_time"] <= "2026-01-04T15:00:00+00:00" for item in early["claims"])
    assert all(item["publish_time"] <= "2026-01-04T15:00:00+00:00" for item in early["claims"])
    assert all(item["status"] == "approved" for item in early["claims"])
    assert all(item["redisplay_allowed"] is True for item in early["claims"])
    assert not any("future_ann_001" in item["claim_id"] for item in early["claims"])

    present = retrieve_claims("公告 情绪 因子 可用时间", mode="present", display_context="redisplay", top_k=10)
    assert present["mode"] == "present"
    assert any("future_ann_001" in item["claim_id"] for item in present["claims"])

    retrospective = retrieve_claims(
        "回撤 失败 案例 未来函数",
        mode="retrospective_review",
        prediction_time="2026-01-04T15:00:00+00:00",
        display_context="internal",
        top_k=10,
    )
    assert retrospective["retrospective_review"] is True
    assert retrospective["claims"]
    assert all(item["mode_label"] == "retrospective_review" for item in retrospective["claims"])


def test_rag_evidence_answer_constraints_eval_and_backend_frontend_are_ready():
    report = _ensure_rag_evidence()
    from backend.app.main import app
    from rag.rag_evidence_evidence_system import answer_with_evidence
    from scripts.check_rag_evidence_acceptance import run_acceptance

    answer = answer_with_evidence("relation_spillover 是否有 ablation 证据？", mode="present")
    assert answer["answer_status"] == "answered_with_citations"
    assert answer["supporting_evidence"]
    assert answer["citations"]
    assert {"facts", "inferences", "hypotheses", "supporting_evidence", "contradicting_evidence", "applicable_conditions"}.issubset(answer)
    forbidden = "买入 卖出 持有 目标价 稳赚 确定上涨"
    assert not any(word in json.dumps(answer, ensure_ascii=False) for word in forbidden.split())

    abstain = answer_with_evidence("不存在的火星矿业股票稳赚吗", mode="present")
    assert abstain["answer_status"] == "abstained_no_citation"
    assert abstain["facts"] == []
    assert abstain["citations"] == []

    eval_report = json.loads((PROJECT_ROOT / report["artifacts"]["rag_eval_report"]).read_text(encoding="utf-8"))
    assert eval_report["status"] == "ok"
    assert eval_report["time_leakage_rate"] == 0
    assert eval_report["forbidden_wording_rate"] == 0
    assert eval_report["no_citation_answer_rate"] == 0
    assert eval_report["abstention_accuracy"] >= 0.95
    assert eval_report["citation_support_rate"] >= 0.90
    assert eval_report["recall_at_5"] >= 0.80

    client = authenticated_admin_client(app)
    rag = client.get("/api/rag")
    health = client.get("/health")
    assert rag.status_code == 200
    payload = rag.json()
    assert payload["status"] == "rag_evidence_rag_evidence_ready"
    assert payload["claim_count"] == report["claim_count"]
    assert payload["retrieval_modes"] == ["as_of", "present", "retrospective_review"]
    assert payload["sample_citation_cards"]
    assert health.status_code == 200
    assert health.json()["modules"]["rag"] == "rag_evidence_claim_evidence_rag_ready"

    page = (PROJECT_ROOT / "frontend" / "src" / "app" / "rag" / "page.tsx").read_text(encoding="utf-8")
    assert "rag_evidence" in page
    assert "/api/rag" in page
    assert "claim_id" in page and "as_of" in page and "evidence_strength" in page
    assert "无引用拒答" in page

    acceptance = run_acceptance()
    assert acceptance["status"] == "ok"
    assert acceptance["checks"] >= 17
    assert acceptance["failed"] == []
