'use client';

import { useState } from 'react';
import { useApiPayload } from '../lib/useApiPayload';

type ScoreRow = {
  trade_date: string;
  prediction_target_date?: string;
  symbol: string;
  stock_name?: string;
  industry_name?: string;
  score?: number;
  probability_up?: number;
  probability_down?: number;
  predicted_relative_change?: number;
  predicted_relative_change_pct?: number;
  rank?: number;
  percentile?: number;
  horizon?: string;
  model_name?: string;
  model_family?: string;
  model_version?: string;
  market_regime?: string;
  sentiment_score?: number;
  sentiment_source?: string;
  sentiment_coverage?: number;
  relation_signal?: number;
  candidate_reason?: string;
  review_action?: string;
};

type CandidateSummary = {
  source_horizon?: string;
  candidate_count?: number;
  pool_definition?: string;
};

type ScoreModelOption = {
  id: string;
  label: string;
  description?: string;
  status?: 'ready' | 'pending' | string;
  latest_trade_date?: string;
  model_version?: string;
  integration_status?: string;
  runtime_requirements?: string;
  runtime_blockers?: string[];
};

export type ScoresPayload = {
  status?: string;
  latest_trade_date?: string;
  latest_trade_date_by_horizon?: Record<string, string>;
  available_horizons?: string[];
  horizon_rankings?: Record<string, ScoreRow[]>;
  candidate_pool?: ScoreRow[];
  candidate_summary?: CandidateSummary;
  selected_model?: string;
  available_models?: ScoreModelOption[];
  model_description?: string;
  model_family?: string;
  prediction_target_date?: string;
  prediction_target_date_is_estimated?: boolean;
  latest_training_label_date?: string;
  training_sample_count?: number;
  relationship_graph?: string;
  test_metrics?: {
    mse?: number;
    mae?: number;
    ic_mean?: number;
    rank_ic_mean?: number;
  };
  sentiment_status?: string;
  text_sentiment_coverage?: number;
  news_event_rows?: number;
  news_symbol_coverage?: number;
  market_sentiment_proxy?: number;
  risk_appetite_proxy?: number;
  implementation_scope?: string;
  integration_status?: string;
  runtime_requirements?: string;
  runtime_blockers?: string[];
  training_command?: string;
  upstream_source?: {
    repository?: string;
    paper?: string;
    commit?: string;
    license?: string;
  };
  api_note?: string;
};

const fallbackHorizons = ['1d'];

function formatScore(value: number | undefined) {
  if (typeof value !== 'number' || Number.isNaN(value)) return '—';
  return value.toFixed(3);
}

function formatRelativeChange(value: number | undefined) {
  if (typeof value !== 'number' || Number.isNaN(value)) return '—';
  return `${value >= 0 ? '+' : ''}${value.toFixed(3)}%`;
}

function horizonLabel(horizon: string) {
  if (horizon === '1d') return '未来1d';
  return horizon;
}

function displayIndustry(value: string | undefined) {
  if (!value || value.startsWith('unknown_')) return '—';
  return value;
}

