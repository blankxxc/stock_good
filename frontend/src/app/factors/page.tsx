export default function Page() {
  return (
    <section className="card">
      <span className="badge">Day 7 event/regime factors ready</span>
      <h1>因子库</h1>
      <p>
        Day 7 已在 Day 4 离线因子库之上增加新闻/公告/事件因子、金融文本 baseline、market regime、
        增强版 model_feature_matrix_wide_day7 和 LightGBM smoke ablation。所有事件特征显式保留
        publish_time / available_time / prediction_time，避免把未来文本或事后 regime 标签喂给模型。
      </p>
      <div className="grid">
        <div className="card">
          <strong>Day 4：74 个离线因子</strong>
          <p>
            收益、动量、反转、波动率、流动性、价量结构、均线偏离、风格代理、行业中性和横截面标准化仍保留；
            point_in_time_violations=0，作为 Day 7 增强矩阵的 base price/volume/fundamental factors。
          </p>
        </div>
        <div className="card">
          <strong>事件因子</strong>
          <p>
            factor_news_sentiment_panel 输出 news_sentiment_1d/3d/5d、announcement_sentiment、event_count、
            negative_event_count、source_weighted_sentiment、novelty_score、event_authority_score、
            event_decay_5m/1h/1d/5d、policy_event_score 和 macro_event_score。
          </p>
        </div>
        <div className="card">
          <strong>金融文本 baseline</strong>
          <p>
            FinBERT-compatible lexicon baseline 与 keyword event classifier 已可运行；FinGPT/LLM 只作为摘要、抽取、
            RAG 和辅助标签工具，不能直接产出买卖建议或未经回测的交易信号。
          </p>
        </div>
        <div className="card">
          <strong>market regime</strong>
          <p>
            factor_market_regime_panel 输出 market_breadth、market_ret_1d/5d/20d、market_vol_20d、drawdown、
            amount_percentile_252d、small_vs_large_return、growth_vs_value_return、industry_dispersion、
            northbound_flow_zscore、liquidity_regime 和 risk_appetite_proxy。
          </p>
        </div>
        <div className="card">
          <strong>Regime 时间语义</strong>
          <p>
            ex_ante_regime_feature 是预测时点可用的模型特征；ex_post_regime_label 只用于事后复盘解释，
            标记为 report_only_not_training_feature。
          </p>
        </div>
        <div className="card">
          <strong>Ablation</strong>
          <p>
            reports/day7/event_regime_ablation_report.json 覆盖 Base、Base + market_regime、Base + news_event、
            Full - market_regime、Full - news_event 等 smoke run。relation_spillover 在 Day 7 是占位，Day 8 图谱因子替换。
          </p>
        </div>
      </div>
      <p>
        后端 API：/api/factors 返回 Day 4 因子库状态，并在 event_regime 字段展示 Day 7 事件因子、market regime、
        latest_available_time、leakage_check_status 和 ablation 状态。
      </p>
    </section>
  );
}
