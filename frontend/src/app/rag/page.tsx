export default function Page() {
  return (
    <section className="card">
      <span className="badge">Day 10 RAG evidence system ready</span>
      <h1>RAG 投研证据</h1>
      <p>
        Day 10 已把 RAG 从资料库升级为 claim 级投研证据系统。后端 API：/api/rag 读取真实
        reports/day10 与 data/gold/rag_claims artifact，展示 claim_id、citation_span、evidence_direction、
        evidence_strength、as_of 检索和 license gate 状态。
      </p>
      <div className="grid">
        <div className="card">
          <strong>Claim schema</strong>
          <p>
            rag_claim.schema.yaml 覆盖 claim_id、doc_id、chunk_id、doc_type、claim_type、citation_span、
            source、license_id、event_time、publish_time、ingest_time、available_time、valid_from、valid_to、
            status、content_hash、embedding_model 和 index_version。
          </p>
        </div>
        <div className="card">
          <strong>检索模式</strong>
          <p>
            支持 as_of、present、retrospective_review。as_of 强制 available_time / publish_time 不晚于
            prediction_time，并只返回 approved 且 license 允许展示的 claim。
          </p>
        </div>
        <div className="card">
          <strong>Hybrid retrieval</strong>
          <p>
            本地 BM25、hash-vector search、metadata filter、symbols / industries / concepts graph filter、
            as_of filter 和 hybrid rerank 组合，Milvus/Qdrant/pgvector 后续可替换 adapter。
          </p>
        </div>
        <div className="card">
          <strong>引用卡片</strong>
          <p>
            每条回答必须显示 claim_id、citation_span、source_title、evidence_direction、evidence_strength、
            available_time 和许可证状态。无引用拒答，返回“证据不足 / 待验证假设”。
          </p>
        </div>
        <div className="card">
          <strong>评测门禁</strong>
          <p>
            rag_eval_questions.yaml、expected_citations.yaml、failure_cases.yaml、forbidden_wording_cases.yaml、
            license_cases.yaml 均已生成；门禁要求 time_leakage_rate=0、forbidden_wording_rate=0、
            no_citation_answer_rate=0、citation_support_rate ≥ 90%、Recall@5 ≥ 80%。
          </p>
        </div>
        <div className="card">
          <strong>合规边界</strong>
          <p>
            RAG 只能输出事实、推断、假设、支持证据、反对证据和适用条件；不输出买入、卖出、持有、目标价、
            稳赚或确定上涨等交易指令文案。
          </p>
        </div>
        <div className="card">
          <strong>Artifacts</strong>
          <p>
            输出 data/gold/rag_documents、data/gold/rag_chunks、data/gold/rag_claims、
            reports/day10/rag_evidence_report.json、rag_eval_report.json、rag_answer_cards.json 和
            rag_citation_cards.html。
          </p>
        </div>
      </div>
    </section>
  );
}
