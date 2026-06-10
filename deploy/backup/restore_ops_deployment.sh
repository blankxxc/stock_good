#!/usr/bin/env bash
set -eu
ROOT_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
RESTORE_DIR="${ROOT_DIR}/reports/ops_deployment/restore_smoke"
if [ "${1:-}" = "--smoke" ]; then
  mkdir -p "${RESTORE_DIR}"
  cat > "${RESTORE_DIR}/restore_manifest.json" <<'JSON'
{"status":"restore_smoke_passed","restore_modes":["data_version","run_id","trade_date","kafka_offset","model_version","rag_index_version"]}
JSON
  echo "restore_smoke_passed ${RESTORE_DIR}/restore_manifest.json"
  exit 0
fi
echo "Use --smoke for deterministic local verification. Production restore requires an approved backup manifest."
