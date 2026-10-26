"""Aggregate preserved runs and draw publication figures without selecting a seed."""
from pathlib import Path
import json
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.font_manager import FontProperties

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'reports/thesis_baseline_ablation_20260914'
FIG=OUT/'figures';FIG.mkdir(exist_ok=True)
font=FontProperties(fname=r'C:\Windows\Fonts\simsun.ttc')
plt.rcParams.update({'font.family':font.get_name(),'font.size':13,'axes.unicode_minus':False,
    'axes.spines.top':False,'axes.spines.right':False,'savefig.dpi':300,
    'axes.labelcolor':'#222222','text.color':'#222222','axes.edgecolor':'#666666'})
names={'equal_weight':'样本等权','momentum20':'20日动量','reversal5':'5日反转','Ridge':'Ridge',
       'LightGBM':'LightGBM','COGRASP':'完整COGRASP','without_graph':'去除关系图',
       'without_attention':'去除时间注意力','single_15d':'仅15日窗口','equal_scale_weights':'等权融合尺度'}
base=['equal_weight','momentum20','reversal5','Ridge','LightGBM','COGRASP']
abl=['COGRASP','without_graph','without_attention','single_15d','equal_scale_weights']
metrics=json.loads((OUT/'metrics.json').read_text(encoding='utf-8'))
df=pd.DataFrame(metrics)
assert set(df.model)==set(names) and len(df)==22, (len(df),df.model.unique())
summary={}
for model, group in df.groupby('model'):
    summary[model]={'runs':len(group)}
    for c in ['mae','mse','ic_mean','rank_ic_mean','top20_label_return_pct','net_return_pct','max_drawdown_pct','average_two_sided_turnover_pct']:
        a=group[c].dropna().to_numpy(float)
        summary[model][c]={'mean':float(a.mean()),'std':float(a.std(ddof=1)) if len(a)>1 else 0.} if len(a) else None
    if model in ['equal_weight','momentum20','reversal5']:
        summary[model]['mae']=summary[model]['mse']=None
