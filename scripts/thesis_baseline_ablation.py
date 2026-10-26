"""Reproduce the current COGRASP temporal split and compare honest held-out results.

Run with the project's Python environment. No production artifacts are overwritten.
Predictions use only data preceding their target date. Portfolio orders execute at
the target day's open; positions are valued/sold at subsequent opens (T+1).
"""
from __future__ import annotations

import copy
import hashlib
import json
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

import numpy as np
import pandas as pd
import torch
from lightgbm import LGBMRegressor
from sklearn.linear_model import Ridge
from torch import nn

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from models import cograsp_current as core

OUT = ROOT / 'reports' / 'thesis_baseline_ablation_20260914'
SEEDS = [42, 43, 44]
VARIANTS = ['COGRASP', 'without_graph', 'without_attention', 'single_15d', 'equal_scale_weights']
MAX_EPOCHS = 60
PATIENCE = 12


def train_worker(payload):
    name, seed, features, targets, tr, va, scaler, adj = payload
    torch.set_num_threads(1)
    torch.manual_seed(seed); np.random.seed(seed)
    graph = core._graph_tensors(torch, adj)
    model = Variant(name)
    if name == 'COGRASP':
        z = torch.from_numpy(core._scale_features(features[:1], scaler))
        with torch.no_grad():
            assert torch.allclose(model(graph, z), model.base(graph, z), atol=1e-7)
    start = time.perf_counter()
    def log(msg):
        print(f'{name} seed={seed} {msg}', flush=True)
    model, history, epoch = core._fit_model(
        torch, model, graph, features[:tr], targets[:tr], scaler,
        epochs=MAX_EPOCHS, batch_size=1, learning_rate=.001, weight_decay=.0001,
        validation_features=features[tr:va], validation_targets=targets[tr:va],
        patience=PATIENCE, log=log)
    pred = core._predict_array(torch, model, graph, features[va:], scaler, batch_size=1)
    torch.save(model.state_dict(), OUT/f'{name}_{seed}.pt')
    return name, seed, pred, history, {'best_epoch': epoch, 'epochs_ran': len(history),
        'runtime_seconds': time.perf_counter()-start,
        'trainable_parameters': sum(p.numel() for p in model.parameters() if p.requires_grad)}


def dump(name, obj):
    (OUT / name).write_text(json.dumps(obj, ensure_ascii=False, indent=2, allow_nan=False), encoding='utf-8')


class MeanAttention(nn.Module):
    def forward(self, h):
        return h.mean(dim=1), torch.ones_like(h[:, :, :1]) / h.shape[1]


class Variant(nn.Module):
    def __init__(self, name):
        super().__init__()
        self.name = name
        self.base = core._new_model(torch)
        if name == 'without_attention':
            for branch in self.branches():
                branch.attention = MeanAttention()
        if name == 'equal_scale_weights':
            self.base.M_ALSTM_S.weights.requires_grad_(False)
        if name == 'without_graph':
            self.base.gnn.requires_grad_(False)
        if name == 'single_15d':
            self.base.M_ALSTM_S.alstm_1.requires_grad_(False)
            self.base.M_ALSTM_S.alstm_2.requires_grad_(False)
            self.base.M_ALSTM_S.weights.requires_grad_(False)

    def branches(self):
        m = self.base.M_ALSTM_S
        return [m.alstm_1, m.alstm_2, m.alstm_3]

    def forward(self, graph, x):
        if self.name == 'without_graph':
            g = torch.zeros((1, x.shape[1], x.shape[2], 10), dtype=x.dtype)
        else:
            g = self.base.gnn(*graph).unsqueeze(0).unsqueeze(2).repeat(1, 1, x.shape[2], 1)
        combined = torch.cat([x, g], dim=-1)
        if self.name == 'single_15d':
            return self.base.M_ALSTM_S.alstm_3(combined)
        return self.base.M_ALSTM_S(combined)


def rankic_by_day(pred, truth):
    vals = []
    for p, y in zip(pred, truth):
        if np.std(p) < 1e-12 or np.std(y) < 1e-12:
            vals.append(np.nan)
        else:
            vals.append(pd.Series(p).corr(pd.Series(y), method='spearman'))
    return np.array(vals)


def prediction_metrics(pred, truth):
    m = core._prediction_metrics(pred, truth)
    rankic = rankic_by_day(pred, truth)
    indices = np.argsort(-pred, axis=1, kind='stable')[:, :20]
    m['top20_label_return_pct'] = float(np.take_along_axis(truth, indices, axis=1).mean())
    m['rankic_positive_day_rate'] = float(np.mean(rankic > 0))
    return m


