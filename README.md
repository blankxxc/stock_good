# stock_good — 智能选股研究平台

stock_good 是一个面向量化研究与智能选股的本地全栈工程样例。项目以“可追溯数据、可复现实验、可验证因子、可回测模型、可解释研究证据、可视化研究工作台”为核心目标，当前已完成 Day 1 至 Day 14 的本地闭环实现。

仓库地址：https://github.com/blankxxc/stock_good

## 项目定位

本项目不是自动荐股或实盘交易系统，而是研究型智能选股平台。系统输出的是：

- 横截面股票评分、排序和候选池；
- 离线因子、特征矩阵、标签和模型诊断；
- walk-forward 回测、风险归因、容量和交易成本分析；
- RAG/知识证据、研究假设和实验记录；
- 面向投研人员的 Web research console。

所有信号都必须经过样本外验证、模拟交易、风险约束和人工复核后，才可以作为进一步研究依据。项目不接券商实盘、不自动下单、不输出“必买/稳赚/目标价”等确定性投资建议。

## 当前完成度

| 阶段 | 主题 | 当前状态 |
| --- | --- | --- |
| Day 1 | 全栈工程骨架、数据契约、元数据治理、Spark/Flink/Kafka/Compose 基础 | 已完成 |
| Day 2 | 本地湖仓、批量接入、ODS/DWD/DWS/ADS、许可证治理、Iceberg PoC、ClickHouse ADS | 已完成 |
| Day 3 | 数据质量、quarantine、防泄漏、point-in-time、血缘、数据可信度页面/API | 已完成 |
| Day 4 | 74 个离线因子、Feature Store、点时间特征 join、Spark/Polars 一致性、因子页面/API | 已完成 |
| Day 5 | 5d/10d 标签、LightGBM baseline、walk-forward、回测/风险/容量、实验记录器、Qlib-compatible recorder | 已完成 |
| Day 6 | Redpanda/Kafka topic、replay simulated producer、Flink-style 实时因子、online feature snapshot、实时页面/API | 已完成 L1 PoC |
| Day 7 | 新闻/公告事件、FinBERT-compatible 情绪 baseline、事件因子、market regime、增强特征矩阵、ablation | 已完成 |
| Day 8 | 股票关系图、Spark-style 价格相关边、NetworkX centrality/community、关系传播因子、HIST/TRSR adapter、图谱页面/API | 已完成 L1/L2 PoC |
| Day 9 | MASTER、StockMixer、HIST、TRSR 高级模型 adapter、小样本训练/推理、统一对比报告、模型页面/API | 已完成 L1 research candidate |
| Day 10 | claim 级 RAG 证据系统、as_of/present/retrospective 检索、引用卡片、许可证门禁、RAG 页面/API | 已完成 L1/L2 claim evidence RAG |
| Day 11 | 官网层、Research Console 全页面产品化、统一视觉系统、artifact-backed 主卡片、Spark/Lakehouse/Realtime 状态展示 | 已完成 Day11 site productized |
| Day 12 | paper trading research simulation、组合风控、RBAC/职责分离、append-only 审计、license policy、报告状态机和 export manifest | 已完成 Day12 simulation governance |
| Day 13 | 自动化部署与运维闭环、配置解析/config_hash、prefect-local DAG、backfill dry-run、snapshot manifest、可观测性、CI/CD、备份恢复 | 已完成 Day13 ops deployment readiness |
| Day 14 | 全量联调、最终验收、覆盖矩阵、演示资产、ADR、risk register、最终文档和 release gates | 已完成 Day14 final acceptance |

最近本地验收结果：

- Day4 acceptance: `status=ok`, `checks=15`, `failed=[]`, `factor_count=74`, `factor_rows=129796`, `feature_matrix_rows=1960`, `spark_consistency_status=passed`, `point_in_time_violations=0`。
- Day5 acceptance: `status=ok`, `checks=19`, `failed=[]`, `label_rows=3620`, `prediction_rows=413`, `holding_rows=105`, `split_count=3`, `feature_count=72`, `lightgbm_status=trained`, `qlib_status=minimal_qlib_recorder_available`, `leakage_check_status=passed`。
- Day6 acceptance: `status=ok`, `checks=24`, `failed=[]`, `feed_mode=replay_simulated_not_live_market_data`, `raw_events_written=137`, `flink_jobs_ready=5`, `realtime_factor_rows=162`, `online_feature_rows=36`, `diff_report.max_abs_diff=0.0`。
- Day7 acceptance: `status=ok`, `checks=18`, `failed=[]`, `text_model_status=lexicon_finbert_compatible_baseline_ready`, `event_factor_rows=29400`, `market_regime_rows=100`, `enhanced_feature_rows=1960`, `ablation_status=lightgbm_smoke_trained`。
- Day8 acceptance: `status=ok`, `checks=17`, `failed=[]`, `edge_rows=990`, `relation_type_count=8`, `relation_factor_rows=1960`, `enhanced_feature_rows=1960`, `networkx_status=networkx_centrality_ready`, `hist_trsr_adapter_status=hist_trsr_relation_inputs_ready`。
- Day9 acceptance: `status=ok`, `checks=16`, `failed=[]`, `model_count=4`, `prediction_rows=1620`, `approval_status=research_candidate_only_not_approved`, `leakage_check_status=passed`。
- Day10 acceptance: `status=ok`, `checks=18`, `failed=[]`, `document_count=11`, `claim_count=11`, `eval_status=ok`, `time_leakage_rate=0.0`, `license_gate_status=passed`。
- Day11 acceptance: `status=ok`, `checks=16`, `failed=[]`, `public_route_count=7`, `console_route_count=20`, `artifact_backed_pages=20`, `visual_system=professional_research_saas_light`。
- Day12 acceptance: `status=ok`, `checks=25`, `failed=[]`, `simulation_order_count=8`, `simulation_position_count=8`, `risk_status=passed`, `role_count=6`, `license_source_count=3`, `export_manifest_status=generated`, `append_only_audit=true`。
- Day13 acceptance: `status=ok`, `checks=28`, `failed=[]`, `orchestrator=prefect-local`, `mvp_task_count=15`, `extended_task_count=9`, `backfill_status=dry_run_passed`, `component_count=6`, `ci_gate_count=16`, `backup_asset_count=10`。
- Day14 acceptance: `status=ok`, `checks>=34`, `failed=[]`, `final_status=day14_final_acceptance_ready`, `completed_days=14`, `coverage_area_count=30`, `release_gate_status=passed`。
- 完整测试：`61 passed, 24 warnings`。
- 前端路由：`route_count=29`。
- Next.js production build：31 个静态页面生成成功。


