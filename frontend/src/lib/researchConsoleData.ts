export type ConsolePageConfig = {
  route: string;
  title: string;
  eyebrow: string;
  apiPath: string;
  artifact: string;
  dataMode: string;
  status: string;
  description: string;
  fields: string[];
};

export const consolePages: Record<string, ConsolePageConfig> = {
  dashboard: {
    route: '/dashboard',
    title: 'Dashboard 研究总览',
    eyebrow: 'artifact-backed · research_site',
    apiPath: '/api/dashboard',
    artifact: 'reports/research_loop/live_predictions_report.json',
    dataMode: 'artifact-backed research run',
    status: 'latest_run_quality_ready',
    description: '股票池、数据截止时间、最新 run、质量状态、Spark 状态和风险提示集中展示。',
    fields: ['run_id', 'data_cutoff_time', 'quality_status', 'spark_status']
  },
  scores: {
    route: '/scores',
    title: 'Scores COGRASP 当前重训评分',
    eyebrow: 'artifact-backed · IJCAI 2025 architecture · current CSI300 retraining',
    apiPath: '/api/scores',
    artifact: 'reports/research_loop/live_predictions.parquet',
    dataMode: 'current-universe retrained 1d regression score',
    status: 'cograsp_current_rank_ready',
    description: '保留 COGRASP 作者网络结构，使用当前沪深300日频数据与收益相关性图重训并展示最新 1d 回归值；不做概率校准。',
    fields: ['symbol', 'prediction_target_date', 'predicted_relative_change_pct', 'score', 'rank', 'percentile', 'horizon', 'candidate_pool', 'candidate_summary', '1d']
  },
  candidates: {
    route: '/candidates',
    title: 'Candidates 研究候选池',
    eyebrow: 'artifact-backed · TopK pool',
    apiPath: '/api/backtests',
    artifact: 'reports/research_loop/holdings.parquet',
    dataMode: 'artifact-backed topk holdings',
    status: 'topk_candidate_pool_ready',
    description: '候选池功能已合并到 /scores：按当前沪深300重训版 COGRASP 1d 原始回归值生成 Top20 研究候选。',
    fields: ['candidate_pool', 'candidate_summary', 'predicted_relative_change_pct', 'rank', 'score']
  },
  experiments: {
    route: '/experiments',
    title: 'Experiments 实验记录',
    eyebrow: 'artifact-backed · recorder',
    apiPath: '/api/experiments',
    artifact: 'reports/research_loop/experiment_recorder',
    dataMode: 'artifact-backed experiment recorder',
    status: 'experiment_recorder_ready',
    description: 'run_id、resolved_config、config_hash、数据/因子/标签/模型版本和 artifact。',
    fields: ['run_id', 'resolved_config', 'config_hash', 'data_version', 'factor_version', 'artifact']
  },
  rag: {
    route: '/rag',
    title: 'RAG 投研证据',
    eyebrow: 'artifact-backed · claim evidence',
    apiPath: '/api/rag',
    artifact: 'rag/schemas/rag_claim.schema.yaml',
    dataMode: 'artifact-backed claim cards',
    status: 'claim_evidence_rag_ready',
    description: '引用、claim、证据方向、as_of 检索和证据不足拒答边界。',
    fields: ['claim_id', 'citation_span', 'evidence_direction', 'available_time', 'as_of_mode', 'license_gate']
  },
  'data-quality': {
    route: '/data-quality',
    title: 'Data Quality 数据质量',
    eyebrow: 'artifact-backed · quality gate',
    apiPath: '/api/data-quality',
    artifact: 'reports/data_trust/data_quality_report.json',
    dataMode: 'artifact-backed quality report',
    status: 'quality_quarantine_ready',
    description: '质量报告、quarantine、血缘、许可证和 snapshot。',
    fields: ['missingness', 'outliers', 'quarantine_count', 'license_status', 'snapshot_id']
  },
  lineage: {
    route: '/lineage',
    title: 'Lineage 数据血缘',
    eyebrow: 'artifact-backed · lineage',
    apiPath: '/api/lineage',
    artifact: 'reports/data_trust/lineage_report.json',
    dataMode: 'artifact-backed lineage report',
    status: 'source_job_snapshot_lineage_ready',
    description: 'ODS/DWD/DWS/ADS、Spark job 到结果快照的可追溯链路。',
    fields: ['source_id', 'job_id', 'snapshot_id', 'upstream_snapshot_ids', 'downstream_artifacts']
  },
  lakehouse: {
    route: '/lakehouse',
    title: 'Lakehouse 湖仓状态',
    eyebrow: 'artifact-backed · ODS/DWD/DWS/ADS',
    apiPath: '/api/lakehouse',
    artifact: 'metadata/dataset_snapshot_manifest.json',
    dataMode: 'artifact-backed snapshot manifest',
    status: 'lakehouse_snapshot_ready',
    description: 'ODS/DWD/DWS/ADS 表、Iceberg/Hudi/Delta PoC 状态和 dataset_snapshot_manifest。',
    fields: ['dataset_layer', 'table_name', 'snapshot_id', 'row_count', 'table_format_status']
  },
  'spark-jobs': {
    route: '/spark-jobs',
    title: 'Spark Jobs 离线作业',
    eyebrow: 'artifact-backed · Spark local',
    apiPath: '/api/spark-jobs',
    artifact: 'reports/factor_store/spark_job_runs.json',
    dataMode: 'artifact-backed spark job runs',
    status: 'spark_materialization_ready',
    description: 'spark_job_run、作业耗时、输入输出行数、失败日志和输出 snapshot。',
    fields: ['spark_job_run', 'duration_sec', 'input_rows', 'output_rows', 'error_log', 'snapshot_id']
  },
  graph: {
    route: '/graph',
    title: 'Graph 股票关系图',
    eyebrow: 'artifact-backed · relation_graph',
    apiPath: '/api/graph',
    artifact: 'reports/relation_graph/relation_graph_report.json',
    dataMode: 'artifact-backed relation_graph',
    status: 'relation_graph_ready',
    description: '股票关系图、传播因子、as_of_date 和边权重。',
    fields: ['source_symbol', 'target_symbol', 'relation_type', 'edge_weight', 'as_of_date']
  },
  simulation: {
    route: '/simulation',
    title: 'Simulation 模拟盘与组合风控',
    eyebrow: 'artifact-backed · governance_simulation paper trading',
    apiPath: '/api/simulation',
    artifact: 'reports/governance_simulation/governance_simulation_simulation_governance_report.json',
    dataMode: 'artifact-backed paper_trading_research_simulation_only',
    status: 'paper_simulation_governance_ready',
    description: 'simulation_account、simulation_order、simulation_position、simulation_nav、simulation_risk 与组合风控 gate；仅用于 research simulation。',
    fields: ['simulation_account', 'simulation_order', 'simulation_position', 'simulation_nav', 'simulation_risk', 'risk_limit']
  },
  reports: {
    route: '/reports',
    title: 'Reports 报告导出与状态机',
    eyebrow: 'artifact-backed · governance_simulation export gate',
    apiPath: '/api/reports',
    artifact: 'reports/governance_simulation/export_manifest.json',
    dataMode: 'artifact-backed report_state_machine',
    status: 'report_export_manifest_ready',
    description: '报告状态机、导出审批、license_gate、forbidden_wording 和 export_manifest。',
    fields: ['report_status', 'approval_status', 'license_gate', 'forbidden_wording', 'export_manifest', 'file_hash']
  },
  'settings/licenses': {
    route: '/settings/licenses',
    title: 'Settings · Licenses 许可证',
    eyebrow: 'artifact-backed · governance_simulation license policy',
    apiPath: '/api/licenses',
    artifact: 'reports/governance_simulation/license_gate_report.json',
    dataMode: 'artifact-backed license policy engine',
    status: 'license_policy_gate_ready',
    description: '许可证策略、可展示范围、snippet 限制、license_gate 和导出边界。',
    fields: ['source_id', 'permitted_use', 'redisplay_allowed', 'snippet_allowed', 'export_allowed', 'external_share_allowed', 'compliance_status']
  },
  'settings/users': {
    route: '/settings/users',
    title: 'Settings · Users 用户角色',
    eyebrow: 'artifact-backed · governance_simulation RBAC',
    apiPath: '/api/admin',
    artifact: '/api/admin rbac_roles payload',
    dataMode: 'artifact-backed RBAC duties separation',
    status: 'rbac_duties_ready',
    description: '用户、角色、权限、职责分离和 action-level permission 的页面入口。',
    fields: ['user_id', 'role', 'permission', 'data_scope', 'duties_separation', 'audit_required']
  },
  'settings/audit': {
    route: '/settings/audit',
    title: 'Settings · Audit 审计',
    eyebrow: 'artifact-backed · governance_simulation governance log',
    apiPath: '/api/audit',
    artifact: 'reports/governance_simulation/audit_log.json',
    dataMode: 'artifact-backed append_only audit log',
    status: 'append_only_audit_ready',
    description: '审计日志和治理事件查询；记录数据、因子、模型、RAG、报告、simulation 动作。',
    fields: ['audit_id', 'actor', 'action', 'resource', 'created_at', 'trace_id', 'append_only']
  },
  ops: {
    route: '/ops',
    title: 'Ops 运维部署与编排',
    eyebrow: 'artifact-backed · ops_deployment ops readiness',
    apiPath: '/api/ops',
    artifact: 'reports/ops_deployment/ops_deployment_ops_acceptance_report.json',
    dataMode: 'artifact-backed orchestration_observability_backup_restore',
    status: 'ops_deployment_ops_deployment_ready',
    description: '配置解析、config_hash、prefect-local DAG、backfill dry-run、dataset_snapshot_manifest、CI/CD、可观测性和 backup/restore smoke。',
    fields: ['config_hash', 'orchestrator', 'backfill_request', 'dataset_snapshot_manifest', 'component_health', 'backup_assets']
  }
};

export function getConsolePage(route: string): ConsolePageConfig {
  return consolePages[route];
}