def portfolio(scores, opens, volumes, dates, cost=0.001, equal_weight=False):
    """Daily open rebalancing, proportional costs, no borrowing or shorting.

    Frozen positions cannot trade on days with zero reported volume. Sell unwanted
    holdings first, then scale purchases to cash after fees. Last date liquidates
    tradable holdings; frozen holdings, if any, retain open-price marked value.
    """
    shares = np.zeros(opens.shape[1], dtype=float)
    cash = 1.0
    rows = []
    previous = 1.0
    skips = 0
    for i, day in enumerate(dates):
        price = opens[i]
        tradable = (volumes[i] > 0) & np.isfinite(price) & (price > 0)
        assert np.all(np.isfinite(price) & (price > 0)), 'Invalid valuation open'
        value = shares * price
        wealth = float(cash + value.sum())
        # Last available open closes the experiment, without a new signal trade.
        selected = np.array([], dtype=int) if i == len(dates)-1 else (
            np.arange(len(price)) if equal_weight else np.argsort(-scores[i], kind='stable')[:20]
        )
        goal = np.zeros_like(value)
        if len(selected):
            goal[selected] = wealth / len(selected)
            skips += int((~tradable[selected]).sum())
        sell_value = np.where(tradable, np.maximum(value - goal, 0), 0)
        shares -= sell_value / price
        cash += float(sell_value.sum() * (1 - cost))
        buy_requested = np.where(tradable, np.maximum(goal - shares * price, 0), 0)
        scale = min(1.0, cash / (float(buy_requested.sum()) * (1 + cost))) if buy_requested.sum() else 0
        buy_value = buy_requested * scale
        shares += buy_value / price
        cash -= float(buy_value.sum() * (1 + cost))
        fee = float((buy_value.sum() + sell_value.sum()) * cost)
        nav = float(cash + (shares * price).sum())
        assert cash > -1e-8 and shares.min() > -1e-10
        assert abs(nav - (wealth - fee)) < 1e-9
        rows.append({'date': day, 'nav': nav, 'net_return': nav / previous - 1,
                     'traded_fraction': float((buy_value.sum() + sell_value.sum()) / wealth),
                     'fee': fee, 'cash': cash, 'holdings': int((shares > 1e-10).sum())})
        previous = nav
    nav = np.array([1.0] + [r['nav'] for r in rows])
    dd = nav / np.maximum.accumulate(nav) - 1
    # There are D-1 actual holding intervals. Fold initial entry cost into interval 1.
    holding_returns = np.diff(nav[1:]) / nav[1:-1]
    holding_returns[0] = nav[2] - 1
    return rows, {'net_return_pct': float((nav[-1]-1)*100),
                  'max_drawdown_pct': float(-dd.min()*100),
                  'average_two_sided_turnover_pct': float(np.mean([r['traded_fraction'] for r in rows[:-1]])*100),
                  'skipped_buy_count': skips, 'fee_total_initial_nav': float(sum(r['fee'] for r in rows)),
                  'holding_intervals': len(dates)-1}