最新 Day14 本地验收快照（2026-06-09 22:01 +0800）：

- Day14：`scripts/check_day14_acceptance.py` 返回 `status=ok`、`checks>=34`、`failed=[]`、`final_status=day14_final_acceptance_ready`、`completed_days=14`、`coverage_area_count=30`、`document_count=16`、`demo_asset_count=13`、`release_gate_status=passed`。
- Day14 focused tests：`tests/test_day14_final_acceptance.py` 共 `3 passed`。
- 完整测试：`61 passed, 24 warnings`；warnings 为 Day5 pandas FutureWarning，不影响 Day14。
- API smoke：`/health`、`/api/final-acceptance`、`/api/ops`、`/api/reports`、`/api/rag`、`/api/site` 均返回 200；其中 `/health.version=0.1.0-day14`，`/api/final-acceptance=day14_final_acceptance_ready`。
- 前端：`npm run validate:routes` 返回 `status=ok`、`route_count=29`；`npm run build` 编译成功并生成 31 个静态页面。
- 运维 smoke：`docker compose -f deploy/docker/docker-compose.yml config --services` 成功；backup/restore smoke 成功。
- 最终文档：`docs/final_acceptance_report.md`、`docs/demo/coverage_matrix.md`、`docs/demo_script.md`、`docs/architecture.md`、`docs/security_compliance.md` 和 `docs/adr/ADR-005-final-release-gates.md` 已补齐。

最新 Day13 本地验收快照（2026-06-09 21:44 +0800）：

- Day13：`scripts/check_day13_acceptance.py` 返回 `status=ok`、`checks=28`、`failed=[]`、`orchestrator=prefect-local`、`mvp_task_count=15`、`extended_task_count=9`、`config_hash=051752bbf18971476b7cecab6eb18f5703c2c90c137937394876dc4fa8f6724d`、`backfill_status=dry_run_passed`、`component_count=6`、`ci_gate_count=16`、`backup_asset_count=10`。
- Day13 focused tests：`tests/test_day13_ops_deployment.py` 共 `3 passed`。
- 完整测试：`58 passed, 24 warnings`；warnings 为 Day5 pandas FutureWarning，不影响 Day13。
- API smoke：`/health`、`/api/ops`、`/api/orchestration`、`/api/backfill`、`/api/observability`、`/api/deployment`、`/api/simulation`、`/api/reports`、`/api/site`、`/api/rag` 均返回 200；其中 `/health.version=0.1.0-day13`，`/api/ops=day13_ops_deployment_ready`。
- 前端：`npm run validate:routes` 返回 `status=ok`、`route_count=29`；`npm run build` 编译成功并生成 31 个静态页面，新增 `/ops`。
- 运维 smoke：`docker compose -f deploy/docker/docker-compose.yml config --services` 成功；`sh deploy/backup/backup_day13.sh --smoke` 与 `sh deploy/backup/restore_day13.sh --smoke` 成功。

最新 Day12 本地验收快照（2026-06-09 18:32 +0800）：

- Day12：`scripts/check_day12_acceptance.py` 返回 `status=ok`、`checks=25`、`failed=[]`、`simulation_order_count=8`、`simulation_position_count=8`、`risk_status=passed`、`role_count=6`、`license_source_count=3`、`export_manifest_status=generated`、`forbidden_wording_gate=passed`、`append_only_audit=true`。
- Day12 focused tests：`tests/test_day12_simulation_governance.py` 共 `3 passed`；兼容性回归覆盖 Day2 licenses API/page。
- 完整测试：`55 passed, 24 warnings`；warnings 为 Day5 pandas FutureWarning，不影响 Day12。
- API smoke：`/health`、`/api/simulation`、`/api/reports`、`/api/licenses`、`/api/admin`、`/api/audit`、`/api/site`、`/api/rag`、`/api/dashboard` 均返回 200；其中 `/health.version=0.1.0-day12`，`/api/simulation=day12_paper_simulation_ready`，`/api/reports=day12_report_export_ready`，`/api/licenses` 保持 Day2 `status=day2_license_registry_ready` 并新增 `day12_policy_status=day12_license_policy_ready`。
- 前端：`npm run validate:routes` 返回 `status=ok`、`route_count=28`；`npm run build` 编译成功并生成 30 个静态页面。

最新 Day10/Day11 复验与 GitHub 上传快照（2026-06-09 18:02 +0800）：

