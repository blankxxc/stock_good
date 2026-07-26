# stock_good — 智能选股研究平台

stock_good 是一个本地全栈智能选股研究平台样例，目标不是直接给出买卖指令，而是把“数据接入 → 数据治理 → 因子工程 → 模型训练 → 回测评估 → 研究证据 → 模拟盘治理 → Web Research Console”串成可复现、可验证、可解释的研究闭环。

当前 README 不再按开发计划里的 foundation-final acceptance 叙述。仓库中仍保留部分 `day*` 文件名、脚本名和报告目录，那只是历史开发阶段留下的命名，实际使用时按下面的功能模块和调用方式理解即可。

## 研究边界

- 本项目输出研究信号、横截面分数、候选组合、回测报告、风险解释和 RAG 证据，不构成投资建议。
- 任何真实交易前都必须经过授权数据、样本外验证、交易成本/滑点/容量评估、模拟盘、风控约束和人工复核。
- RAG/LLM 只用于证据组织、研究解释和实验假设，不允许把文本结论直接当作交易指令。

## 默认数据口径

先采用“沪深300近三年日频数据”作为主线数据范围：

- 股票池：沪深300，使用点时间成分历史，避免未来成分股和幸存者偏差。
- 时间范围：滚动近三年，以最新可用交易日为结束点。
- 频率：日频为主，只处理 daily OHLCV、成交额、复权因子、指数成分历史、行业/参考维表等。
- 暂不处理：分钟、tick、盘口等高频数据。原因是本地存储优先保证日频闭环，高频数据量更大且通常需要额外供应商授权。
- 配置入口：
  - `configs/universe/csi300.yaml`
  - `configs/data/daily_mvp.yaml`
- 数据治理要求：所有真实外部数据源必须绑定 `license_id`、授权状态、展示策略和导出策略；没有授权时只允许 schema/adapter 占位或 synthetic sample。

推荐真实数据落地范围：

```text
data/
  bronze/   原始授权数据快照，按 trade_date 分区
  silver/   清洗、复权、去异常、对齐交易日后的日频数据
  gold/     因子长表、模型宽表、标签、分数、回测与报告输入
reports/    验收、模型、回测、RAG、导出 manifest 和运维报告
```

## 核心能力

### 1. 数据契约与许可证治理

- `data_contracts/*.schema.yaml` 定义行情、财务、公告、新闻、宏观、资金流、因子、标签、信号、回测、RAG claim、导出 manifest 等契约。
- `configs/data/source_license_registry.yaml` 记录数据源授权、展示和导出边界。
- `/api/licenses` 展示许可证策略、可用范围、导出限制和治理结果。

### 2. 湖仓与批处理

- 本地以 Parquet/DuckDB/Spark/Polars 组合完成轻量湖仓 PoC。
- 支持 ODS/Bronze、DWD/Silver、DWS/Gold、ADS/报告层的分层设计。
- 支持 snapshot manifest、数据版本、回填 dry-run 和不可变正式报告快照。
- 当前主线聚焦日频行情；分钟/实时流只保留 PoC 与接口边界，不作为默认数据路径。

### 3. 数据质量、防泄漏与血缘

- 数据质量检查覆盖缺失、异常、停牌、涨跌停、延迟、quarantine 和质量报告。
- 防泄漏检查覆盖 available_time、prediction_time、point-in-time join、公告/新闻发布时间和全样本归一化风险。
- 血缘记录 source、job、snapshot、report、model、RAG index 等关键节点。

### 4. 因子库与 Feature Store

- 当前实现离线因子长表与模型宽表，覆盖价格收益、动量、反转、波动率、流动性、成交量、风险暴露等类别。
- 因子长表：`data/gold/factor_daily_panel_long`
- 模型宽表：`data/gold/model_feature_matrix_wide`
- 因子必须带版本、窗口、计算时点、可用时点和 research boundary。

### 5. 建模、回测与研究循环

- 预测任务采用横截面选股：在某个交易时点对股票池打分/排序，而不是预测单只股票绝对价格。
- 默认标签方向：5d/10d 未来收益、超额收益、行业中性收益或横截面分位标签。
- baseline 包含 LightGBM 与 Qlib-compatible recorder；高级模型 adapter 覆盖 MASTER、StockMixer、HIST、TRSR 的本地研究候选形态。
- 回测输出包含 IC/RankIC、分位组合、TopK、long-short、换手、交易成本、最大回撤、Sharpe/Calmar、容量和风险暴露。

