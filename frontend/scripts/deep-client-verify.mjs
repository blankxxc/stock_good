import { chromium } from 'playwright';

const routes = [
  {
    name: 'home',
    url: 'http://127.0.0.1:3000/',
    api: 'http://127.0.0.1:3000/api/market',
    getSample: (payload) => payload?.stocks?.find((row) => row?.symbol)?.symbol,
    minText: ['沪深300股票全景', 'Obsidian Alpha'],
  },
  {
    name: 'scores',
    url: 'http://127.0.0.1:3000/scores',
    api: 'http://127.0.0.1:3000/api/scores',
    getSample: (payload) => {
      const horizons = payload?.available_horizons ?? [];
      for (const horizon of horizons) {
        const symbol = payload?.horizon_rankings?.[horizon]?.find((row) => row?.symbol)?.symbol;
        if (symbol) return symbol;
      }
      return payload?.candidate_pool?.find((row) => row?.symbol)?.symbol;
    },
    minText: ['横截面评分台', '研究候选池'],
  },
  {
    name: 'condition-screen',
    url: 'http://127.0.0.1:3000/condition-screen',
    api: 'http://127.0.0.1:3000/api/condition-screen',
    getSample: (payload) => payload?.rows?.find((row) => row?.symbol)?.symbol,
    minText: ['条件实验室', '综合条件通过'],
  },
];

const browser = await chromium.launch({ headless: true });
const results = [];
let hardFailures = 0;

for (const route of routes) {
  const page = await browser.newPage({ viewport: { width: 1440, height: 1100 } });
  const consoleMessages = [];
  const pageErrors = [];
  const requestFailures = [];

  page.on('console', (msg) => {
    if (['error', 'warning'].includes(msg.type())) consoleMessages.push({ type: msg.type(), text: msg.text() });
  });
  page.on('pageerror', (err) => pageErrors.push(err.message));
  page.on('requestfailed', (request) => requestFailures.push({ url: request.url(), failure: request.failure()?.errorText ?? 'unknown' }));

  const apiResponse = await page.request.get(route.api, { timeout: 15000 });
  const payload = apiResponse.ok() ? await apiResponse.json() : null;
  const sample = payload ? route.getSample(payload) : null;

  await page.goto(route.url, { waitUntil: 'domcontentloaded', timeout: 30000 });
  await page.waitForLoadState('networkidle', { timeout: 30000 }).catch(() => null);

  if (sample) {
    await page.waitForFunction((expected) => document.body.innerText.includes(expected), sample, { timeout: 20000 }).catch(() => null);
  }
  await page.waitForTimeout(1500);

  const bodyText = await page.locator('body').innerText({ timeout: 5000 });
  const titleChecks = route.minText.map((text) => ({ text, present: bodyText.includes(text) }));
  const sampleRendered = sample ? bodyText.includes(sample) : false;
  const staleLoading = /加载 \/api\/|加载中…|加载中\.\.\./.test(bodyText);
  const rows = await page.locator('tbody tr').count().catch(() => 0);
  const cards = await page.locator('.card, .artifact-card, .market-board, .hero').count().catch(() => 0);

  const result = {
    name: route.name,
    url: route.url,
    apiStatus: apiResponse.status(),
    apiOk: apiResponse.ok(),
    sample,
    sampleRendered,
    staleLoading,
    rows,
    cards,
    titleChecks,
    consoleErrorCount: consoleMessages.filter((m) => m.type === 'error').length,
    consoleWarningCount: consoleMessages.filter((m) => m.type === 'warning').length,
    pageErrorCount: pageErrors.length,
    requestFailureCount: requestFailures.length,
    consoleMessages,
    pageErrors,
    requestFailures,
  };

  if (!result.apiOk || !sampleRendered || result.pageErrorCount || result.consoleErrorCount || result.requestFailureCount) hardFailures += 1;
  results.push(result);
  await page.close();
}

await browser.close();

const summary = {
  status: hardFailures === 0 ? 'ok' : 'failed',
  hardFailures,
  routes: results,
};
console.log(JSON.stringify(summary, null, 2));
process.exit(hardFailures === 0 ? 0 : 1);