- Day10 提交：`e823e7e feat: implement day10 rag evidence system`。
- Day11 提交：`831f9bd feat: productize day11 research site`。
- Day10：`scripts/check_day10_acceptance.py` 返回 `status=ok`、`checks=18`、`failed=[]`、`document_count=11`、`claim_count=11`、`eval_status=ok`、`time_leakage_rate=0.0`、`license_gate_status=passed`。
- Day10 focused tests：`tests/test_day10_rag_evidence.py` 共 `3 passed`；Day10+Day11 focused tests 合计 `6 passed`。
- Day11：`scripts/check_day11_acceptance.py` 返回 `status=ok`、`checks=16`、`failed=[]`、`public_route_count=7`、`console_route_count=20`、`artifact_backed_pages=20`、`visual_system=professional_research_saas_light`。
- 完整测试：`52 passed, 24 warnings`；warnings 为 Day5 pandas FutureWarning，不影响 Day10/Day11。
- API smoke：`/health`、`/api/rag`、`/api/site`、`/api/dashboard`、`/api/lakehouse`、`/api/spark-jobs`、`/api/realtime`、`/api/flink-jobs`、`/api/models`、`/api/experiments` 均返回 200；其中 `/api/rag` 为 `day10_rag_evidence_ready`，`/api/site` 为 `day11_site_productized_ready`。
- 前端：`npm run validate:routes` 返回 `status=ok`、`route_count=28`；`npm run build` 编译成功并生成 30 个静态页面。
- GitHub 同步：本节随 README docs 提交一起推送到 `origin/main`，以远端 `main` HEAD 为准。

## 技术栈

后端与研究计算：

- Python 3.11
- FastAPI / Uvicorn
- Pandas / PyArrow / DuckDB
- Polars
- NetworkX
- PySpark 3.5.3
- SQLAlchemy / Alembic
- pytest
- pyqlib 0.9.7

前端：

- Next.js App Router
- React
- TypeScript

数据与基础设施：

- Parquet 本地湖仓
- Iceberg Hadoop catalog PoC
- ClickHouse ADS
- PostgreSQL / Redis / Qdrant
- Redpanda/Kafka topic manifest
- Flink job graph manifest
- Spark local jobs
- Docker Compose
- Prometheus / Grafana

## 目录结构

```text
backend/                         FastAPI 后端、API 路由、Alembic migration
configs/                         数据源、因子、模型等配置
contracts/                       项目契约与治理约束
docs/                            Day14 架构、最终验收、演示脚本、风险 register 和 ADR
data/                            Bronze/Silver/Gold/ADS/样例数据/隔离数据
feature_store/                   Feature registry 与 point-in-time join
factors/                         离线因子计算引擎
frontend/                        Next.js 官网层 + research console
graph/                           Day8 股票关系图、关系传播因子和图模型 adapter
lakehouse/                       DuckDB 查询、Iceberg/Delta PoC 相关入口
models/                          Day5 研究闭环、Day7 事件/市场环境因子与 ablation、Day9 高级模型 adapter
quality/                         Day3 数据质量、防泄漏、血缘与可信度逻辑
rag/                             Day10 claim 级 RAG schema、eval sets、证据检索与回答约束
simulation/                      Day12 paper trading simulation、风控、RBAC/license/report governance
ops/                             Day13/Day14 配置解析、DAG、运维 helper 和最终验收 payload
reports/                         验收报告、质量报告、回测报告、实验 artifacts
scripts/                         一键验收、pipeline、ClickHouse 装载等脚本
spark/                           Spark 本地批处理与因子物化任务
streaming/                       Kafka topic、replay producer 与 Flink-style 实时因子 PoC
warehouse_schema/                元数据仓库 SQL migration
```

## 核心功能

### 1. 数据契约与治理

- `data_contracts/*.schema.yaml` 覆盖行情、财务、公告、新闻、宏观、资金流、因子、标签、信号、回测、RAG claim 等数据契约。
- 元数据 migration 覆盖 dataset snapshot、schema registry、Spark/Flink job run、RAG claim、export manifest、backfill request、ADR、risk register 等。
- 数据源许可证 registry 明确 `authorized`、`restricted`、`not_authorized`、`adapter_pending` 等状态，并限制展示/导出边界。

### 2. 本地湖仓与批量接入

- Day2 pipeline 生成可复现 synthetic market 数据。
- Bronze/ODS：raw market、minute、tick、trade、orderbook、financial、announcement、news、macro、fund flow、northbound。
- Silver/DWD：清洗后的日频行情、分钟行情、财务、新闻事件、公告事件。
- Gold/DWS：因子面板、标签、训练样本、横截面信号、回测结果。
- ADS：dashboard summary、latest score、backtest summary、data quality summary。
- Iceberg PoC 已验证写入、读回、schema evolution、metadata files 与 snapshots。

### 3. 数据可信度、防泄漏与血缘

- synthetic mini market 覆盖停牌、ST、涨跌停、退市、新上市、公告晚于收盘、未来成分股、未来复权因子、全样本归一化泄漏、label 泄漏诱捕等场景。
- 数据质量报告覆盖 schema、主键重复、缺失、OHLC、成交量、交易日缺口、复权因子、行业、指数成分历史、延迟、重复率、修正率和 source license gate。
- 防泄漏检查验证 `feature.available_time <= prediction_time`、`label_start_time > prediction_time`、公告/新闻/财报发布时间、行业/指数 as-of、scaler fit window、purged split/embargo。
- 血缘报告连接 `source_table -> transform_job -> target_table -> snapshot/report`。

### 4. 因子库与 Feature Store

- 当前实现 74 个离线因子，覆盖价格收益、动量、反转、波动率、流动性、成交量、风险暴露等类别。
- 因子长表：`data/gold/factor_daily_panel_long`。
- 模型宽表：`data/gold/model_feature_matrix_wide`。
- 风险暴露：`data/gold/risk_factor_exposure`。
- 支持点时间 join，并验收 `point_in_time_violations=0`。
- Spark 与 Polars 因子物化结果已做一致性校验，`spark_consistency_status=passed`。

