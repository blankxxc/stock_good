import fs from 'fs';
import path from 'path';

const userVisibleRoutes = [
  'page.tsx',
  'capabilities/page.tsx',
  'methodology/page.tsx',
  'data-security/page.tsx',
  'backtest-risk/page.tsx',
  'login/page.tsx',
  'scores/page.tsx',
  'condition-screen/page.tsx',
  'backtests/page.tsx',
  'factors/page.tsx',
  'models/page.tsx',
  'graph/page.tsx',
  'stocks/[symbol]/page.tsx'
];

const internalBackendOnlyRoutes = [
  'dashboard/page.tsx',
  'data-quality/page.tsx',
  'lineage/page.tsx',
  'lakehouse/page.tsx',
  'spark-jobs/page.tsx',
  'realtime/page.tsx',
  'flink-jobs/page.tsx',
  'ops/page.tsx',
  'rag/page.tsx',
  'simulation/page.tsx',
  'reports/page.tsx',
  'settings/licenses/page.tsx',
  'settings/users/page.tsx',
  'settings/audit/page.tsx'
];

const base = path.join(process.cwd(), 'src', 'app');
const missing = userVisibleRoutes.filter(route => !fs.existsSync(path.join(base, route)));
const internalMissing = internalBackendOnlyRoutes.filter(route => !fs.existsSync(path.join(base, route)));
if (missing.length) {
  console.error(JSON.stringify({ status: 'failed', missing }, null, 2));
  process.exit(1);
}
console.log(JSON.stringify({
  status: 'ok',
  route_count: userVisibleRoutes.length,
  user_visible_route_count: userVisibleRoutes.length,
  internal_backend_only_route_count: internalBackendOnlyRoutes.length,
  internal_missing: internalMissing,
  data_fabric_policy: 'backend_admin_only'
}, null, 2));