export function HorizonProbabilityTable({ initialPayload = null }: { initialPayload?: ScoresPayload | null }) {
  const [selectedModel, setSelectedModel] = useState(initialPayload?.selected_model ?? 'cograsp');
  const scoresApiUrl = `/api/scores?model=${encodeURIComponent(selectedModel)}`;
  const { payload, error, loading, reload } = useApiPayload<ScoresPayload>(scoresApiUrl, initialPayload);
  const [selectedCandidateHorizon, setSelectedCandidateHorizon] = useState('1d');
  const [selectedCandidateLimit, setSelectedCandidateLimit] = useState(20);

  const modelOptions = payload?.available_models?.length
    ? payload.available_models
    : [
      { id: 'cograsp', label: 'COGRASP 当前沪深300重训', status: 'ready' },
      { id: 'sentiment_event', label: '情绪/事件融合 LightGBM', status: 'pending' },
      { id: 'finmamba', label: 'FinMamba 官方模型', status: 'blocked_runtime' },
    ];
  const selectedModelOption = modelOptions.find((option) => option.id === selectedModel);
  const usesSentiment = selectedModel === 'sentiment_event';
  const usesFinMamba = selectedModel === 'finmamba';
  const modelIsReady = payload?.status === 'research_loop_scores_ready';

  function selectModel(modelId: string) {
    setSelectedModel(modelId);
    const url = new URL(window.location.href);
    url.searchParams.set('model', modelId);
    window.history.pushState(null, '', url);
  }

  const horizons = payload?.available_horizons?.filter((h) => fallbackHorizons.includes(h)) ?? fallbackHorizons;
  const candidateSourceHorizon = horizons.includes(selectedCandidateHorizon) ? selectedCandidateHorizon : (horizons[0] ?? '1d');
  const candidateSourceRows = payload?.horizon_rankings?.[candidateSourceHorizon] ?? payload?.candidate_pool ?? [];
  const normalizedCandidateLimit = Math.min(Math.max(1, selectedCandidateLimit || 1), Math.max(candidateSourceRows.length, 1));
  const candidatePool = candidateSourceRows.slice(0, normalizedCandidateLimit);
  const candidateMetadataBySymbol = new Map((payload?.candidate_pool ?? []).map((row) => [row.symbol, row]));

  return (
    <div className="card artifact-backed prediction-selection" aria-busy={loading && !payload}>
      <div className="artifact-card__topline">
        <span className="badge">股票预测选股</span>
        <span className="status-pill">{payload?.model_family ?? selectedModelOption?.label ?? '预测模型'} · 1d Top10</span>
      </div>
      <div className="workflow-page-heading workflow-page-heading--compact">
        <span className="workflow-page-heading__eyebrow">可切换模型回归输出</span>
        <h1>下一交易日相对涨跌排行</h1>
        <p>{payload?.model_description ?? selectedModelOption?.description ?? '选择模型查看对应的最新预测结果。'}</p>
      </div>
      <div className="model-selector-panel" aria-label="预测模型选择">
        <label>
          <span>预测模型</span>
          <select
            className="model-selector"
            value={selectedModel}
            onChange={(event) => selectModel(event.target.value)}
            disabled={loading && !payload}
          >
            {modelOptions.map((option) => (
              <option key={option.id} value={option.id}>
                {option.label}{option.status === 'ready' ? '' : option.status === 'blocked_runtime' ? '（环境待就绪）' : '（尚未训练）'}
              </option>
            ))}
          </select>
        </label>
        <div>
          <strong>{selectedModelOption?.label ?? payload?.model_family ?? selectedModel}</strong>
          <span>{selectedModelOption?.description ?? payload?.model_description ?? '加载模型说明…'}</span>
        </div>
      </div>
      {error ? (
        <div className="data-state data-state--error" role="alert">
          <span>暂时无法读取评分数据：{error}</span>
          <button className="button table-button" type="button" onClick={reload} disabled={loading}>重新加载</button>
        </div>
      ) : null}
      {payload?.latest_trade_date
        ? <p className="muted">最新输入截面：{payload.latest_trade_date} · 预测目标：{payload.prediction_target_date ?? '下一交易日'}{payload.prediction_target_date_is_estimated ? '（按下一工作日估算）' : ''}</p>
        : !payload || loading
          ? <p className="data-state" role="status" aria-live="polite">正在加载评分数据…</p>
          : null}
      {payload && !modelIsReady ? (
        <div className="data-state" role="status" aria-live="polite">
          <strong>{usesFinMamba ? 'FinMamba 已接入，当前运行环境尚未就绪。' : '该模型尚未生成可展示的预测结果。'}</strong>
          {payload.runtime_requirements ? <span>需要：{payload.runtime_requirements}</span> : null}
          {payload.runtime_blockers?.length ? <span>当前阻塞：{payload.runtime_blockers.join('；')}</span> : null}
          {payload.training_command ? <code>{payload.training_command}</code> : null}
        </div>
      ) : null}
      {payload ? (
        <div className="artifact-card__topline" aria-label="预测模型与输入口径">
          <span className="status-pill">模型：{payload.model_family ?? selectedModelOption?.label ?? selectedModel}</span>
          <span className="muted">
            {payload.training_sample_count ?? '—'} 个训练样本
            {usesSentiment
              ? ' · 市场情绪代理始终启用，真实新闻按覆盖情况融合。'
              : usesFinMamba
                ? ' · 20日 Spearman 动态关系图 × 行业衰减；作者原版结构。'
                : ' · 收益相关性 Top8 关系图，不含文本情绪。'}
          </span>
        </div>
      ) : null}
      {usesSentiment && payload ? (
        <div className="sentiment-evidence-grid" aria-label="情绪与事件输入状态">
          <div><span>市场情绪代理</span><strong>{formatScore(payload.market_sentiment_proxy)}</strong></div>
          <div><span>风险偏好代理</span><strong>{formatScore(payload.risk_appetite_proxy)}</strong></div>
          <div><span>近期新闻覆盖</span><strong>{payload.text_sentiment_coverage ?? 0} / 300</strong></div>
          <div><span>新闻缓存</span><strong>{payload.news_event_rows ?? 0} 条</strong></div>
          <p>{payload.implementation_scope ?? 'CAMEF/CARAG-inspired 日频实现，不宣称完整复现论文模型。'}</p>
        </div>
      ) : null}
      {payload?.test_metrics ? (
        <p className="data-state" role="note">
          样本外 MAE：{typeof payload.test_metrics.mae === 'number' ? `${payload.test_metrics.mae.toFixed(3)} 个百分点` : '—'}；
          RankIC：{typeof payload.test_metrics.rank_ic_mean === 'number' ? payload.test_metrics.rank_ic_mean.toFixed(3) : '—'}。
          当前验证表现较弱，仅用于研究候选排序。
        </p>
      ) : null}
      <div className="prediction-horizon-grid">
        {horizons.map((horizon) => {
          const rows = payload?.horizon_rankings?.[horizon]?.slice(0, 10) ?? [];
          return (
            <div className="card horizon-card" key={horizon}>
              <div className="artifact-card__topline">
                <strong>{horizonLabel(horizon)}</strong>
                <span className="muted">截面：{payload?.latest_trade_date_by_horizon?.[horizon] ?? '加载中'}</span>
              </div>
              <div className="responsive-table-shell" role="region" aria-label={`${horizonLabel(horizon)}相对涨跌排行，可横向滚动`} tabIndex={0}>
                <table className="mini-score-table">
                  <caption className="sr-only">{horizonLabel(horizon)}相对涨跌回归值前十名</caption>
                  <thead>
                    <tr><th>排名</th><th>股票代码</th><th>股票名称</th><th>预测相对涨跌</th>{usesSentiment ? <th>融合情绪</th> : null}</tr>
                  </thead>
                  <tbody>
                    {rows.length ? rows.map((row) => (
                      <tr key={`${horizon}-${row.trade_date}-${row.symbol}`}>
                        <td>#{row.rank ?? '—'}</td>
                        <td><a className="code-link" href={`/stocks/${row.symbol}?from=scores`}>{row.symbol}</a></td>
                        <td>{row.stock_name ?? '—'}</td>
                        <td className={typeof row.predicted_relative_change_pct === 'number' && row.predicted_relative_change_pct < 0 ? 'negative' : 'positive'}>{formatRelativeChange(row.predicted_relative_change_pct)}</td>
                        {usesSentiment ? <td>{formatScore(row.sentiment_score)}</td> : null}
                      </tr>
                    )) : <tr><td colSpan={usesSentiment ? 5 : 4}>等待评分数据</td></tr>}
                  </tbody>
                </table>
              </div>
            </div>
          );
        })}
      </div>

      <section className="card candidate-pool-panel" id="candidate-pool">
        <div className="artifact-card__topline">
          <div>
            <span className="badge">研究候选</span>
            <h3>研究候选池 Top{normalizedCandidateLimit}</h3>
          </div>
          <span className="status-pill">基于{horizonLabel(candidateSourceHorizon)}</span>
        </div>
        <div className="candidate-controls" aria-label="候选池筛选">
          <label>
            <span>选择周期</span>
            <select className="candidate-horizon-select" value={candidateSourceHorizon} onChange={(event) => setSelectedCandidateHorizon(event.target.value)}>
              {horizons.map((horizon) => <option key={horizon} value={horizon}>{horizonLabel(horizon)}</option>)}
            </select>
          </label>
          <label>
            <span>Top数量</span>
            <input
              className="candidate-limit-input"
              type="number"
              min={1}
              max={Math.max(candidateSourceRows.length, 1)}
              step={1}
              value={selectedCandidateLimit}
              onChange={(event) => setSelectedCandidateLimit(Math.max(1, Math.floor(Number(event.target.value) || 1)))}
            />
          </label>
        </div>
        <div className="responsive-table-shell" role="region" aria-label="研究候选池，可横向滚动" tabIndex={0}>
          <table className="mini-score-table candidate-pool-table">
            <caption className="sr-only">研究候选池及入选理由</caption>
            <thead>
              <tr><th>候选排名</th><th>股票</th><th>行业</th><th>预测相对涨跌</th><th>score</th><th>研究说明</th><th>下一步</th></tr>
            </thead>
            <tbody>
              {candidatePool.length ? candidatePool.map((row) => {
                const metadata = candidateMetadataBySymbol.get(row.symbol);
                return (
                <tr key={`candidate-${row.trade_date}-${row.symbol}`}>
                  <td>#{row.rank ?? '—'}</td>
                  <td><a className="candidate-stock-link" href={`/stocks/${row.symbol}?from=scores`}><strong>{row.stock_name ?? row.symbol}</strong><span>{row.symbol}</span></a></td>
                  <td>{displayIndustry(row.industry_name)}</td>
                  <td>{formatRelativeChange(row.predicted_relative_change_pct)}</td>
                  <td>{formatScore(row.score)}</td>
                  <td className="candidate-reason"><span>{row.candidate_reason ?? metadata?.candidate_reason ?? '模型排名靠前，等待人工复核。'}</span><small>{row.review_action ?? metadata?.review_action ?? '查看个股详情并复核整体回测风险。'}</small></td>
                  <td><span className="candidate-actions"><a className="button table-button" href={`/stocks/${row.symbol}?from=scores`}>查看个股</a><a className="button table-button button--secondary" href="/backtests">看回测风险（整体）</a></span></td>
                </tr>
              );}) : <tr><td colSpan={7}>等待候选池数据</td></tr>}
            </tbody>
          </table>
        </div>
        <p className="muted">候选池来自当前选择的 {payload?.model_family ?? selectedModelOption?.label ?? '预测模型'}；输入截面为 {payload?.latest_trade_date ?? '—'}，目标日为 {payload?.prediction_target_date ?? '下一交易日'}。模型样本外效果尚弱，不代表投资建议。</p>
      </section>
    </div>
  );
}
