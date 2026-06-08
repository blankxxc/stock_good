export default function Page() {
  return (
    <section className="card">
      <span className="badge">Day 5 experiment recorder ready</span>
      <h1>实验记录</h1>
      <p>
        Day 5 已建立 file-based MLflow/Qlib compatible recorder：记录 run_id、experiment_id、resolved_config.yaml、
        config_hash、data/factor/label/model version、feature_count、split_count 和 artifact_manifest。
      </p>
      <div className="grid">
        <div className="card">
          <strong>Recorder</strong>
          <p>reports/day5/experiment_recorder/day5_lightgbm_walk_forward_v001 保存配置、指标、模型元数据和 artifact 清单。</p>
        </div>
        <div className="card">
          <strong>Qlib 状态</strong>
          <p>如本地 qlib 未安装，记录 qlib_blocked_reason.md；不伪造 workflow 成功。</p>
        </div>
        <div className="card">
          <strong>版本追踪</strong>
          <p>data_version=day3_v001，factor_version=factor_v004，label_version=label_v005，model_version=lightgbm_day5_v001。</p>
        </div>
        <div className="card">
          <strong>API</strong>
          <p>/api/experiments 返回 resolved_config、artifact_manifest、config_hash 与 qlib_status。</p>
        </div>
      </div>
    </section>
  );
}
