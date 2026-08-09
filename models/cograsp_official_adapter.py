from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType
from typing import Any

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
UPSTREAM_DIR = ROOT / "third_party" / "COGRASP"
UPSTREAM_MODEL = UPSTREAM_DIR / "model.py"
UPSTREAM_DATALOADER = UPSTREAM_DIR / "dataloader.py"
UPSTREAM_CHECKPOINT = UPSTREAM_DIR / "checkpoint.pt"
UPSTREAM_GRAPH = UPSTREAM_DIR / "data" / "stock_matrix.csv"
UPSTREAM_CODES = UPSTREAM_DIR / "data" / "code.csv"

UPSTREAM_URL = "https://github.com/NingboSong/COGRASP"
UPSTREAM_COMMIT = "34e31f856ac396fa5ecea1f4410fe6c7d0bd5851"
MODEL_FAMILY = "COGRASP (IJCAI 2025 official)"
MODEL_FAMILY_ZH = "COGRASP（IJCAI 2025 作者原版）"
MODEL_VERSION = f"cograsp-official-{UPSTREAM_COMMIT[:12]}"
LOOKBACK_WINDOW = 15
FEATURE_COLUMNS = [
    "open",
    "close",
    "high",
    "low",
    "amount",
    "volume",
    "amplitude",
    "momentum",
    "momentum_volume",
    "turnover",
]