def main():
    OUT.mkdir(exist_ok=True, parents=True)
    torch.set_num_threads(1)
    market = pd.read_parquet(core.CURRENT_DAILY)
    dataset = core.prepare_current_dataset(market)
    n = len(dataset.target_dates)
    nt = max(8, round(n*.15)); nv = max(8, round(n*.15)); tr = n-nt-nv; va = tr+nv
    scaler = core._fit_scaler(dataset.features[:tr], dataset.targets[:tr])
    symbols = dataset.universe.symbol.tolist()
    adj = core.build_correlation_graph(dataset.feature_frame, symbols, end_date=dataset.target_dates[tr-1])
    graph = core._graph_tensors(torch, adj)
    truth = dataset.targets[va:]
    dates = dataset.target_dates[va:]
    pivot = lambda col: dataset.feature_frame.pivot(index='trade_date', columns='symbol', values=col).reindex(columns=symbols)
    opens = pivot('open').loc[dates].to_numpy(float)
    volumes = pivot('volume').loc[dates].to_numpy(float)
    close = pivot('close')
    signal_dates = [dataset.valid_dates[dataset.valid_dates.index(d)-1] for d in dates]
    assert dataset.target_dates[tr-1] < dataset.target_dates[tr] < dates[0]
    source_paths = [core.CURRENT_DAILY, Path(core.__file__), core.UPSTREAM_MODEL, Path(__file__)]
    protocol = {'created_at': pd.Timestamp.now(tz='UTC').isoformat(), 'seeds': SEEDS,
        'raw_rows': len(market), 'stocks': len(symbols), 'supervised_dates': n,
        'train': [dataset.target_dates[0], dataset.target_dates[tr-1],tr],
        'validation': [dataset.target_dates[tr], dataset.target_dates[va-1],nv],
        'test': [dates[0], dates[-1],nt], 'train_cutoff_graph':dataset.target_dates[tr-1],
        'features':core.FEATURE_COLUMNS, 'lookback':15, 'target':'next day close-to-close return in percentage points',
        'training': {'epochs_max':MAX_EPOCHS,'patience':PATIENCE,'lr':0.001,'weight_decay':0.0001,'batch_size':1,
                     'selection':'minimum validation MSE; no test selection','loader_seed':42,'threads':1},
        'portfolio':{'start':dates[0]+' open','end':dates[-1]+' open','holding_intervals':len(dates)-1,
                     'top_k':20,'frequency':'daily','one_sided_cost':0.001,'entry_exit_costs':True,
                     'execution':'preceding close signal -> next open order; no same day resale',
                     'zero_volume':'cannot trade; no replacement of blocked top20 buys',
                     'missing_constraints':['historical membership','ST and limit-up/down execution queues','round lots','market impact']},
        'source_sha256':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in source_paths},
        'upstream_commit':core.UPSTREAM_COMMIT, 'python':sys.version, 'torch':torch.__version__}
    dump('protocol.json', protocol)
    np.savez_compressed(OUT/'test_targets.npz',targets=truth, dates=np.array(dates), symbols=np.array(symbols))
    all_metrics=[]; all_daily=[]; all_ic=[]; all_history={}

    def record(name, seed, pred, more=None, equal=False):
        assert pred.shape == truth.shape and np.isfinite(pred).all()
        np.save(OUT/f'predictions_{name}_{seed}.npy', pred)
        metrics = prediction_metrics(pred, truth)
        daily, pm = portfolio(pred,opens,volumes,dates,equal_weight=equal)
        metrics.update(pm)
        metrics.update({'model':name,'seed':seed,**(more or {})})
        if equal:
            for k in ('mse','mae','ic_mean','rank_ic_mean','top20_label_return_pct','rankic_positive_day_rate'):
                metrics[k]=None
        all_metrics.append(metrics)
        all_daily.extend({'model':name,'seed':seed,**row} for row in daily)
        for day,v in zip(dates, rankic_by_day(pred,truth)):
            all_ic.append({'model':name,'seed':seed,'date':day,'rank_ic':float(v) if np.isfinite(v) else None})
        dump('metrics.json',all_metrics)
        dump('daily_equity.json',all_daily)
        dump('daily_rankic.json',all_ic)
        print(json.dumps(metrics,ensure_ascii=False),flush=True)

    record('equal_weight',0,np.zeros_like(truth),equal=True)
    record('momentum20',0,(close/close.shift(20)-1).loc[signal_dates].to_numpy(float))
    record('reversal5',0,-(close/close.shift(5)-1).loc[signal_dates].to_numpy(float))
    X=core._scale_features(dataset.features,scaler).reshape(n*300,-1)
    Y=dataset.targets.reshape(-1)
    ridge=Ridge(alpha=1.0).fit(X[:tr*300],Y[:tr*300])
    record('Ridge',0,ridge.predict(X[va*300:]).reshape(nt,300),{'alpha':1.0})
    for seed in SEEDS:
        model=LGBMRegressor(objective='regression',n_estimators=20,learning_rate=.05,num_leaves=15,
                            random_state=seed,n_jobs=1,verbosity=-1)
        model.fit(X[:tr*300],Y[:tr*300])
        record('LightGBM',seed,model.predict(X[va*300:]).reshape(nt,300))
    saved_history = json.loads((OUT/'training_history.json').read_text(encoding='utf-8')) if (OUT/'training_history.json').exists() else {}
    jobs = []
    for name in VARIANTS:
        for seed in SEEDS:
            key = f'{name}_{seed}'
            cached = OUT/f'predictions_{key}.npy'
            if cached.exists() and key in saved_history:
                history = saved_history[key]
                epoch = min(history, key=lambda r:r['validation_mse_pct2'])['epoch']
                record(name,seed,np.load(cached),{'best_epoch':int(epoch),'epochs_ran':len(history),'resumed':True})
                all_history[key] = history
            else:
                jobs.append((name,seed,dataset.features,dataset.targets,tr,va,scaler,adj))
    with ProcessPoolExecutor(max_workers=3) as pool:
        futures = [pool.submit(train_worker, job) for job in jobs]
        for future in as_completed(futures):
            name,seed,pred,history,more = future.result()
            record(name,seed,pred,more)
            all_history[f'{name}_{seed}']=history
            dump('training_history.json',all_history)
    dump('completion.json',{'complete':True,'runs':len(all_metrics)})


if __name__=='__main__':
    main()
