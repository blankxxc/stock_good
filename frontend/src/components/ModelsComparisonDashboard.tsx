'use client';

import { useEffect, useMemo, useState } from 'react';

type ModelMetric = {
  IC: number | null;
  RankIC: number | null;
  Sharpe: number | null;
  MaxDrawdown: number | null;
  HitRate: number | null;
  Turnover: number | null;
  RuntimeSeconds: number | null;
  maturity?: string;
  status?: string;
};

type ModelsPayload = {
  maturity?: string;
  comparison?: {
    baseline_model?: string;
    models?: Record<string, ModelMetric>;
  };
};

type ModelRow = {
  name: string;
  description: string;
  metrics: ModelMetric;
};

type LoadState = 'loading' | 'success' | 'error';

const MODEL_DEFINITIONS = [
  { name: 'LightGBM', description: '树模型基准' },
  { name: 'MASTER', description: '融合市场状态信息' },
  { name: 'StockMixer', description: '混合时序与股票特征' },
  { name: 'HIST', description: '利用行业与概念关系' },
  { name: 'TRSR', description: '建模股票关系传播' },
] as const;

const UNKNOWN_MODEL_DESCRIPTION = '研究候选模型';

function isNumber(value: number | null | undefined): value is number {
  return typeof value === 'number' && Number.isFinite(value);
}

function formatMetric(value: number | null | undefined) {
  return isNumber(value) ? value.toFixed(4) : '—';
}

function formatPercentage(value: number | null | undefined) {
  return isNumber(value) ? `${(value * 100).toFixed(1)}%` : '—';
}

function formatRuntime(value: number | null | undefined) {
  if (!isNumber(value)) return '—';
  return `${value.toFixed(value < 10 ? 2 : 1)} 秒`;
}

function metricTone(value: number | null | undefined) {
  if (!isNumber(value)) return '';
  return value >= 0 ? 'metric-positive' : 'metric-negative';
}

function joinClasses(...classes: Array<string | false>) {
  return classes.filter(Boolean).join(' ');
}

function researchStatus(maturity: string | undefined) {
  if (maturity?.includes('L2')) return '基准研究';
  if (maturity?.includes('L1')) return '小样本候选';
  return '研究中';
}

function researchPhase(maturity: string | undefined) {
  if (maturity?.includes('L2')) return '基准研究阶段';
  if (maturity?.includes('L1')) return '小样本研究阶段';
  return '研究中';
}

function maximum(rows: ModelRow[], select: (row: ModelRow) => number | null) {
  const values = rows.map(select).filter(isNumber);
  return values.length ? Math.max(...values) : null;
}

function minimum(rows: ModelRow[], select: (row: ModelRow) => number | null) {
  const values = rows.map(select).filter(isNumber);
  return values.length ? Math.min(...values) : null;
}

function winners(
  rows: ModelRow[],
  select: (row: ModelRow) => number | null,
  winningValue: number | null,
) {
  if (!isNumber(winningValue)) return [];
  return rows.filter((row) => select(row) === winningValue);
}

function winnerNames(rows: ModelRow[]) {
  return rows.map((row) => row.name).join('、') || '—';
}

