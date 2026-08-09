// Supplemental source contract only; Task 4 browser integration verifies rendered and functional behavior.
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const pagePath = path.join(root, 'src', 'app', 'models', 'page.tsx');
const componentPath = path.join(root, 'src', 'components', 'ModelsComparisonDashboard.tsx');
const cssPath = path.join(root, 'src', 'app', 'globals.css');

function readRequired(filePath) {
  try {
    return fs.readFileSync(filePath, 'utf8');
  } catch (error) {
    console.error(`Unable to read ${path.relative(root, filePath)}: ${error.message}`);
    process.exit(1);
  }
}

function readOptional(filePath) {
  try {
    return fs.readFileSync(filePath, 'utf8');
  } catch (error) {
    if (error.code === 'ENOENT') return null;
    console.error(`Unable to read ${path.relative(root, filePath)}: ${error.message}`);
    process.exit(1);
  }
}

const pageSource = readRequired(pagePath);
const componentSource = readOptional(componentPath);
const cssSource = readRequired(cssPath);
const publicModelsSource = [pageSource, componentSource].filter(Boolean).join('\n');
const failures = [];

function assert(condition, message) {
  if (!condition) failures.push(message);
}

assert(
  /import\s+(?:ModelsComparisonDashboard|\{[^}]*\bModelsComparisonDashboard\b[^}]*\})\s+from\s+['"][^'"]*ModelsComparisonDashboard['"]/.test(pageSource),
  'src/app/models/page.tsx must import ModelsComparisonDashboard'
);
assert(
  /<ModelsComparisonDashboard(?:\s|\/|>)/.test(pageSource),
  'src/app/models/page.tsx must render ModelsComparisonDashboard'
);
assert(
  componentSource !== null,
  'src/components/ModelsComparisonDashboard.tsx must exist'
);

if (componentSource !== null) {
  const requiredComponentText = [
    '模型对比',
    'RankIC 最佳',
    'Sharpe 最佳',
    '回撤最小',
    '运行最快',
    'LightGBM',
    'MASTER',
    'StockMixer',
    'HIST',
    'TRSR'
  ];

  for (const text of requiredComponentText) {
    assert(
      componentSource.includes(text),
      `ModelsComparisonDashboard.tsx must contain ${text}`
    );
  }

  const requiredTableHeaders = [
    '模型',
    '研究状态',
    'IC',
    'RankIC',
    'Sharpe',
    '最大回撤',
    '胜率',
    '换手率',
    '运行耗时'
  ];

  for (const header of requiredTableHeaders) {
    const escapedHeader = header.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    const headerPattern = new RegExp(`<th(?:\\s+scope=["']col["'])?\\s*>\\s*${escapedHeader}\\s*<\\/th>`);
    assert(
      headerPattern.test(componentSource),
      `ModelsComparisonDashboard.tsx must include the ${header} table header`
    );
  }

  assert(
    /fetch\s*\(\s*['"`]\/api\/models(?:['"`]|[?#])/.test(componentSource),
    'ModelsComparisonDashboard.tsx must fetch /api/models'
  );
}

const forbiddenPublicText = [
  'ArtifactStatusCard',
  '真实数据入口',
  '可追溯字段',
  '验收兼容说明',
  'data_mode',
  'artifact-backed',
  'compatibility-checkpoints'
];

for (const text of forbiddenPublicText) {
  assert(
    !publicModelsSource.includes(text),
    `public Models page/component source must exclude ${text}`
  );
}

const requiredCssClasses = [
  'models-dashboard',
  'models-summary-grid',
  'models-comparison-table',
  'model-character-grid'
];

for (const className of requiredCssClasses) {
  const selector = new RegExp(`\\.${className}(?![\\w-])`);
  assert(
    selector.test(cssSource),
    `src/app/globals.css must include .${className}`
  );
}

if (failures.length > 0) {
  console.error('Models source contract failed:');
  for (const failure of failures) console.error(`- ${failure}`);
  process.exit(1);
}

console.log('Models source contract passed.');
