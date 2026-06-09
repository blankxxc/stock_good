export default function Page() {
  return (
    <section className="card">
      <span className="badge">Day 9 advanced model research candidates ready</span>
      <h1>高级模型</h1>
      <p>
        Day 9 已把计划中的 MASTER、StockMixer、HIST 和 TRSR 接入统一模型接口，并在 Day 8
        关系图增强特征矩阵上完成 small-sample run。所有输出都只是 research candidate，不进入正式评分、
        不产生买入/卖出/持有指令。
      </p>
      <div className="grid">
        <div className="card">
          <strong>统一接口</strong>
          <p>
            adapter 实现 fit(train_dataset, valid_dataset, config)、predict(test_dataset)、evaluate、
            register_model_artifact(run_id) 和 explain_feature_dependency(run_id)。
          </p>
        </div>
        <div className="card">
          <strong>MASTER</strong>
          <p>
            使用 market_breadth、market_ret、market_vol_20d、ex_ante_regime_feature 构造 market information
            token，记录 market-guided 输入方式和 feature dependency。
          </p>
        </div>
        <div className="card">
          <strong>StockMixer</strong>
          <p>
            使用 indicator mixing、temporal mixing 和 stock mixing 的本地 adapter，把收益、动量、波动、量能与
            截面标准化特征组合成小样本张量代理。
          </p>
        </div>
        <div className="card">
          <strong>HIST</strong>
          <p>
            基于 Day 8 concept_matrix、行业/概念 spillover、centrality 和 community_momentum 构造概念共享信息输入。
          </p>
        </div>
        <div className="card">
          <strong>TRSR</strong>
          <p>
            基于 relation_matrix、lead_lag_signal、neighbor_return 和 relation_risk_score 构造 Temporal Relational
            Stock Ranking 小样本排序输入。
          </p>
        </div>
        <div className="card">
          <strong>对比报告</strong>
          <p>
            model_comparison_report 输出 LightGBM vs MASTER vs StockMixer vs HIST vs TRSR 的 IC、RankIC、TopK、
            Drawdown、Turnover、Runtime、参数量、训练成本、最差 seed 和 blocked reason。
          </p>
        </div>
        <div className="card">
          <strong>准入状态</strong>
          <p>
            四个模型均标记为 candidate / not_approved_research_candidate_only。官方 repo 生产集成、依赖审查、
            GPU 训练、Day12 模拟盘风控和 Day14 review gate 通过前，不允许进入 approved。
          </p>
        </div>
        <div className="card">
          <strong>Artifacts</strong>
          <p>
            输出 data/gold/advanced_model_predictions、reports/day9/model_comparison_report.json、
            reports/day9/experiment_recorder 以及每个 models/*/adapter.py、run_small_sample.py、environment.lock。
          </p>
        </div>
      </div>
      <p>
        后端 API：/api/models 返回 Day 9 模型对比、成熟度、artifact 和候选状态；/api/experiments 的
        advanced_models 字段同步展示本次实验记录。
      </p>
    </section>
  );
}
