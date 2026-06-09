import fs from 'fs';
import path from 'path';

const routes = [
  'page.tsx',
  'capabilities/page.tsx',
  'methodology/page.tsx',
  'data-security/page.tsx',
  'backtest-risk/page.tsx',
  'rag-evidence/page.tsx',
  'architecture-roadmap/page.tsx',
  'login/page.tsx',
  'dashboard/page.tsx',
  'scores/page.tsx',
  'candidates/page.tsx',
  'backtests/page.tsx',
  'factors/page.tsx',
  'experiments/page.tsx',
  'rag/page.tsx',
  'data-quality/page.tsx',
  'lineage/page.tsx',
  'lakehouse/page.tsx',
  'spark-jobs/page.tsx',
  'realtime/page.tsx',
  'flink-jobs/page.tsx',
  'graph/page.tsx',
  'models/page.tsx',
  'simulation/page.tsx',
  'reports/page.tsx',
  'settings/licenses/page.tsx',
  'settings/users/page.tsx',
  'settings/audit/page.tsx',
  'ops/page.tsx'
];
const base = path.join(process.cwd(), 'src', 'app');
const missing = routes.filter(route => !fs.existsSync(path.join(base, route)));
if (missing.length) {
  console.error(JSON.stringify({ status: 'failed', missing }, null, 2));
  process.exit(1);
}
console.log(JSON.stringify({ status: 'ok', route_count: routes.length }, null, 2));