### 6. 事件、关系图与高级研究特征

- 事件侧支持新闻/公告样例、金融文本情绪 baseline、事件因子、市场状态因子和 ablation 报告。
- 关系侧支持行业、概念、价格相关、共现、lead-lag 等关系边，生成 centrality/community 与关系传播因子。
- 图模型和深度模型当前是研究候选 adapter，不等同于官方完整生产训练。

### 7. RAG 证据系统

- 支持 paper、factor card、strategy card、experiment card、backtest report、failure case、market review、announcement、news、research note、relation case 等研究资料类型。
- 证据粒度到 claim，包含 citation span、license、event_time、publish_time、available_time、valid_from/valid_to、evidence strength 和 index version。
- as-of 检索默认要求 `available_time <= prediction_time`；复盘型 hindsight 结论必须显式标注 retrospective。

### 8. 模拟盘、权限、审计与报告导出

- 模拟盘只用于研究验证，不连接真实券商下单。
- 报告状态机覆盖 draft、review、approved、exportable、exported、revoked。
- 导出前必须通过 data quality、leakage、license gate、RAG citation、forbidden wording 等门禁。
- 审计日志使用 append-only 语义，导出 manifest 包含 run/data/factor/model/label/RAG source version、watermark、disclaimer、file_hash 和 audit_id。

### 9. Web Research Console

前端是 Next.js Research Console，后端是 FastAPI。主要页面：

```text
/                         官网首页
/capabilities             能力说明
/methodology              方法论
/data-security            数据与安全边界
/backtest-risk            回测与风险
/rag-evidence             RAG 证据说明
/architecture-roadmap     架构路线
/login                    登录入口占位
/dashboard                研究总览
/data-quality             数据质量与防泄漏
/lineage                  血缘
/lakehouse                湖仓与 snapshot
/spark-jobs               Spark/批处理任务
/factors                  因子库
/features                 Feature Store
/scores                   模型分数与排序
/backtests                回测与风险
/experiments              实验记录
/realtime                 实时/分钟 PoC 状态，默认不作为主线数据
/flink-jobs               Flink-style PoC 状态
/graph                    股票关系图
/models                   模型与高级 adapter
/rag                      研究证据
/simulation               模拟盘研究账户
/reports                  报告状态机与导出
/ops                      运维、配置哈希、回填、备份恢复
/settings/licenses        数据许可证
/settings/users           RBAC 用户/角色
/settings/audit           审计日志
```

## 目录结构

```text
backend/                         FastAPI 后端与 API 路由
configs/                         项目、环境、股票池、数据、因子、标签、模型、回测、流式和 Spark 配置
data/                            本地数据、样例数据、湖仓分层和生成结果
data_contracts/                  数据契约 schema
deploy/                          Docker Compose、代理、监控、备份恢复和 K8s 草案
docs/                            架构、验收、演示脚本、ADR 和风险登记
frontend/                        Next.js Research Console
models/                          研究闭环、baseline、高级模型 adapter 和实验输出
ops/                             配置解析、DAG、回填、可观测性、部署与最终验收 payload
quality/                         数据质量、防泄漏、血缘和可信度逻辑
rag/                             claim 级 RAG schema、检索、评测和引用卡片
reports/                         验收报告、质量报告、回测报告、RAG 报告和导出 manifest
scripts/                         一键验收、数据流水线、运维和 smoke 脚本
simulation/                      模拟盘、风控、RBAC、license/report governance
spark/                           Spark 本地批处理与因子物化任务
tests/                           pytest 测试
warehouse_schema/                数仓表结构草案
```

## 快速开始

以下命令假设在 Windows Git Bash/MSYS 环境中运行，路径使用 `/c/Users/...`。

### 1. 安装依赖

```bash
cd /c/Users/blankxxc/Desktop/work_space/stock_good
uv sync

cd frontend
npm install
```

如果本机已经有项目虚拟环境，也可以直接使用：

```bash
./.venv/Scripts/python.exe --version
```

### 2. 启动后端 API

```bash
cd /c/Users/blankxxc/Desktop/work_space/stock_good
./.venv/Scripts/python.exe -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
```