export function ModelsComparisonDashboard() {
  const [payload, setPayload] = useState<ModelsPayload | null>(null);
  const [loadState, setLoadState] = useState<LoadState>('loading');
  const [requestVersion, setRequestVersion] = useState(0);

  useEffect(() => {
    const controller = new AbortController();

    setLoadState('loading');
    setPayload(null);

    fetch('/api/models', { cache: 'no-store', signal: controller.signal })
      .then((response) => {
        if (!response.ok) throw new Error('Models request failed');
        return response.json() as Promise<ModelsPayload>;
      })
      .then((data) => {
        if (!controller.signal.aborted) {
          setPayload(data);
          setLoadState('success');
        }
      })
      .catch(() => {
        if (!controller.signal.aborted) {
          setPayload(null);
          setLoadState('error');
        }
      });

    return () => controller.abort();
  }, [requestVersion]);

  const models = payload?.comparison?.models;
  const hasModels = loadState === 'success' && models !== undefined;

  const rows = useMemo<ModelRow[]>(() => {
    if (!models) return [];

    const knownRows = MODEL_DEFINITIONS
      .filter(({ name }) => Object.prototype.hasOwnProperty.call(models, name))
      .map(({ name, description }) => ({ name, description, metrics: models[name] }));
    const futureRows = Object.keys(models)
      .filter((name) => !MODEL_DEFINITIONS.some((definition) => definition.name === name))
      .sort((left, right) => left.localeCompare(right, 'en'))
      .map((name) => ({
        name,
        description: UNKNOWN_MODEL_DESCRIPTION,
        metrics: models[name],
      }));

    return [...knownRows, ...futureRows];
  }, [models]);

  const bestRankIC = maximum(rows, (row) => row.metrics.RankIC);
  const bestSharpe = maximum(rows, (row) => row.metrics.Sharpe);
  const smallestDrawdown = minimum(rows, (row) => (
    isNumber(row.metrics.MaxDrawdown) ? Math.abs(row.metrics.MaxDrawdown) : null
  ));
  const fastestRuntime = minimum(rows, (row) => row.metrics.RuntimeSeconds);

  const rankICWinners = winners(rows, (row) => row.metrics.RankIC, bestRankIC);
  const sharpeWinners = winners(rows, (row) => row.metrics.Sharpe, bestSharpe);
  const drawdownWinners = winners(rows, (row) => (
    isNumber(row.metrics.MaxDrawdown) ? Math.abs(row.metrics.MaxDrawdown) : null
  ), smallestDrawdown);
  const runtimeWinners = winners(rows, (row) => row.metrics.RuntimeSeconds, fastestRuntime);

  const baselineModel = payload?.comparison?.baseline_model;

  return (
    <div className="models-dashboard">
      <header className="card models-hero">
        <div className="models-hero-copy">
          <h1>模型对比</h1>
          <p>比较预测质量、收益风险与运行效率</p>
        </div>
        <dl className="models-hero-meta">
          <div>
            <dt>模型数量</dt>
            <dd>{hasModels ? rows.length : '—'}</dd>
          </div>
          <div>
            <dt>当前研究阶段</dt>
            <dd>{loadState === 'success' ? (hasModels ? researchPhase(payload?.maturity) : '研究中') : '—'}</dd>
          </div>
        </dl>
      </header>

      {loadState === 'loading' ? (
        <p className="card models-status-message" role="status" aria-live="polite">
          正在加载模型对比数据…
        </p>
      ) : null}

      {loadState === 'error' ? (
        <div className="card models-status-message" role="alert">
          <p>模型数据暂时无法加载。</p>
          <button
            className="models-retry-button"
            type="button"
            onClick={() => setRequestVersion((version) => version + 1)}
          >
            重试
          </button>
        </div>
      ) : null}

      {loadState === 'success' && !hasModels ? (
        <p className="card models-status-message" role="status">
          模型对比数据正在准备中。
        </p>
      ) : null}

      {hasModels && rows.length === 0 ? (
        <p className="card models-status-message" role="status">
          暂无可比较的模型数据。
        </p>
      ) : null}

      {hasModels && rows.length > 0 ? (
        <>
          <section aria-labelledby="models-summary-heading">
            <h2 id="models-summary-heading">关键对比</h2>
            <div className="models-summary-grid">
              <article className="card">
                <span>RankIC 最佳</span>
                <strong>{winnerNames(rankICWinners)}</strong>
                {rankICWinners[0] ? <small>{formatMetric(rankICWinners[0].metrics.RankIC)}</small> : null}
              </article>
              <article className="card">
                <span>Sharpe 最佳</span>
                <strong>{winnerNames(sharpeWinners)}</strong>
                {sharpeWinners[0] ? <small>{formatMetric(sharpeWinners[0].metrics.Sharpe)}</small> : null}
              </article>
              <article className="card">
                <span>回撤最小</span>
                <strong>{winnerNames(drawdownWinners)}</strong>
                {drawdownWinners[0] ? (
                  <small>{formatPercentage(drawdownWinners[0].metrics.MaxDrawdown)}</small>
                ) : null}
              </article>
              <article className="card">
                <span>运行最快</span>
                <strong>{winnerNames(runtimeWinners)}</strong>
                {runtimeWinners[0] ? (
                  <small>{formatRuntime(runtimeWinners[0].metrics.RuntimeSeconds)}</small>
                ) : null}
              </article>
            </div>
          </section>

          <section className="card models-table-card" aria-labelledby="models-table-heading">
            <div className="panel-title-row">
              <h2 id="models-table-heading">指标比较</h2>
            </div>
            <div
              className="models-table-shell"
              tabIndex={0}
              aria-label="模型指标横向对比表"
            >
              <table className="models-comparison-table">
                <caption className="sr-only">模型研究指标对比</caption>
                <thead>
                  <tr>
                    <th scope="col">模型</th>
                    <th scope="col">研究状态</th>
                    <th scope="col">IC</th>
                    <th scope="col">RankIC</th>
                    <th scope="col">Sharpe</th>
                    <th scope="col">最大回撤</th>
                    <th scope="col">胜率</th>
                    <th scope="col">换手率</th>
                    <th scope="col">运行耗时</th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map(({ name, metrics }) => (
                    <tr key={name}>
                      <th scope="row">
                        <strong>{name}</strong>
                        <small>{name === baselineModel ? '基准模型' : '候选模型'}</small>
                      </th>
                      <td><span className="model-research-status">{researchStatus(metrics.maturity)}</span></td>
                      <td className={metricTone(metrics.IC)}>{formatMetric(metrics.IC)}</td>
                      <td className={joinClasses(
                        metricTone(metrics.RankIC),
                        isNumber(metrics.RankIC) && metrics.RankIC === bestRankIC && 'is-best',
                      )}>{formatMetric(metrics.RankIC)}</td>
                      <td className={joinClasses(
                        metricTone(metrics.Sharpe),
                        isNumber(metrics.Sharpe) && metrics.Sharpe === bestSharpe && 'is-best',
                      )}>{formatMetric(metrics.Sharpe)}</td>
                      <td className={joinClasses(
                        isNumber(metrics.MaxDrawdown)
                          && Math.abs(metrics.MaxDrawdown) === smallestDrawdown
                          && 'is-best',
                      )}>{formatPercentage(metrics.MaxDrawdown)}</td>
                      <td>{formatPercentage(metrics.HitRate)}</td>
                      <td>{formatPercentage(metrics.Turnover)}</td>
                      <td className={joinClasses(
                        isNumber(metrics.RuntimeSeconds)
                          && metrics.RuntimeSeconds === fastestRuntime
                          && 'is-best',
                      )}>{formatRuntime(metrics.RuntimeSeconds)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>

          <section aria-labelledby="model-character-heading">
            <h2 id="model-character-heading">模型特点</h2>
            <div className="model-character-grid">
              {rows.map((model) => (
                <article className="card" key={model.name}>
                  <h3>{model.name}</h3>
                  <p>{model.description}</p>
                </article>
              ))}
            </div>
          </section>

          <p className="models-disclaimer">模型结果用于研究比较，不构成投资建议。</p>
        </>
      ) : null}
    </div>
  );
}