def _load_module(module_name: str, path: Path) -> ModuleType:
    if not path.exists():
        raise FileNotFoundError(
            f"Missing official COGRASP source at {path}; run: git submodule update --init --recursive"
        )
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Unable to import official COGRASP module from {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def official_universe() -> pd.DataFrame:
    if not UPSTREAM_CODES.exists():
        raise FileNotFoundError(
            "COGRASP submodule is missing; run: git submodule update --init --recursive"
        )
    frame = pd.read_csv(UPSTREAM_CODES, dtype={"Code": str})
    frame["Code"] = frame["Code"].str.zfill(6)
    frame["symbol"] = frame["Code"].map(
        lambda code: f"{code}.SH" if code.startswith(("5", "6", "9")) else f"{code}.SZ"
    )
    if len(frame) != 300 or frame["Code"].nunique() != 300:
        raise ValueError("Official COGRASP universe must contain exactly 300 unique codes")
    return frame


def prepare_official_sequence(market: pd.DataFrame) -> tuple[np.ndarray, list[str], dict[str, Any]]:
    required = {"trade_date", "symbol", "open", "close", "high", "low", "amount", "volume", "turnover_rate"}
    missing = sorted(required - set(market.columns))
    if missing:
        raise KeyError(f"COGRASP market input is missing columns: {missing}")

    universe = official_universe()
    codes = universe["Code"].tolist()
    frame = market.copy()
    frame["code"] = frame["symbol"].astype(str).str[:6].str.zfill(6)
    frame = frame[frame["code"].isin(codes)].copy()
    frame["trade_date"] = pd.to_datetime(frame["trade_date"]).dt.strftime("%Y-%m-%d")
    for column in ["open", "close", "high", "low", "amount", "volume", "turnover_rate"]:
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    frame = frame.sort_values(["code", "trade_date"]).drop_duplicates(
        ["code", "trade_date"], keep="last"
    )
    grouped = frame.groupby("code", sort=False)
    previous_close = grouped["close"].shift(1)
    frame["amplitude"] = (frame["high"] - frame["low"]) / previous_close * 100.0
    frame["momentum"] = (frame["close"] - previous_close) / previous_close * 100.0
    frame["momentum_volume"] = frame["close"] - previous_close
    frame["turnover"] = frame["turnover_rate"]
    frame[FEATURE_COLUMNS] = frame[FEATURE_COLUMNS].replace([np.inf, -np.inf], np.nan)

    complete = frame.dropna(subset=FEATURE_COLUMNS)
    counts = complete.groupby("trade_date")["code"].nunique()
    valid_dates = counts[counts.eq(len(codes))].index.astype(str).tolist()
    if len(valid_dates) < LOOKBACK_WINDOW:
        raise ValueError(
            f"COGRASP needs {LOOKBACK_WINDOW} complete dates for all 300 official nodes; "
            f"available={len(valid_dates)}"
        )
    selected_dates = valid_dates[-LOOKBACK_WINDOW:]
    selected = complete[complete["trade_date"].isin(selected_dates)].copy()
    selected["code"] = pd.Categorical(selected["code"], categories=codes, ordered=True)
    selected["trade_date"] = pd.Categorical(
        selected["trade_date"], categories=selected_dates, ordered=True
    )
    selected = selected.sort_values(["code", "trade_date"])
    expected_rows = len(codes) * LOOKBACK_WINDOW
    if len(selected) != expected_rows:
        raise ValueError(f"Unexpected COGRASP sequence size: {len(selected)} != {expected_rows}")
    sequence = selected[FEATURE_COLUMNS].to_numpy(dtype=np.float32).reshape(
        1, len(codes), LOOKBACK_WINDOW, len(FEATURE_COLUMNS)
    )
    metadata = {
        "latest_input_date": selected_dates[-1],
        "input_dates": selected_dates,
        "stock_count": len(codes),
        "lookback_window": LOOKBACK_WINDOW,
        "feature_columns": FEATURE_COLUMNS,
        "feature_definition": {
            "amplitude": "(high-low)/previous_close*100",
            "momentum": "(close-previous_close)/previous_close*100",
            "momentum_volume": "close-previous_close (AKShare price-change amount)",
            "turnover": "turnover_rate",
        },
    }
    return sequence, codes, metadata


def predict_official_cograsp(market: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, Any]]:
    try:
        import torch
    except ImportError as exc:
        raise RuntimeError("Install COGRASP dependencies with: uv sync --extra cograsp") from exc

    model_module = _load_module("cograsp_official_model", UPSTREAM_MODEL)
    dataloader_module = _load_module("cograsp_official_dataloader", UPSTREAM_DATALOADER)
    sequence, codes, input_metadata = prepare_official_sequence(market)

    model = model_module.COGRASP(
        features=10,
        gnn_hidden_dim=10,
        lstm_hidden_dim=64,
        gnn_num_layers=1,
        lstm_num_layers=1,
    )
    state_dict = torch.load(
        UPSTREAM_CHECKPOINT,
        map_location="cpu",
        weights_only=True,
    )
    model.load_state_dict(state_dict, strict=True)
    edge_index, edge_weight = dataloader_module.load_graph_data(str(UPSTREAM_GRAPH))
    graph_data = (torch.ones((300, 10)), edge_index, edge_weight)
    sequence_tensor = torch.from_numpy(sequence)
    model.eval()
    with torch.inference_mode():
        raw_prediction = model(graph_data, sequence_tensor).squeeze(0).cpu().numpy()

    if raw_prediction.shape != (300,) or not np.isfinite(raw_prediction).all():
        raise ValueError(f"Invalid official COGRASP output shape or values: {raw_prediction.shape}")
    universe = official_universe().set_index("Code")
    predictions = pd.DataFrame(
        {
            "code": codes,
            "predicted_relative_change_pct": raw_prediction.astype(float),
        }
    )
    predictions["symbol"] = universe.loc[codes, "symbol"].to_numpy()
    predictions["stock_name"] = universe.loc[codes, "Name"].to_numpy()
    predictions["predicted_relative_change"] = (
        predictions["predicted_relative_change_pct"] / 100.0
    )
    predictions["score"] = predictions["predicted_relative_change_pct"]
    predictions["rank"] = predictions["score"].rank(ascending=False, method="first").astype(int)
    predictions["percentile"] = predictions["score"].rank(pct=True)
    predictions = predictions.sort_values(["rank", "symbol"]).reset_index(drop=True)

    metadata = {
        **input_metadata,
        "model_family": MODEL_FAMILY,
        "model_version": MODEL_VERSION,
        "upstream_url": UPSTREAM_URL,
        "upstream_commit": UPSTREAM_COMMIT,
        "license": "MIT",
        "checkpoint": str(UPSTREAM_CHECKPOINT.relative_to(ROOT)).replace("\\", "/"),
        "graph": str(UPSTREAM_GRAPH.relative_to(ROOT)).replace("\\", "/"),
        "output_semantics": "next-trading-day relative price change; raw official regression output",
        "online_information_semantics": (
            "official Xueqiu/social-news co-occurrence attention graph; "
            "it does not classify positive/negative sentiment polarity"
        ),
        "algorithm_modified": False,
    }
    return predictions, metadata
