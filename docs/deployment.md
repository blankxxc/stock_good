# 服务器直接部署

行情仅使用日频数据。前后端直接运行在服务器上，依赖统一由根目录 `pyproject.toml` / `uv.lock` 和 `frontend/package-lock.json` 管理。

## 准备代码与数据

以下以 Linux 服务器为例，需要 Python 3.11+、Node.js 22 和 uv。在项目根目录执行：

```bash
uv sync --frozen
npm --prefix frontend ci
```

数据、模型和报告多数被 Git 忽略，单独拉取代码不会带上现有研究结果。部署时需要同步实际使用的 `data/`、`reports/`、`models/artifacts/` 及本地环境配置，保留原有目录结构；也可以按 README 的日频流水线重新生成。保留 `frontend/src/`，后端站点目录检查会读取它。

## 环境变量

以根目录 `.env.example` 为模板建立服务器自己的 `.env`，把 `STOCK_GOOD_ENVIRONMENT` 设为 `production`。正式域名使用 HTTPS 时，将 `STOCK_GOOD_SECURE_COOKIE` 设为 `true`，并将 `STOCK_GOOD_ALLOWED_ORIGINS`、`PUBLIC_SITE_ORIGINS` 改为实际站点 origin。

后端不会自动读取 `.env`；启动前通过服务管理器注入变量，或在当前 shell 中加载：

```bash
set -a
. ./.env
set +a
```

`BACKEND_INTERNAL_ORIGIN=http://127.0.0.1:8000` 必须在构建前端前设置，API 代理目标在构建时确定。更改该值后需要重新构建前端。

## 构建与启动

在已经加载环境变量的项目根目录构建：

```bash
npm --prefix frontend run build
```

后端和前端分别以独立进程启动，两者都以项目为工作目录并继承服务器环境变量：

```bash
# 后端
.venv/bin/python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000

# 前端：在另一个终端或服务中执行
HOSTNAME=127.0.0.1 PORT=3000 npm --prefix frontend start
```

前端使用现有 standalone 启动脚本，它会准备静态资源。长期运行时可将上述两个进程交给服务器上的 systemd 等服务管理器管理；当前仓库不预设服务器账号、安装路径或域名。

日常访问使用生产版本，开发模式的按需编译会拖慢首次打开页面。公开研究接口采用有容量上限的进程内缓存，随输入文件的修改、替换或新增分区自动失效；多 worker 各自保存缓存。更新数据无需重启后端，更新代码需重启；修改前端代码或内部 API 地址后需重新构建。

`deploy/proxy/Caddyfile` 是监听 8088 端口的本机 HTTP 调试示例，代理到 `127.0.0.1:8000` 和 `127.0.0.1:3000`。正式上线时按实际域名配置 HTTPS 代理，并与环境变量中的 origin、cookie 配置保持一致。

认证数据默认保存在项目 `.secrets/` 中，应跨重启和代码更新保留。服务账号需要能够写入 `.secrets/`、`reports/` 和需要更新的数据目录。

## 日频更新与检查

日频增量更新沿用现有入口：

```bash
.venv/bin/python scripts/update_daily_market_data.py
curl -f http://127.0.0.1:8000/health
```

可由服务器调度器在收盘后触发更新。模型训练依赖与可选 COGRASP 环境按 README 配置；网站启动本身不触发完整训练。

旧版后复权历史缺少未复权 OHLC / 逐日 ST 状态时，先运行 `python scripts/backfill_daily_price_status.py --publish`。它按股票和日期校验原始 OHLC、成交量、成交额及每日 `isST`，全部通过后备份并原子替换行情文件；中断后可复用已验证缓存。随后运行 `python scripts/update_daily_market_data.py --force-rebuild`，更新最新交易日并重建因子、标签和两套模型。首次诊断可用 `--max-symbols 2`，不会发布部分股票数据。

如另行安装 ClickHouse，可手动执行 `.venv/bin/python scripts/load_lakehouse_clickhouse.py` 导入日频 ADS 表。脚本使用本机 `clickhouse-client` 及其客户端配置；可用 `CLICKHOUSE_CLIENT` 指定可执行文件路径。该导入会刷新目标 ADS 表，不属于默认部署检查。

运维检查：

```bash
.venv/bin/python scripts/check_ops_deployment_acceptance.py
.venv/bin/python scripts/check_final_acceptance_acceptance.py
bash deploy/backup/backup_ops_deployment.sh --smoke
bash deploy/backup/restore_ops_deployment.sh --smoke
```

备份/恢复 smoke 只验证清单流程；服务器正式备份应包含日频数据、模型、报告、配置与 `.secrets/` 中的认证数据。

## 用户自带 Key 的 AI 助手

侧边助手随前端构建发布，后端提供 `/api/assistant/config` 和 `/api/assistant/chat`。无需配置共享密钥，用户在面板内输入自己的 Key。服务器需可访问所选服务商的 HTTPS API；生产环境使用 HTTPS，并避免代理记录请求头或正文。反向代理对聊天路径关闭响应缓冲，读取超时建议至少 100 秒。

可选的兼容服务由后端环境变量 `AI_ASSISTANT_BASE_URL` 和 `AI_ASSISTANT_MODEL` 指定，修改后重启后端；默认服务不需要额外环境变量。使用方法、数据范围和密钥处理见 [AI 助手说明](ai_assistant.md)。
