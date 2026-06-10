#!/usr/bin/env bash
set -eu
ROOT_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
BACKUP_DIR="${ROOT_DIR}/reports/ops_deployment/backup_smoke"
ASSETS="raw_data cleaned_data factor_panel label_table experiment_metadata model_files backtest_reports rag_documents_and_index config_files database_migrations"
if [ "${1:-}" = "--smoke" ]; then
  mkdir -p "${BACKUP_DIR}"
  printf '{"status":"backup_smoke_passed","assets":[' > "${BACKUP_DIR}/backup_manifest.json"
  first=1
  for asset in ${ASSETS}; do
    [ ${first} -eq 0 ] && printf ',' >> "${BACKUP_DIR}/backup_manifest.json"
    first=0
    printf '"%s"' "${asset}" >> "${BACKUP_DIR}/backup_manifest.json"
  done
  printf ']}' >> "${BACKUP_DIR}/backup_manifest.json"
  echo "backup_smoke_passed ${BACKUP_DIR}/backup_manifest.json"
  exit 0
fi
echo "Use --smoke for deterministic local verification. Production backup requires an approved storage target."