### 5. Day5 研究闭环

- 生成 5d/10d 横截面收益标签。
- 标签包含 prediction time、label start/end、交易可行性、停牌/ST/涨跌停/退市等约束。
- LightGBM baseline 已训练完成。
- walk-forward split 数量为 3。
- 记录 IC、RankIC、ICIR、TopK return、quantile spread、long-short spread、turnover、cost-adjusted return、max drawdown、Sharpe、Calmar、hit rate、capacity 等指标。
- 输出预测、持仓、净值曲线、风险报告、回测 HTML 和 experiment recorder artifact。
- Qlib Python 包已安装，当前 recorder 状态为 `minimal_qlib_recorder_available`。注意：这表示 Qlib 包和最小 recorder 可用，不代表已下载官方 Qlib 股票数据集。

### 6. Day6 实时流 PoC

- `streaming/kafka/topics.yaml` 覆盖 raw、clean、factor、feature、signal、alert 等 Kafka/Redpanda topic。
- 本地 replay producer 生成契约合法 JSONL topic logs，feed mode 明确为 `replay_simulated_not_live_market_data`。
- Flink-style deterministic pipeline 生成实时价格量价、微观结构、新闻情绪、市场环境、relation placeholder 等因子。
- 输出 `realtime_factor_latest.parquet`、`factor_intraday_panel`、`online_feature_snapshot.json`、`flink_job_status.json`、`topic_health.json` 和 realtime-vs-offline diff report。
- `/api/realtime`、`/api/flink-jobs` 与 `/realtime`、`/flink-jobs` 页面展示 PoC 状态和 not formal signal 边界。

### 7. Day7 事件/市场环境因子

- 生成 news/announcement document、event extraction、entity-symbol mapping、DWD event 表。
- 使用诚实标注的 `lexicon_finbert_compatible_baseline` 作为本地金融文本情绪 baseline；未伪装成真实远程 FinBERT/FinGPT 推理。
- 事件因子覆盖 1d/3d/5d 情绪、公告情绪、事件数、负面事件、source weighted sentiment、novelty、authority、decay、policy/macro event score。
- 市场环境因子覆盖 breadth、return、volatility、drawdown、limit up/down、成交额分位、风格轮动、industry dispersion、northbound flow、liquidity regime、risk appetite。
- 严格区分 `ex_ante_regime_feature` 与 `ex_post_regime_label`，并保留 publish/available/prediction time 以避免新闻公告时间泄漏。
- 输出 Day7 增强特征矩阵和 `event_regime_ablation_report`，当前 ablation 状态为 `lightgbm_smoke_trained`。

### 8. Day8 股票关系图与关系传播因子

- 生成 `stock_relation_edge`，覆盖 industry_same、concept_same、index_member_same、price_corr、lead_lag、news_co_mention、supply_chain_upstream/downstream 等关系类型。
- `spark/jobs/build_day8_price_corr_edges.py` 生成 Spark-compatible 价格相关边；本地 PoC 不依赖真实集群，但保留可迁移边界。
- NetworkX 计算 degree centrality、PageRank 和 community，并输出 `reports/day8/graph_summary.json`。
- `factor_relation_panel` 输出 neighbor_return_5m/1d、neighbor_volume_shock、neighbor_sentiment_1h、industry/concept/supply-chain spillover、lead_lag_signal、centrality_score、community_momentum、correlation_cluster_momentum 等关系因子。
- `model_feature_matrix_wide_day8` 在 Day7 增强特征矩阵之上加入关系传播因子，并继续保留 point-in-time 时间语义和 `research_boundary`。
- `data/gold/graph_model_adapters/hist_trsr` 已生成 stock_id_mapping、relation_type_mapping、relation_matrix、concept_matrix、stock_feature_tensor、label_tensor，作为 HIST/TRSR 关系图模型输入 adapter。
- `relation_factor_ablation_report` 覆盖 base_day7、base_plus_relation_graph、full_minus_relation_graph；结果仍标记为 `not_approved_research_candidate_only`，不能视为实盘信号。

### 9. Day9 高级模型 adapter 与统一对比

- `models/day9_advanced_models.py` 实现统一模型接口：`fit`、`predict`、`evaluate`、`register_model_artifact`、`explain_feature_dependency`。
- `models/master`、`models/stockmixer`、`models/hist`、`models/trsr` 均包含 `adapter.py`、`run_small_sample.py`、`README.md`、`environment.lock` 和官方生产集成 blocked note。
- MASTER 使用 market information token；StockMixer 使用 indicator/temporal/stock mixing token；HIST 使用 concept/industry shared-information proxy；TRSR 使用 relation_matrix/lead-lag 排序 proxy。
- 输出 `data/gold/advanced_model_predictions`、`data/gold/advanced_model_comparison/model_comparison.csv`、`reports/day9/model_comparison_report.json` 和 `reports/day9/experiment_recorder/*`。
- 对比报告覆盖 LightGBM vs MASTER vs StockMixer vs HIST vs TRSR 的 IC、RankIC、TopK、Drawdown、Turnover、Runtime、ParameterCount、TrainingCostTier、WorstSeedRankIC 和 BlockedReason。
- 四个高级模型均为 `candidate / not_approved_research_candidate_only`，不能进入正式评分或交易决策。

### 10. Day10 claim 级 RAG 证据系统

