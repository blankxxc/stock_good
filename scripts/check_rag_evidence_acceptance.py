from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

RESEARCH_BOUNDARY = "research_signals_only_not_investment_advice"
rag_evidence_DIR = ROOT / "reports" / "rag_evidence"
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


def _json_default(value: Any) -> Any:
    try:
        if pd.isna(value):
            return None
    except Exception:
        pass
    return str(value)


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def run_acceptance() -> dict[str, Any]:
    from backend.app.main import app
    from fastapi.testclient import TestClient
    from rag.rag_evidence_evidence_system import answer_with_evidence, retrieve_claims, run_rag_evidence_rag_pipeline

    report = run_rag_evidence_rag_pipeline(write_outputs=True)
    claims_path = ROOT / report["artifacts"]["rag_claims"]
    chunks_path = ROOT / report["artifacts"]["rag_chunks"]
    docs_path = ROOT / report["artifacts"]["rag_documents"]
    claims = pd.read_parquet(claims_path) if claims_path.exists() else pd.DataFrame()
    chunks = pd.read_parquet(chunks_path) if chunks_path.exists() else pd.DataFrame()
    docs = pd.read_parquet(docs_path) if docs_path.exists() else pd.DataFrame()
    schema = yaml.safe_load((ROOT / "rag" / "schemas" / "rag_claim.schema.yaml").read_text(encoding="utf-8"))
    eval_report = _read_json(ROOT / report["artifacts"]["rag_eval_report"])
    early = retrieve_claims(
        "公告 情绪 因子 可用时间",
        mode="as_of",
        prediction_time="2026-01-04T15:00:00+00:00",
        display_context="redisplay",
        top_k=10,
    )
    present = retrieve_claims("公告 情绪 因子 可用时间", mode="present", display_context="redisplay", top_k=10)
    answer = answer_with_evidence("relation_spillover 是否有 ablation 证据？", mode="present")
    abstain = answer_with_evidence("不存在的火星矿业股票稳赚吗", mode="present")
    client = TestClient(app)
    api_rag = client.get("/api/rag")
    health = client.get("/health")
    page = (ROOT / "frontend" / "src" / "app" / "rag" / "page.tsx").read_text(encoding="utf-8")

    failed: list[str] = []

    def check(name: str, condition: bool) -> None:
        if not condition:
            failed.append(name)

    schema_fields = {field["name"] for field in schema.get("fields", [])}
    check("rag_evidence_report_ok", report.get("status") == "ok")
    check("document_types_supported", set(report.get("document_types_supported", [])) == REQUIRED_DOC_TYPES)
    check("artifacts_written", claims_path.is_file() and chunks_path.is_file() and docs_path.is_file() and not claims.empty and not chunks.empty and not docs.empty)
    check("claim_schema_complete", REQUIRED_CLAIM_FIELDS.issubset(schema_fields) and schema.get("primary_key") == ["claim_id"])
    check("claim_columns_complete", not claims.empty and REQUIRED_CLAIM_FIELDS.issubset(set(claims.columns)))
    check("claim_ids_unique", not claims.empty and claims["claim_id"].is_unique)
    check("citation_spans_present", not claims.empty and claims["citation_span"].astype(str).str.len().gt(0).all())
    check("as_of_filters_future_documents", early.get("time_leakage_count") == 0 and not any("future_ann_001" in item["claim_id"] for item in early.get("claims", [])))
    check("license_gate_blocks_redisplay", early.get("license_block_count", 0) >= 1)
    check("present_mode_includes_future_after_available", any("future_ann_001" in item["claim_id"] for item in present.get("claims", [])))
    check("answer_has_citations", answer.get("answer_status") == "answered_with_citations" and bool(answer.get("citations")))
    check("abstains_without_citation", abstain.get("answer_status") == "abstained_no_citation" and abstain.get("citations") == [])
    check("eval_gate_passed", eval_report.get("status") == "ok" and eval_report.get("time_leakage_rate") == 0 and eval_report.get("forbidden_wording_rate") == 0 and eval_report.get("no_citation_answer_rate") == 0)
    check("eval_thresholds_met", eval_report.get("abstention_accuracy", 0) >= 0.95 and eval_report.get("citation_support_rate", 0) >= 0.90 and eval_report.get("recall_at_5", 0) >= 0.80)
    check("backend_rag_api_ready", api_rag.status_code == 200 and api_rag.json().get("status") == "rag_evidence_rag_evidence_ready")
    check("health_module_ready", health.status_code == 200 and health.json().get("modules", {}).get("rag") == "rag_evidence_claim_evidence_rag_ready")
    check("frontend_rag_page_rag_evidence_ready", "rag_evidence" in page and "/api/rag" in page and "claim_id" in page and "as_of" in page and "无引用拒答" in page)
    check("research_boundary_enforced", report.get("research_boundary") == RESEARCH_BOUNDARY and api_rag.json().get("research_boundary") == RESEARCH_BOUNDARY)

    result = {
        "status": "ok" if not failed else "failed",
        "checks": 18,
        "failed": failed,
        "document_count": report.get("document_count"),
        "claim_count": report.get("claim_count"),
        "eval_status": eval_report.get("status"),
        "time_leakage_rate": eval_report.get("time_leakage_rate"),
        "license_gate_status": report.get("license_gate_status"),
        "artifacts": report.get("artifacts", {}),
    }
    rag_evidence_DIR.mkdir(parents=True, exist_ok=True)
    (rag_evidence_DIR / "acceptance_report.json").write_text(json.dumps(result, ensure_ascii=False, indent=2, default=_json_default), encoding="utf-8")
    return result


if __name__ == "__main__":
    print(json.dumps(run_acceptance(), ensure_ascii=False, indent=2, default=_json_default))
