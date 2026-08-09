# COGRASP official-code integration

> Historical reproduction only. The website now defaults to a locally retrained current-CSI300
> checkpoint produced by `scripts/train_cograsp_current.py`; the official frozen checkpoint path
> below remains available for provenance and reproducibility.

## Provenance

- Paper: COGRASP: Co-Occurrence Graph Based Stock Price Forecasting, IJCAI 2025
- Proceedings: https://www.ijcai.org/proceedings/2025/837
- Author repository: https://github.com/NingboSong/COGRASP
- Pinned commit: `34e31f856ac396fa5ecea1f4410fe6c7d0bd5851`
- License: MIT (kept in `third_party/COGRASP/LICENSE`)

The repository is included as a Git submodule. Files inside `third_party/COGRASP` are not modified.
The website adapter imports the author's `model.py` and `dataloader.py`, loads the published
`checkpoint.pt`, and uses the published `data/stock_matrix.csv` graph.

## What is and is not changed

The COGRASP network, graph, checkpoint, layer sizes, 5/10/15-day ALSTM windows, and raw regression
output are unchanged. The website does not apply a sigmoid, probability calibration, LightGBM
fallback, node substitution, or additional sentiment expert.

The only local code is interface glue:

1. Fetch the author's fixed 300-stock universe from BaoStock/AkShare-compatible daily fields.
2. Map the paper's ten market fields to the tensor order used by the author's dataloader.
3. Convert the raw 300-value output into rows that the website can rank and display.

The paper lists open, close, high, low, volume, trading value, amplitude, price-change percentage,
price-change amount, and turnover rate. The repository uses the names `amount`, `volume`,
`amplitude`, `momentum`, `momentum_volume`, and `turnover`; the adapter preserves that order.

## Frozen-universe boundary

The published graph contains a fixed 2024 CSI300 node list. Two nodes in that graph, `600837` and
`601989`, no longer have 2026 daily bars. The official dataloader requires all 300 nodes on every
input date. To avoid changing the algorithm, replacing nodes, or forward-filling delisted stocks,
the runnable website artifact is frozen at the paper test-period end, `2024-06-28`.

The model still runs all 300 official nodes. The website displays 239 rows: the intersection between
the official graph and the site's current stock-detail universe. This is a historical reproducibility
view, not a current-day forecast.

## Online-information meaning

COGRASP builds its graph from co-mentions in Snowball posts, news, and reports. It captures investor
attention and cross-stock relations. It does not classify text into positive or negative sentiment
polarity, so the UI describes it as a co-occurrence/attention signal rather than a sentiment score.

## Run

```powershell
git submodule update --init --recursive
uv sync --extra cograsp
uv run --extra cograsp python scripts\update_cograsp_market_data.py
uv run --extra cograsp python scripts\build_latest_live_scores.py
```

The upstream requirements include packages not imported by the released model and a Triton pin that
does not support this Windows CPU environment. The `cograsp` optional dependency installs the exact
released `torch==2.2.2` and `torch-geometric==2.5.2`, plus NumPy 1.26.4 for PyTorch's NumPy 1.x ABI.