- `rag/day10_evidence_system.py` 构建 document -> chunk -> claim 的本地证据链，支持 paper、factor_card、strategy_card、experiment_card、backtest_report、failure_case、market_review、announcement、news、research_note、relation_case 等 11 类资料。
- `rag/schemas/rag_claim.schema.yaml` 明确 `claim_id`、`citation_span`、`license_id`、`event_time`、`publish_time`、`ingest_time`、`available_time`、`valid_from`、`valid_to`、`evidence_direction`、`evidence_strength`、`content_hash`、`embedding_model` 和 `index_version`。
- 输出 `data/gold/rag_documents`、`data/gold/rag_chunks`、`data/gold/rag_claims`，并生成 `reports/day10/rag_evidence_report.json`、`rag_eval_report.json`、`rag_answer_cards.json`、`rag_citation_cards.html`。
- 检索支持 `as_of`、`present`、`retrospective_review`：`as_of` 强制 `available_time <= prediction_time`、`publish_time <= prediction_time`、`status=approved` 和 license gate。
- 回答约束为事实、推断、假设、支持证据、反对证据、适用条件；无引用拒答，不输出买入/卖出/持有/目标价/稳赚/确定上涨等交易指令。
- RAG 评测覆盖 expected citations、time leakage、license gate、forbidden wording、abstention accuracy、citation support rate 和 Recall@5。


### 11. Day11 网站全页面产品化

- 新增官网层 7 个页面：能力介绍、方法论、数据与安全、回测与风控、RAG 证据、架构路线图、登录入口。
- Research Console 20 个业务页面统一使用 `ArtifactStatusCard` 和 `researchConsoleData.ts`，主卡片绑定 `/api/*` 与本地 artifact / contract，并显式展示 `data_mode`。
- `/api/site` 汇总 public route、console route、artifact-backed 页面数、禁用文案检查、Spark/Lakehouse/Realtime 状态入口和视觉系统状态。
- `layout.tsx` 增加官网导航、Research Console 侧栏和固定研究边界提示；`globals.css` 升级为专业、克制、浅色研究 SaaS 风格。
- `/spark-jobs`、`/lakehouse`、`/realtime`、`/flink-jobs` 均在导航、页面和 API smoke 中可见；页面不使用主流程纯静态假数据。

### 12. Day12 模拟盘、治理与报告导出

- `simulation/day12_governance.py` 生成 paper trading research simulation，不接券商实盘接口，所有订单显式 `simulated=true` 和 `broker_route=none_disabled`。
- 输出 `simulation_account`、`simulation_order`、`simulation_position`、`simulation_nav` 与 `simulation_risk`，覆盖单票权重、行业权重、turnover、ST/停牌/涨跌停、流动性、max_drawdown、style exposure、tracking error、TopK concentration 等风控 gate。
- 实现 RBAC 与职责分离：admin、researcher、reviewer、viewer、compliance、data_owner；viewer 不能看未发布候选池、不能导出完整数据、不能运行实验；报告提交者不能审批自己的报告。
- 实现 Day12 license policy：保留 Day2 `/api/licenses` 兼容字段，同时新增 `day12_policy_status`、`license_registry`、`license_gate_results`、snippet/export/share/redaction 规则。
- 实现报告状态机与导出门禁：draft → review → approved → exportable → exported → revoked；导出前检查 data_quality、leakage、license_gate、RAG citation 和 forbidden_wording。
- 生成 `export_manifest`，包含 run/data/factor/model/label/RAG source version、watermark、disclaimer、file_hash 和 audit_id；审计日志为 append-only。


### 13. Day13 自动化部署与运维闭环

- `ops/day13_ops.py` 统一生成 Day13 运维 payload，解析 base/env/universe/data/factor/label/model/backtest/streaming/spark 配置并生成 `resolved_config.yaml` 与 sha256 `config_hash`。
- 采用单一 `prefect-local` 编排语义，MVP DAG 覆盖 ingest、validate、Spark materialization、factor、label、leakage、train、backtest、risk report、RAG index 和 publish；扩展 DAG 覆盖 replay/Kafka/Flink/online feature/graph/advanced model/simulation/report export。
- `backfill_request` 支持 dry-run，记录 partition、source_correction_id、affected_downstream、new_snapshot_id，并禁止覆盖正式报告已引用 snapshot。
- `dataset_snapshot_manifest` 支持按 data_version、run_id、trade_date、kafka_offset、model_version、rag_index_version 恢复。
- 可观测性覆盖 data/task/model/system metrics，以及 Spark/Flink/Kafka/ClickHouse/PostgreSQL/Redis 组件健康。
- 新增 `.github/workflows/ci.yml`、`deploy/proxy/Caddyfile`、`deploy/k8s/day13-platform.yaml`、Prometheus/Grafana dashboard、backup/restore smoke 脚本和 `/ops` 页面。

## Web Research Console

前端位于 `frontend/`，当前包含 29 条路由：7 条官网层路由 + 21 条 Research Console/Ops 业务路由 + 首页，覆盖：

- `/dashboard`：研究总览与 Day5 dashboard summary
- `/scores`：横截面评分与候选池
- `/backtests`：回测与风险/容量结果
- `/experiments`：实验记录器与 artifact manifest
- `/factors`：Day4 因子库、Feature Store、Day7 事件/市场环境因子、Day8 关系图因子
- `/spark-jobs`：Spark 因子物化与一致性校验
- `/data-quality`：Day3 数据质量与防泄漏摘要
- `/lineage`：数据血缘
- `/lakehouse`：Day2 湖仓与 snapshot
- `/settings/licenses`：数据源许可证治理
- `/realtime`：Day6 replay simulated realtime factor PoC
- `/flink-jobs`：Day6 Flink-style job status
- `/graph`：Day8 股票关系图、关系传播因子、HIST/TRSR adapter 和 ablation 状态
- `/models`：Day9 MASTER、StockMixer、HIST、TRSR 小样本 adapter、模型对比和 candidate 准入状态
- `/rag`：Day10 claim 级 RAG 证据、as_of 检索、引用卡片、评测门禁和无引用拒答边界
- `/simulation`、`/reports` 等研究扩展页面
- `/ops`：Day13 配置、DAG、backfill dry-run、dataset snapshot、observability、CI/CD、deployment 和 backup/restore smoke
- 官网层：`/capabilities`、`/methodology`、`/data-security`、`/backtest-risk`、`/rag-evidence`、`/architecture-roadmap`、`/login`

