"""Focused checks for the thesis's timing, ledger and frozen source artifacts."""
from pathlib import Path
import hashlib,json
import numpy as np
import pandas as pd
from thesis_baseline_ablation import ROOT,OUT,portfolio

protocol=json.loads((OUT/'protocol.json').read_text(encoding='utf-8'))
for path,digest in protocol['source_sha256'].items():
    assert hashlib.sha256((ROOT/path).read_bytes()).hexdigest()==digest,path
assert protocol['train'][1]<protocol['validation'][0]<=protocol['validation'][1]<protocol['test'][0]
assert protocol['train_cutoff_graph']==protocol['train'][1]
target=np.load(OUT/'test_targets.npz')
assert target['targets'].shape==(21,300)
metrics=json.loads((OUT/'metrics.json').read_text(encoding='utf-8'))
assert len(metrics)==22
assert len({(r['model'],r['seed']) for r in metrics})==22
for r in metrics:
    p=np.load(OUT/f"predictions_{r['model']}_{r['seed']}.npy")
    assert p.shape==(21,300) and np.isfinite(p).all()
    assert r['holding_intervals']==20
history=json.loads((OUT/'training_history.json').read_text(encoding='utf-8'))
assert len(history)==15
for name,rows in history.items():
    r=next(m for m in metrics if f"{m['model']}_{m['seed']}"==name)
    best=min(rows,key=lambda x:x['validation_mse_pct2'])
    assert r['best_epoch']==int(best['epoch'])

# Flat prices isolate entry/exit fees, including full liquidation.
p=np.ones((2,30))*10;v=np.ones_like(p);s=np.tile(np.arange(30),(2,1))
rows,m=portfolio(s,p,v,['2026-01-05','2026-01-06'],cost=.001)
expected=(1-.001)/(1+.001)
assert abs(rows[-1]['nav']-expected)<1e-12
assert rows[-1]['holdings']==0
# Later prices cannot affect the earlier order or NAV.
p2=p.copy();p2[1]*=1.1
rows2,_=portfolio(s,p2,v,['2026-01-05','2026-01-06'],cost=.001)
assert rows[0]==rows2[0]
# A blocked top-ranked purchase stays cash and does not trigger replacement.
v[0,-1]=0
blocked,bm=portfolio(s,p,v,['2026-01-05','2026-01-06'],cost=0)
assert blocked[0]['holdings']==19 and bm['skipped_buy_count']==1
assert abs(blocked[0]['cash']-.05)<1e-12
original=json.loads((ROOT/'models/checkpoints/cograsp_current_csi300/metadata.json').read_text(encoding='utf-8'))
ours=next(r for r in metrics if r['model']=='COGRASP' and r['seed']==42)
differences={k:abs(ours[k]-original['test_metrics'][k]) for k in ('mae','mse','ic_mean','rank_ic_mean')}
assert max(differences.values())<1e-4,differences
record={'passed':True,'runs':len(metrics),'neural_runs':len(history),
    'source_hashes_unchanged':True,'original_seed42_max_metric_difference':max(differences.values()),
    'ledger_checks':['flat prices yield exact entry-exit fees','future prices do not change prior NAV',
                     'zero-volume buy skipped without replacement','nonnegative cash and holdings checked every rebalance'],
    'original_production_checkpoint_unchanged':hashlib.sha256((ROOT/original['checkpoint']).read_bytes()).hexdigest()==original['checkpoint_sha256']}
assert record['original_production_checkpoint_unchanged']
(OUT/'validation.json').write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(record,ensure_ascii=False,indent=2))
