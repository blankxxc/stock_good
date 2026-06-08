export default function Page() {
  return (
    <section className="card">
      <span className="badge">Day 4 L2 offline factor store ready</span>
      <h1>因子库</h1>
      <p>
        Day 4 已把离线因子从路线图占位推进到可验收 artifact：Polars 优先的本地因子引擎、
        configs/factor/factor_spec.yaml、feature_store/feature_registry.yaml、point-in-time join、
        Spark materialization consistency check、单因子分析报告和风险模型输入全部生成。
      </p>
      <div className="grid">
        <div className="card">
          <strong>74 个离线因子</strong>
          <p>
            覆盖收益、动量、反转、波动率、流动性、价量结构、均线偏离、风格代理、行业中性和横截面标准化；
            每个因子都有经济假设、公式、lookback、缺失处理、标准化/中性化和泄漏风险说明。
          </p>
        </div>
        <div className="card">
          <strong>Feature Store</strong>
          <p>
            feature_registry.yaml、day4_factor_daily_view.yaml 与 day4_materialize_feature_matrix.yaml 已就绪；
            data/gold/model_feature_matrix_wide 是按 symbol + trade_date + prediction_time 生成的宽表特征矩阵。
          </p>
        </div>
        <div className="card">
          <strong>Point-in-time join</strong>
          <p>
            build_model_feature_matrix.py 验证 available_time &lt;= prediction_time，当前 point_in_time_violations=0，
            避免用未来数据生成训练特征。
          </p>
        </div>
        <div className="card">
          <strong>Spark / Polars 一致性</strong>
          <p>
            spark/jobs/day4_factor_materialization.py 已用 PySpark 重新物化核心因子，并和 Polars 输出逐因子比较；
            reports/day4/spark_factor_materialization_report.json 显示 consistency_status=passed。
          </p>
        </div>
        <div className="card">
          <strong>单因子报告</strong>
          <p>
            reports/day4/factors 下生成覆盖率、缺失率、异常率、换手、IC、RankIC、ICIR、HAC/Newey-West t 统计、
            分位数组合、成本调整 spread、容量估计和多重检验风险字段。
          </p>
        </div>
        <div className="card">
          <strong>风险模型输入</strong>
          <p>
            risk_factor_exposure、risk_factor_covariance、specific_risk 已输出，包含 size、beta、value、momentum、
            volatility、liquidity、quality、growth、residual_volatility 与行业暴露，供后续模型和回测控制风险。
          </p>
        </div>
      </div>
      <p>
        后端 API：/api/factors 返回 Day 4 因子库状态、artifact 路径、单因子报告摘要、风险输出和 Spark 一致性状态。
      </p>
    </section>
  );
}
