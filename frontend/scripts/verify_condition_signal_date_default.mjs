import { chromium } from 'playwright';

const pageUrl = process.env.PAGE_URL || 'http://127.0.0.1:3000/condition-screen';
const apiUrl = process.env.API_URL || 'http://127.0.0.1:3000/api/condition-screen';

const apiResponse = await fetch(apiUrl);
if (!apiResponse.ok) {
  throw new Error(`API ${apiUrl} returned HTTP ${apiResponse.status}`);
}
const payload = await apiResponse.json();
const latestTradeDate = payload.latest_trade_date;
if (!latestTradeDate) {
  throw new Error('API payload has no latest_trade_date');
}

const browser = await chromium.launch({ headless: true });
const consoleErrors = [];
const pageErrors = [];
const requestFailures = [];

try {
  const page = await browser.newPage();
  page.on('console', (message) => {
    if (message.type() === 'error') consoleErrors.push(message.text());
  });
  page.on('pageerror', (error) => pageErrors.push(String(error?.message || error)));
  page.on('requestfailed', (request) => {
    requestFailures.push(`${request.method()} ${request.url()} ${request.failure()?.errorText || ''}`.trim());
  });

  await page.goto(pageUrl, { waitUntil: 'networkidle' });
  await page.waitForSelector('.condition-table tbody tr');
  await page.waitForFunction(() => !document.body.textContent?.includes('加载中'));

  const result = await page.evaluate((latest) => {
    const headerCells = Array.from(document.querySelectorAll('.condition-table thead tr:first-child th'));
    const signalDateIndex = headerCells.findIndex((cell) => (cell.textContent || '').trim() === '信号日期');
    const filterCells = Array.from(document.querySelectorAll('.condition-table thead tr:nth-child(2) th'));
    const filterCell = signalDateIndex >= 0 ? filterCells[signalDateIndex] : null;
    const control = filterCell?.querySelector('input, select');
    const firstRows = Array.from(document.querySelectorAll('.condition-table tbody tr')).slice(0, 20);
    const signalDateCells = firstRows
      .map((row) => row.children[signalDateIndex]?.textContent?.trim() || '')
      .filter(Boolean);

    return {
      latest,
      signalDateIndex,
      controlTag: control?.tagName || null,
      controlValue: control?.value || '',
      renderedSignalDates: signalDateCells,
      allSampleRowsLatest: signalDateCells.length > 0 && signalDateCells.every((value) => value === latest),
    };
  }, latestTradeDate);

  const failures = [];
  if (result.signalDateIndex < 0) failures.push('未找到“信号日期”列');
  if (result.controlValue !== latestTradeDate) {
    failures.push(`信号日期筛选默认值错误：expected ${latestTradeDate}, got ${result.controlValue || '<empty>'}`);
  }
  if (!result.allSampleRowsLatest) failures.push('首屏表格样本行不是最新信号日期');
  if (consoleErrors.length) failures.push(`console errors: ${consoleErrors.join(' | ')}`);
  if (pageErrors.length) failures.push(`page errors: ${pageErrors.join(' | ')}`);
  if (requestFailures.length) failures.push(`request failures: ${requestFailures.join(' | ')}`);

  const output = {
    status: failures.length ? 'fail' : 'ok',
    pageUrl,
    apiUrl,
    latestTradeDate,
    result,
    consoleErrorCount: consoleErrors.length,
    pageErrorCount: pageErrors.length,
    requestFailureCount: requestFailures.length,
    failures,
  };
  console.log(JSON.stringify(output, null, 2));
  if (failures.length) process.exit(1);
} finally {
  await browser.close();
}