## 快速开始

以下命令适用于 Windows Git Bash / MSYS 环境。

```bash
cd /c/Users/blankxxc/Desktop/work_space/stock_good

# Python 依赖
uv venv --python 3.11 .venv
uv pip install --python ./.venv/Scripts/python.exe -e .

# 前端依赖
cd frontend
npm install
cd ..
```

如果只使用当前本机已有环境，可直接使用项目内 `.venv/Scripts/python.exe` 运行脚本。

## 常用运行命令

### 后端

```bash
cd /c/Users/blankxxc/Desktop/work_space/stock_good
./.venv/Scripts/python.exe -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
```

健康检查：

```bash
curl http://127.0.0.1:8000/health
```

核心 API：

```text
/api/factors
/api/features
/api/spark-jobs
/api/dashboard
/api/scores
/api/backtests
/api/experiments
/api/data-quality
/api/lineage
/api/lakehouse
/api/licenses
/api/realtime
/api/flink-jobs
/api/event-regime
/api/graph
/api/models
/api/rag
/api/site
/api/simulation
/api/reports
/api/admin
/api/audit
/api/ops
/api/orchestration
/api/backfill
/api/observability
/api/deployment
```

### 前端

```bash
cd /c/Users/blankxxc/Desktop/work_space/stock_good/frontend
npm run validate:routes
npm run build
npm run dev
```

默认本地访问地址：

```text
http://127.0.0.1:3000/
```

### Docker Compose

```bash
cd /c/Users/blankxxc/Desktop/work_space/stock_good
docker compose -f deploy/docker/docker-compose.yml up -d --build
docker compose -f deploy/docker/docker-compose.yml ps
```

Compose 栈声明了 postgres、redis、qdrant、redpanda、flink、spark、clickhouse、backend、worker、frontend、prometheus、grafana、backup 等服务。Windows 本地运行时需要 Docker Desktop / WSL2 Linux engine 正常可用。

## 一键验收命令

```bash
cd /c/Users/blankxxc/Desktop/work_space/stock_good

./.venv/Scripts/python.exe scripts/check_day1_acceptance.py
./.venv/Scripts/python.exe scripts/check_day2_acceptance.py
./.venv/Scripts/python.exe scripts/check_day3_acceptance.py
./.venv/Scripts/python.exe scripts/check_day4_acceptance.py
./.venv/Scripts/python.exe scripts/check_day5_acceptance.py
./.venv/Scripts/python.exe scripts/check_day6_acceptance.py
./.venv/Scripts/python.exe scripts/check_day7_acceptance.py
./.venv/Scripts/python.exe scripts/check_day8_acceptance.py
./.venv/Scripts/python.exe scripts/check_day9_acceptance.py
./.venv/Scripts/python.exe scripts/check_day10_acceptance.py
./.venv/Scripts/python.exe scripts/check_day11_acceptance.py
./.venv/Scripts/python.exe scripts/check_day12_acceptance.py
./.venv/Scripts/python.exe scripts/check_day13_acceptance.py
```

完整测试：

```bash
./.venv/Scripts/python.exe -m pytest tests -q
```

前端验证：

```bash
cd frontend
npm run validate:routes
npm run build
```

## Day2 常用命令

```bash
cd /c/Users/blankxxc/Desktop/work_space/stock_good
./.venv/Scripts/python.exe scripts/run_day2_pipeline.py
./.venv/Scripts/python.exe spark/jobs/bronze_to_silver_market_daily.py
./.venv/Scripts/python.exe spark/jobs/bronze_to_silver_reference.py
./.venv/Scripts/python.exe spark/jobs/silver_to_gold_base_panels.py
./.venv/Scripts/python.exe scripts/check_iceberg_acceptance.py
./.venv/Scripts/python.exe spark/jobs/write_iceberg_or_delta_poc.py
./.venv/Scripts/python.exe scripts/load_day2_clickhouse.py
```

## Day3 常用命令

```bash
cd /c/Users/blankxxc/Desktop/work_space/stock_good
./.venv/Scripts/python.exe scripts/run_day3_data_trust.py
./.venv/Scripts/python.exe scripts/check_day3_acceptance.py
```

## Day4 常用命令

```bash
cd /c/Users/blankxxc/Desktop/work_space/stock_good
./.venv/Scripts/python.exe scripts/check_day4_acceptance.py
```

Day4 验收会重新生成/检查因子 store、特征矩阵、Spark consistency artifact、后端 API 和前端页面文案。

## Day5 常用命令

```bash
cd /c/Users/blankxxc/Desktop/work_space/stock_good
./.venv/Scripts/python.exe scripts/check_day5_acceptance.py
```

Day5 验收会重新运行研究闭环并检查标签、模型、预测、持仓、回测、风险报告、实验记录器、API 和前端页面文案。

## Day6 常用命令

```bash
cd /c/Users/blankxxc/Desktop/work_space/stock_good
./.venv/Scripts/python.exe scripts/check_day6_acceptance.py
./.venv/Scripts/python.exe -m pytest tests/test_day6_realtime_streaming.py -q
docker compose -f deploy/docker/docker-compose.yml config --services
```

