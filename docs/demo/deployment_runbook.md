# Deployment Runbook

1. `uv run pytest tests -q`
2. `uv run python scripts/check_day14_acceptance.py`
3. `cd frontend && npm run validate:routes && npm run build`
4. `docker compose -f deploy/docker/docker-compose.yml config --services`
5. `sh deploy/backup/backup_day13.sh --smoke`
6. `sh deploy/backup/restore_day13.sh --smoke`

真实 credentials 必须放在本地环境或 secret manager，不进入 Git。