健康检查：

```bash
curl http://127.0.0.1:8000/health
```

常用 API：

```text
GET /health
GET /api/dashboard
GET /api/data-quality
GET /api/lineage
GET /api/lakehouse
GET /api/spark-jobs
GET /api/factors
GET /api/features
GET /api/scores
GET /api/backtests
GET /api/experiments
GET /api/realtime
GET /api/flink-jobs
GET /api/graph
GET /api/models
GET /api/rag
GET /api/simulation
GET /api/reports
GET /api/ops
GET /api/orchestration
GET /api/backfill
GET /api/observability
GET /api/deployment
GET /api/final-acceptance
GET /api/licenses
GET /api/admin
GET /api/audit
```

调用示例：

```bash
curl http://127.0.0.1:8000/api/factors
curl http://127.0.0.1:8000/api/backtests
curl http://127.0.0.1:8000/api/rag
curl http://127.0.0.1:8000/api/ops
```

Python 内部调用示例：

```python
from fastapi.testclient import TestClient
from backend.app.main import app

client = TestClient(app)
print(client.get("/health").json())
print(client.get("/api/factors").json())
```

### 3. 启动前端网站

```bash
cd /c/Users/blankxxc/Desktop/work_space/stock_good/frontend
npm run validate:routes
npm run dev
```

浏览器打开：

```text
http://127.0.0.1:3000/
```

生产构建：

```bash
cd /c/Users/blankxxc/Desktop/work_space/stock_good/frontend
npm run build
```

### 4. 运行主线日频数据流水线

当前主线以沪深300近三年日频为目标口径。日频获取器默认执行幂等增量更新：读取本地最大交易日，回看 7 个自然日以接收上游修订，只在发现新增或修订行情时原子替换 Parquet；无变化时不写数据文件。

只获取日频行情：

```powershell
.\.venv\Scripts\python.exe scripts\fetch_real_csi300_daily.py
```

获取行情，并仅在数据变化时重算因子、标签和最新评分：

```powershell
.\.venv\Scripts\python.exe scripts\update_daily_market_data.py
```

常用参数：

```powershell
# 强制重建近三年历史；日常任务不要使用
.\.venv\Scripts\python.exe scripts\fetch_real_csi300_daily.py --full-refresh

# 即使行情没有变化也重算下游产物
.\.venv\Scripts\python.exe scripts\update_daily_market_data.py --force-rebuild

# 明确允许盘中快照桥接；默认关闭，正式日频建议收盘后运行
.\.venv\Scripts\python.exe scripts\fetch_real_csi300_daily.py --use-snapshot
```

Windows 包装脚本默认执行完整流水线（行情、因子、标签、评分）；只有维护时明确传入 `-FetchOnly` 才只抓行情。可将脚本加入任务计划，在交易日 16:40 后执行，并在失败时最多重试 3 次：

```powershell
schtasks /Create /TN "StockGoodDailyData" /SC WEEKLY /D MON,TUE,WED,THU,FRI /ST 16:40 /TR "powershell.exe -NoProfile -ExecutionPolicy RemoteSigned -File C:\Users\blankxxc\Desktop\work_space\stock_good\scripts\run_daily_data_update.ps1 -RetryCount 3 -RetryDelaySeconds 1800" /F
```

抓取报告写入 `reports/real_data/csi300_daily_ingestion_report.json`，完整流水线报告和 checkpoint 分别写入 `reports/daily_update/daily_market_data_update_report.json` 与 `reports/daily_update/pipeline_state.json`，每次运行同时保留历史报告和日志。退出码为 0 表示成功或无变化；抓取失败、部分失败、数据过期或并发任务冲突时返回非 0，未通过完整性门禁的候选数据不会替换旧 Parquet。

仓库里的湖仓脚本会继续生成/验证本地可复现数据；接入正式授权数据时，应保持相同 schema、license gate 和 snapshot manifest。

```bash
cd /c/Users/blankxxc/Desktop/work_space/stock_good
./.venv/Scripts/python.exe scripts/run_lakehouse_pipeline.py
./.venv/Scripts/python.exe spark/jobs/bronze_to_silver_market_daily.py
./.venv/Scripts/python.exe spark/jobs/bronze_to_silver_reference.py
./.venv/Scripts/python.exe spark/jobs/silver_to_gold_base_panels.py
```

