import { ArtifactStatusCard } from '../../components/ArtifactStatusCard';
import { getConsolePage } from '../../lib/researchConsoleData';

const page = getConsolePage('ops');

const mvpDag = [
  'ingest_daily_market', 'validate_market_daily', 'spark_bronze_to_silver', 'spark_materialize_factor_daily',
  'build_labels', 'leakage_check', 'point_in_time_join', 'build_training_matrix', 'train_lightgbm',
  'run_backtest', 'generate_risk_report', 'build_rag_index', 'publish_to_research_console'
];

const ciGates = ['pytest', 'schema_validation', 'leakage_tests', 'spark_job_smoke', 'flink_job_smoke', 'frontend_build', 'api_smoke', 'docker_build'];

export default function OpsPage() {
  return (
    <section className="page-grid">
      <ArtifactStatusCard config={page} />
      <div className="hero-card">
        <p className="eyebrow">ops_deployment · Ops readiness</p>
        <h1>配置、编排、回填、监控、部署与备份恢复</h1>
        <p>统一落地 ops_deployment 运维闭环：prefect-local 单一编排器、resolved_config.yaml、config_hash、backfill dry-run、dataset_snapshot_manifest、CI/CD gates、Spark/Flink/Kafka/ClickHouse/PostgreSQL/Redis 可观测性和 backup/restore smoke。</p>
      </div>
      <div className="card-grid">
        <div className="card"><strong>配置与 config_hash</strong><p>base/env/universe/data/factor/label/model/backtest/streaming/spark 配置统一解析，生成 resolved_config.yaml 与 sha256 config_hash。</p></div>
        <div className="card"><strong>prefect-local DAG</strong><p>MVP DAG 覆盖 ingest → validate → Spark → factor → label → leakage → train → backtest → RAG → publish。</p></div>
        <div className="card"><strong>backfill dry-run</strong><p>backfill_request 明确 partition、source_correction_id、affected_downstream、new_snapshot_id，不覆盖正式报告引用 snapshot。</p></div>
        <div className="card"><strong>dataset_snapshot_manifest</strong><p>支持按 data_version、run_id、trade_date、kafka_offset、model_version、rag_index_version 恢复。</p></div>
        <div className="card"><strong>Observability</strong><p>Spark/Flink/Kafka/ClickHouse/PostgreSQL/Redis 组件健康、data/task/model/system metrics 全部纳入接口。</p></div>
        <div className="card"><strong>backup/restore</strong><p>deploy/backup/backup_ops_deployment.sh --smoke 与 restore_ops_deployment.sh --smoke 生成 deterministic manifest。</p></div>
      </div>
      <div className="card"><strong>One-click dry-run</strong><p>命令：python scripts/run_ops_deployment_pipeline.py --dry-run；API：/api/ops、/api/orchestration、/api/backfill、/api/observability、/api/deployment。</p></div>
      <div className="card"><strong>MVP DAG</strong><p>{mvpDag.join(' → ')}</p></div>
      <div className="card"><strong>CI/CD gates</strong><p>{ciGates.join(' / ')}</p></div>
      <div className="card"><strong>Research boundary</strong><p>research_signals_only_not_investment_advice；本页是工程运维状态，不展示任何确定性交易建议。</p></div>
    </section>
  );
}
