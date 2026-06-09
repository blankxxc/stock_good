export default function Page() {
  return (
    <section className="card">
      <span className="badge">Day 8 relation graph factors ready</span>
      <h1>关系图</h1>
      <p>
        Day 8 已把计划中的行业、概念、指数成分、供应链、新闻共现、价格相关和 lead-lag 关系落成
        stock_relation_edge，并用 NetworkX 计算 centrality / community，再生成 factor_relation_panel 和
        model_feature_matrix_wide_day8。页面只展示研究信号与解释，不给确定性买卖建议。
      </p>
      <div className="grid">
        <div className="card">
          <strong>stock_relation_edge</strong>
          <p>
            关系边包含 src_symbol、dst_symbol、relation_type、relation_weight、confidence、direction、
            start_time/end_time、available_time/prediction_time、license_id 与 research_boundary。
          </p>
        </div>
        <div className="card">
          <strong>Spark-style 价格相关边</strong>
          <p>
            spark/jobs/build_day8_price_corr_edges.py 用 Day 7 特征矩阵生成 price_corr 边；本地 L1/L2 PoC
            采用 Spark-compatible batch job，保留后续切换真实 Spark 集群的边界。
          </p>
        </div>
        <div className="card">
          <strong>NetworkX 图指标</strong>
          <p>
            使用 degree centrality、PageRank 和 greedy modularity community 生成 centrality_score、
            community_momentum，并写入 reports/day8/graph_summary.json。
          </p>
        </div>
        <div className="card">
          <strong>factor_relation_panel</strong>
          <p>
            输出 neighbor_return_5m、neighbor_return_1d、neighbor_volume_shock、neighbor_sentiment_1h、
            industry_spillover、concept_spillover、supply_chain_spillover、lead_lag_signal、relation_risk_score、
            centrality_score、community_momentum 和 correlation_cluster_momentum。
          </p>
        </div>
        <div className="card">
          <strong>HIST / TRSR adapter</strong>
          <p>
            data/gold/graph_model_adapters/hist_trsr 已生成 stock_id_mapping、relation_type_mapping、
            relation_matrix、concept_matrix、stock_feature_tensor 和 label_tensor，用于后续图模型接入。
          </p>
        </div>
        <div className="card">
          <strong>Ablation 与安全边界</strong>
          <p>
            relation_factor_ablation_report 覆盖 base_day7、base_plus_relation_graph、full_minus_relation_graph。
            即使 smoke 指标有增益，也标记为 not_approved_research_candidate_only，必须后续走回测、风险和报告审批。
          </p>
        </div>
      </div>
      <p>
        后端 API：/api/graph 返回 Day 8 关系图状态；/api/factors 的 relation_graph 字段同步展示关系边、
        图指标、HIST / TRSR adapter、ablation 和 leakage_check_status。
      </p>
    </section>
  );
}
