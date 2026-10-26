# Deployment Runbook

服务器安装、环境变量、进程启动和代理配置见 [服务器直接部署](../deployment.md)。

1. 在项目根目录执行 `uv sync --frozen`，然后加载服务器环境变量。
2. 执行 `npm --prefix frontend ci` 和 `npm --prefix frontend run build`。
3. 同步日频数据、模型、报告与本地配置。
4. 分别启动 Python 后端和 Node.js 前端，用服务管理器保持运行。
5. 检查后端 `/health`，再检查站点代理、登录和选股页面。
6. 执行 `uv run python scripts/check_ops_deployment_acceptance.py` 与 `uv run python scripts/check_final_acceptance_acceptance.py`。
7. 执行 `bash deploy/backup/backup_ops_deployment.sh --smoke` 和 `bash deploy/backup/restore_ops_deployment.sh --smoke`。

真实凭证由服务器环境或 secret manager 提供；代码更新时保留认证数据和研究产物。