Day6 验收会重新生成 replay simulated topic logs、实时因子、online feature snapshot、Flink-style job status 和 realtime-vs-offline diff report。该阶段是本地 L1 PoC，不代表接入真实实盘行情。

## Day7 常用命令

```bash
cd /c/Users/blankxxc/Desktop/work_space/stock_good
./.venv/Scripts/python.exe scripts/check_day7_acceptance.py
./.venv/Scripts/python.exe -m pytest tests/test_day7_event_regime.py -q
```

Day7 验收会重新生成新闻/公告事件、事件因子、市场环境因子、增强特征矩阵和 ablation 报告。当前金融文本模型状态是本地 `lexicon_finbert_compatible_baseline_ready`。

## Day8 常用命令

```bash
cd /c/Users/blankxxc/Desktop/work_space/stock_good
./.venv/Scripts/python.exe scripts/check_day8_acceptance.py
./.venv/Scripts/python.exe -m pytest tests/test_day8_relation_graph.py -q
```

Day8 验收会重新生成股票关系边、关系传播因子、HIST/TRSR 输入 adapter、图谱摘要和 relation ablation 报告。

## Day9 常用命令

```bash
cd /c/Users/blankxxc/Desktop/work_space/stock_good
./.venv/Scripts/python.exe scripts/check_day9_acceptance.py
./.venv/Scripts/python.exe -m pytest tests/test_day9_advanced_models.py -q
```

Day9 验收会重新运行 MASTER、StockMixer、HIST、TRSR 的本地 small-sample adapter，生成统一对比报告、experiment recorder artifact 和模型页面/API 验证。当前四个模型均为 `research_candidate_only_not_approved`。

## Day10 常用命令

```bash
cd /c/Users/blankxxc/Desktop/work_space/stock_good
./.venv/Scripts/python.exe scripts/check_day10_acceptance.py
./.venv/Scripts/python.exe -m pytest tests/test_day10_rag_evidence.py -q
```

Day10 验收会重新生成 document/chunk/claim 证据表、claim schema、RAG eval sets、answer/citation cards、RAG API 与 `/rag` 页面验证。当前 RAG 模块为 claim-level evidence research assistant，不生成交易指令。

## Day11 常用命令

```bash
cd /c/Users/blankxxc/Desktop/work_space/stock_good
./.venv/Scripts/python.exe scripts/check_day11_acceptance.py
./.venv/Scripts/python.exe -m pytest tests/test_day11_site_productization.py -q
cd frontend
npm run validate:routes
npm run build
```

Day11 验收会检查官网层路由、Research Console 全页面、artifact-backed 主卡片、禁用文案、Spark/Lakehouse/Realtime 页面入口、`/api/site` 和固定研究边界提示。

## Day12 常用命令

```bash
cd /c/Users/blankxxc/Desktop/work_space/stock_good
./.venv/Scripts/python.exe scripts/check_day12_acceptance.py
./.venv/Scripts/python.exe -m pytest tests/test_day12_simulation_governance.py -q
cd frontend
npm run validate:routes
npm run build
```

Day12 验收会重新生成 paper trading simulation、组合风控报告、RBAC/职责分离、license gate、append-only audit log、report state machine 和 export_manifest，并验证 `/api/simulation`、`/api/reports`、`/api/licenses`、`/api/admin`、`/api/audit` 与对应前端页面。

## Day13 常用命令

```bash
cd /c/Users/blankxxc/Desktop/work_space/stock_good
./.venv/Scripts/python.exe scripts/check_day13_acceptance.py
./.venv/Scripts/python.exe -m pytest tests/test_day13_ops_deployment.py -q
./.venv/Scripts/python.exe scripts/run_day13_pipeline.py --dry-run
docker compose -f deploy/docker/docker-compose.yml config --services
sh deploy/backup/backup_day13.sh --smoke
sh deploy/backup/restore_day13.sh --smoke
cd frontend
npm run validate:routes
npm run build
```

Day13 验收会检查配置解析与 config_hash、prefect-local DAG、backfill dry-run、dataset_snapshot_manifest、可观测性、CI/CD gates、Docker Compose config、backup/restore smoke、Day13 API 和 `/ops` 页面。

## 关键产物

