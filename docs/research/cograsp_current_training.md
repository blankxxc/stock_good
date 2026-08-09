# Current-CSI300 COGRASP training

The website prediction page uses the unmodified COGRASP network architecture from the IJCAI 2025
authors' repository at commit `34e31f856ac396fa5ecea1f4410fe6c7d0bd5851`. The local data and
relationship graph are adapted so the model can cover the current 300-stock universe.

## Run

```powershell
git submodule update --init --recursive
uv sync --extra cograsp
uv run --extra cograsp python scripts\train_cograsp_current.py
uv run --extra cograsp python scripts\build_latest_live_scores.py
```

The upstream `forward` implementation fixes graph features to one batch, so `batch-size=1` is
required. Training is CPU-compatible and applies chronological train/validation/test selection,
then retrains a final checkpoint on all labels through the latest complete market date.

## Data semantics

- Inputs use the author's 10 features and 15-day maximum lookback.
- A missing or suspended stock-day carries the prior close; volume, amount and turnover are zero.
- Features and the target are z-scored using statistics from the applicable training split.
- The current local news cache does not cover the universe. The static graph therefore connects
  each stock to its Top8 peers by absolute daily-return correlation. It is not a text-sentiment
  graph and does not express positive or negative sentiment polarity.
- The page shows raw next-day relative-change regression outputs and cross-sectional ranks, not
  calibrated probabilities or investment advice.

Artifacts are written below `models/checkpoints/cograsp_current_csi300/`. The generated website
score table and report are written to `reports/research_loop/live_predictions.parquet` and
`reports/research_loop/live_predictions_report.json`.

The current local run uses 139 supervised dates through 2026-07-24. Its held-out metrics are weak
(MAE 2.599 percentage points and mean RankIC -0.124), so the output should only be treated as an
experimental research ranking until more history and stronger validation are available.