(OUT/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
daily=pd.DataFrame(json.loads((OUT/'daily_equity.json').read_text(encoding='utf-8')))
daily['date']=pd.to_datetime(daily.date)
ric=pd.DataFrame(json.loads((OUT/'daily_rankic.json').read_text(encoding='utf-8')))

def save(fig,name):
    fig.savefig(FIG/(name+'.png'),facecolor='white',bbox_inches='tight')
    fig.savefig(FIG/(name+'.svg'),facecolor='white',bbox_inches='tight')
    plt.close(fig)

# Zero-centred bars, raw seed points and standard deviation, no truncated axis.
models=base[1:]
fig,axes=plt.subplots(1,2,figsize=(8.2,3.4),gridspec_kw={'width_ratios':[1.5,1]})
for i,model in enumerate(models):
    a=df[df.model.eq(model)].rank_ic_mean.to_numpy(float)
    axes[0].barh(i,a.mean(),height=.55,color='#A6453D' if model=='COGRASP' else '#447B9C',alpha=.88)
    if len(a)>1:
        axes[0].errorbar(a.mean(),i,xerr=a.std(ddof=1),color='#222',capsize=3,fmt='none')
        axes[0].scatter(a,np.full(len(a),i),s=18,color='#222',zorder=4)
axes[0].set_yticks(range(len(models)),[names[m] for m in models]);axes[0].invert_yaxis()
axes[0].axvline(0,color='#777',lw=.8);axes[0].set_xlabel('平均RankIC');axes[0].grid(axis='x',alpha=.18)
for i,model in enumerate(['Ridge','LightGBM','COGRASP']):
    a=df[df.model.eq(model)].mae.to_numpy(float)
    axes[1].bar(i,a.mean(),width=.55,color='#A6453D' if model=='COGRASP' else '#447B9C',alpha=.88)
    axes[1].errorbar(i,a.mean(),yerr=a.std(ddof=1) if len(a)>1 else 0,color='#222',capsize=3,fmt='none')
    axes[1].text(i,a.mean()+.07,f'{a.mean():.3f}',ha='center',fontsize=10)
axes[1].set_xticks([0,1,2],['Ridge','LightGBM','COGRASP']);axes[1].set_ylabel('MAE（百分点）')
axes[1].set_ylim(0,3);axes[1].grid(axis='y',alpha=.18)
fig.tight_layout(w_pad=2);save(fig,'fig_4_16_baseline_prediction')

fig,axes=plt.subplots(2,1,figsize=(8.2,5.0),sharex=True,gridspec_kw={'height_ratios':[1.55,1]})
colors={'equal_weight':'#777777','momentum20':'#B58C2D','reversal5':'#579665','Ridge':'#8065A2','LightGBM':'#397AA4','COGRASP':'#B3483D'}
for m in base:
    tab=daily[daily.model.eq(m)].pivot(index='date',columns='seed',values='nav').sort_index()
    start=pd.DataFrame(np.ones((1,tab.shape[1])),index=[tab.index.min()-pd.Timedelta(hours=1)],columns=tab.columns)
    tab=pd.concat([start,tab])
    vals=tab.mean(axis=1)
    axes[0].plot(tab.index,vals,color=colors[m],lw=2.2 if m=='COGRASP' else 1.5,label=names[m])
    dd=(tab/tab.cummax()-1)*100
    axes[1].plot(tab.index,dd.mean(axis=1),color=colors[m],lw=2.2 if m=='COGRASP' else 1.5)
    if m=='COGRASP':
        axes[0].fill_between(tab.index,tab.min(axis=1),tab.max(axis=1),alpha=.13,color=colors[m])
        axes[1].fill_between(tab.index,dd.min(axis=1),dd.max(axis=1),alpha=.13,color=colors[m])
axes[0].set_ylabel('扣费净值');axes[0].legend(ncol=3,loc='lower left',frameon=False,fontsize=10)
axes[1].set_ylabel('回撤（%）');axes[1].xaxis.set_major_formatter(mdates.DateFormatter('%m-%d'))
axes[1].set_xlabel('2026年交易日期')
for ax in axes:ax.grid(alpha=.18)
fig.tight_layout();save(fig,'fig_4_17_baseline_backtest')

fig,axes=plt.subplots(1,2,figsize=(8.2,3.7),gridspec_kw={'width_ratios':[1.1,1]})
for i,m in enumerate(abl):
    g=df[df.model.eq(m)]
    for ax,c in zip(axes,['rank_ic_mean','net_return_pct']):
        a=g[c].to_numpy(float)
        ax.barh(i,a.mean(),height=.55,color='#A6453D' if m=='COGRASP' else '#6C8C9D',alpha=.88)
        ax.errorbar(a.mean(),i,xerr=a.std(ddof=1),color='#222',capsize=3,fmt='none')
        ax.scatter(a,np.full(len(a),i),s=18,color='#222',zorder=4)
for ax in axes:
    ax.set_yticks(range(len(abl)),[names[m] for m in abl]);ax.invert_yaxis()
    ax.axvline(0,color='#777',lw=.8);ax.grid(axis='x',alpha=.18)
axes[0].set_xlabel('平均RankIC');axes[1].set_xlabel('累计净收益（%）')
axes[1].set_yticklabels([])
fig.tight_layout(w_pad=2);save(fig,'fig_4_18_ablation')

# Paired circular block bootstrap across dates, using the mean of seed-level ICs.
# This is descriptive uncertainty for the existing short window, not a fresh test.
tables={m:ric[ric.model.eq(m)].pivot(index='date',columns='seed',values='rank_ic').mean(axis=1) for m in names if m!='equal_weight'}
rng=np.random.default_rng(20260914);N=len(tables['COGRASP']);B=5000;L=5
idx=((rng.integers(0,N,size=(B,int(np.ceil(N/L)),1))+np.arange(L))%N).reshape(B,-1)[:,:N]
ci={}
for m in ['LightGBM','without_graph','without_attention','single_15d','equal_scale_weights']:
    a=(tables['COGRASP']-tables[m]).to_numpy(float)
    samples=a[idx].mean(axis=1)
    ci[m]={'delta_mean':float(a.mean()),'low95':float(np.quantile(samples,.025)),'high95':float(np.quantile(samples,.975))}
(OUT/'paired_rankic_intervals.json').write_text(json.dumps(ci,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(summary,ensure_ascii=False,indent=2))
print('PAIRED_INTERVALS',json.dumps(ci,ensure_ascii=False))
