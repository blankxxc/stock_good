# Deployment

本项目是智能选股研究平台/量化研究控制台，不是 AI 荐股网站、自动交易系统或买卖点工具；所有输出均为研究信号，必须经过样本外验证、模拟盘、风控、许可证 gate 和人工复核。

## Local commands

```bash
cd /c/Users/blankxxc/Desktop/work_space/stock_good
uv run pytest tests -q
uv run python scripts/check_final_acceptance_acceptance.py
cd frontend && npm run validate:routes && npm run build
cd ..
docker compose -f deploy/docker/docker-compose.yml config --services
sh deploy/backup/backup_ops_deployment.sh --smoke
sh deploy/backup/restore_ops_deployment.sh --smoke
```

## Stack

FastAPI backend、Next.js frontend、PostgreSQL、Redis、Qdrant、Redpanda、Flink、Spark、ClickHouse、Prometheus、Grafana。K8s manifest 是 ops deployment 部署草案，MVP 默认 Docker Compose / 单机运行。