说明：这些脚本名中仍包含历史阶段命名，但它们现在代表“日频批处理/湖仓/基础面板”入口，不需要按开发天数理解。

### 5. 运行研究与验收检查

轻量核心验收：

```bash
cd /c/Users/blankxxc/Desktop/work_space/stock_good
./.venv/Scripts/python.exe scripts/check_final_acceptance_acceptance.py
./.venv/Scripts/python.exe -m pytest tests/test_governance_simulation_simulation_governance.py tests/test_ops_deployment_ops_deployment.py tests/test_final_acceptance_final_acceptance.py -q
```

完整 pytest：

```bash
cd /c/Users/blankxxc/Desktop/work_space/stock_good
./.venv/Scripts/python.exe -m pytest -q
```

前端验证：

```bash
cd /c/Users/blankxxc/Desktop/work_space/stock_good/frontend
npm run validate:routes
npm run build
```

Docker Compose 配置检查：

```bash
cd /c/Users/blankxxc/Desktop/work_space/stock_good
docker compose -f deploy/docker/docker-compose.yml config --services
```

备份恢复 smoke：

```bash
cd /c/Users/blankxxc/Desktop/work_space/stock_good
sh deploy/backup/backup_ops_deployment.sh --smoke
sh deploy/backup/restore_ops_deployment.sh --smoke
```

## 真实数据接入建议

沪深300近三年日频落地时，优先保证以下字段：

```text
symbol, trade_date, open, high, low, close, volume, amount, adj_factor,
index_code, membership_start_date, membership_end_date,
industry_code, industry_name, available_time, source, license_id
```

接入顺序建议：

1. 准备沪深300点时间成分历史，不要用当前成分股倒推历史。
2. 准备近三年日频 OHLCV 与成交额。
3. 准备复权因子，明确前复权/后复权/不复权口径。
4. 准备行业/指数/交易日历等参考维表。
5. 写入 Bronze 原始层，保留 source、ingest_time、license_id 和原始文件 hash。
6. 清洗到 Silver，处理缺失、停牌、涨跌停、异常值、交易日对齐。
7. 生成 Gold 因子长表、模型宽表、标签和回测输入。
8. 跑防泄漏、质量、许可证和 snapshot manifest 检查。
9. 只在通过门禁后进入模型训练、回测、RAG 解释和报告导出。

分钟频率后续再处理时，需要单独扩展：

- 存储容量预算和分区策略；
- 供应商授权与展示/导出限制；
- Kafka/Flink 或离线分钟批处理路径；
- online/offline feature consistency 检查；
- 更严格的交易成本、滑点、延迟和容量评估。

## 运维与配置

- 主配置：`configs/base.yaml`
- 股票池：`configs/universe/csi300.yaml`
- 数据集：`configs/data/daily_mvp.yaml`
- 因子：`configs/factor/alpha_mvp_v001.yaml`
- 标签：`configs/label/label_5d_10d_v001.yaml`
- 模型：`configs/model/lightgbm_baseline.yaml`
- 回测：`configs/backtest/top50_weekly_vwap.yaml`
- 编排：`ops/ops_deployment_ops.py` 使用 `prefect-local` 语义生成 DAG、config hash、backfill dry-run、observability 和 deployment payload。

`/api/ops`、`/api/orchestration`、`/api/backfill`、`/api/observability`、`/api/deployment` 可用于查看运维状态。

## 安全与合规注意事项

- 不要提交真实 API key、token、账号密码、数据供应商凭证或未授权原始数据。
- 不要把单次回测、单一年份、单个随机种子或明星模型结果写成收益承诺。
- 不要使用未来指数成分、未来公告发布时间、全样本归一化或同收盘价交易假设。
- 导出报告必须附带研究边界、数据版本、模型版本、回测区间、风险提示、license gate 和 export manifest。

## 后续建议

1. 用授权数据源替换 synthetic adapter，先只跑沪深300近三年日频。
2. 为真实数据新增数据导入脚本或 adapter，并保持现有 schema 与 license gate。
3. 把 Web Console 的数据口径文案统一改成“沪深300近三年日频”。
4. 完成日频闭环后，再评估分钟数据的存储、授权、流式架构和运维成本。
5. 在真实数据上重新跑全量防泄漏、质量、回测、RAG 引用和导出门禁。