| 产物 | 路径 |
| --- | --- |
| Day4 因子长表 | `data/gold/factor_daily_panel_long` |
| Day4 模型特征矩阵 | `data/gold/model_feature_matrix_wide` |
| Day4 风险暴露 | `data/gold/risk_factor_exposure` |
| Day4 因子报告 | `reports/day4/day4_factor_report.html` |
| Day5 标签 | `data/gold/label_cross_sectional_return` |
| Day5 模型信号 | `data/gold/model_signal_cross_sectional` |
| Day5 回测 Gold 表 | `data/gold/portfolio_backtest_result` |
| Day5 风险 Gold 表 | `data/gold/portfolio_risk_report` |
| Day5 预测 | `reports/day5/predictions.parquet` |
| Day5 持仓 | `reports/day5/holdings.parquet` |
| Day5 净值曲线 | `reports/day5/equity_curve.csv` |
| Day5 风险报告 | `reports/day5/risk_report.parquet` |
| Day5 回测 HTML | `reports/day5/backtest_report.html` |
| Day5 实验记录器 | `reports/day5/experiment_recorder/day5_lightgbm_walk_forward_v001` |
| Day6 Kafka topic logs | `data/realtime/kafka_topics` |
| Day6 实时因子 latest | `reports/day6/realtime_factor_latest.parquet` |
| Day6 intraday factor panel | `data/gold/factor_intraday_panel` |
| Day6 online feature snapshot | `reports/day6/online_feature_snapshot.json` |
| Day6 Flink-style job status | `reports/day6/flink_job_status.json` |
| Day6 realtime/offline diff | `reports/day6/realtime_vs_offline_diff_report.json` |
| Day7 新闻文档 | `data/silver/news_document` |
| Day7 公告文档 | `data/silver/announcement_document` |
| Day7 事件抽取 | `data/silver/event_extraction_result` |
| Day7 事件因子 | `data/gold/factor_news_sentiment_panel` |
| Day7 市场环境因子 | `data/gold/factor_market_regime_panel` |
| Day7 增强特征矩阵 | `data/gold/model_feature_matrix_wide_day7` |
| Day7 ablation 报告 | `reports/day7/event_regime_ablation_report.json` |
| Day8 股票关系边 | `data/gold/stock_relation_edge` |
| Day8 关系传播因子 | `data/gold/factor_relation_panel` |
| Day8 HIST/TRSR 图模型输入 | `data/gold/graph_model_adapters/hist_trsr` |
| Day9 高级模型预测 | `data/gold/advanced_model_predictions` |
| Day9 模型对比 CSV | `data/gold/advanced_model_comparison/model_comparison.csv` |
| Day9 模型对比报告 | `reports/day9/model_comparison_report.json` |
| Day9 实验记录器 | `reports/day9/experiment_recorder` |
| Day10 RAG documents | `data/gold/rag_documents` |
| Day10 RAG chunks | `data/gold/rag_chunks` |
| Day10 RAG claims | `data/gold/rag_claims` |
| Day10 RAG 证据报告 | `reports/day10/rag_evidence_report.json` |
| Day10 RAG eval 报告 | `reports/day10/rag_eval_report.json` |
| Day10 RAG answer/citation cards | `reports/day10/rag_answer_cards.json`, `reports/day10/rag_citation_cards.html` |
| Day11 Site acceptance | `reports/day11/acceptance_report.json` |
| Day11 frontend component | `frontend/src/components/ArtifactStatusCard.tsx` |
| Day11 console data registry | `frontend/src/lib/researchConsoleData.ts` |
| Day12 governance engine | `simulation/day12_governance.py` |
| Day12 acceptance report | `reports/day12/acceptance_report.json` |
| Day12 simulation governance report | `reports/day12/day12_simulation_governance_report.json` |
| Day12 export manifest | `reports/day12/export_manifest.json` |
| Day12 audit log | `reports/day12/audit_log.json` |
| Day12 license gate report | `reports/day12/license_gate_report.json` |
| Day13 ops helper | `ops/day13_ops.py` |
| Day13 acceptance report | `reports/day13/acceptance_report.json` |
| Day13 ops payload | `reports/day13/day13_ops_acceptance_report.json` |
| Day13 resolved config | `reports/day13/runs/day13_<config_hash>/resolved_config.yaml` |
| Day13 pipeline dry-run | `reports/day13/day13_pipeline_dry_run.json` |
| Day13 backfill dry-run | `reports/day13/backfill_dry_run.json` |
| Day13 CI workflow | `.github/workflows/ci.yml` |
| Day13 backup/restore smoke | `deploy/backup/backup_day13.sh`, `deploy/backup/restore_day13.sh` |
| Day13 Ops 页面 | `frontend/src/app/ops/page.tsx` |

## 研究与合规边界

- 系统只生成研究信号，不生成投资建议。
- 所有特征必须满足 point-in-time 约束，不能使用未来信息。
- 历史回测必须考虑停牌、ST、涨跌停、退市、流动性、交易成本、滑点、容量和行业/风格暴露。
- RAG 输出必须有 claim 级引用；没有证据的内容必须标记为假设或证据不足。
- 数据源必须绑定 license_id 和 display/export policy；导出必须通过 Day12 license_gate、redaction 和 export_manifest。
- Day13 运维动作必须先通过 dry-run、snapshot manifest、CI gates、backup/restore smoke 与人工审批，不允许直接覆盖正式报告引用的历史快照。
- 禁止把单次回测、单一年份、单个随机种子或明星模型结果当成收益承诺。

## 后续建议

1. 接入真实授权数据源，并把 Day2 synthetic pipeline 替换为正式 adapter。
2. 准备官方 Qlib 数据目录，跑完整 Qlib workflow，而不只使用 minimal recorder。
3. 扩展模型路线：XGBoost/CatBoost/LambdaRank、MASTER、StockMixer、HIST、Temporal Relational Stock Ranking。
4. 把 Day10 本地 RAG adapter 替换/扩展为 Qdrant/Milvus/pgvector，并接入真实授权研报、公告和新闻源。
5. 把 Day11/Day12 页面从 artifact-backed 静态研究卡片继续升级为可筛选、可钻取、可下载的交互式研究工作台。
6. Day14 继续做最终总验收、release checklist、性能/安全复盘和用户使用文档。


### 14. Day14 最终验收与演示资产

- `ops/day14_final.py` 汇总 Day1-Day14 的最终验收 payload，覆盖 30 个能力区，包括 Spark、Lakehouse、Flink、RAG、风险归因、导出合规、部署与文档。
- `scripts/check_day14_acceptance.py` 固化最终 release gates：pytest/route/build/Compose/backup smoke、no broker integration、no trading advice wording、license gate、RAG citation、point-in-time、manual review required。
- `/api/final-acceptance` 返回最终覆盖矩阵、文档清单、演示资产、blocked reasons、release gates 与 artifact hash。
- `docs/final_acceptance_report.md`、`docs/demo/coverage_matrix.md`、`docs/demo_script.md`、`docs/risk_register.md` 与 ADR-005 记录最终交付、成熟度、剩余风险和 blocked reason。
