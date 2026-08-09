from __future__ import annotations

import copy
import hashlib
import json
import math
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

import numpy as np
import pandas as pd

from models.cograsp_official_adapter import (
    FEATURE_COLUMNS,
    LOOKBACK_WINDOW,
    ROOT,
    UPSTREAM_COMMIT,
    UPSTREAM_MODEL,
    UPSTREAM_URL,
    _load_module,
)

CURRENT_DAILY = ROOT / "data" / "real" / "csi300_daily" / "part-000.parquet"
ARTIFACT_DIR = ROOT / "models" / "checkpoints" / "cograsp_current_csi300"
CHECKPOINT_PATH = ARTIFACT_DIR / "model.pt"
SCALER_PATH = ARTIFACT_DIR / "scaler.npz"
GRAPH_PATH = ARTIFACT_DIR / "graph.npy"
UNIVERSE_PATH = ARTIFACT_DIR / "universe.parquet"
METADATA_PATH = ARTIFACT_DIR / "metadata.json"

MODEL_FAMILY = "COGRASP current CSI300 retrained"
MODEL_FAMILY_ZH = "COGRASP（当前沪深300重训）"
GRAPH_METHOD = "absolute_return_correlation_top_k"
DEFAULT_TOP_K = 8


@dataclass(frozen=True)
class CurrentDataset:
    features: np.ndarray
    targets: np.ndarray
    target_dates: list[str]
    valid_dates: list[str]
    universe: pd.DataFrame
    feature_frame: pd.DataFrame


def _json_default(value: Any) -> Any:
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        number = float(value)
        return None if math.isnan(number) or math.isinf(number) else number
    if isinstance(value, (np.ndarray,)):
        return value.tolist()
    if isinstance(value, (pd.Timestamp, datetime, Path)):
        return str(value)
    return value


def _prepare_feature_frame(market: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    required = {
        "trade_date",
        "symbol",
        "stock_name",
        "open",
        "close",
        "high",
        "low",
        "amount",
        "volume",
        "turnover_rate",
    }
    missing = sorted(required - set(market.columns))
    if missing:
        raise KeyError(f"Current COGRASP market input is missing columns: {missing}")

    frame = market.copy()
    frame["trade_date"] = pd.to_datetime(frame["trade_date"]).dt.strftime("%Y-%m-%d")
    frame["symbol"] = frame["symbol"].astype(str).str.upper()
    latest_date = str(frame["trade_date"].max())
    latest = (
        frame[frame["trade_date"].eq(latest_date)]
        .sort_values("symbol")
        .drop_duplicates("symbol", keep="last")
    )
    if len(latest) != 300:
        raise ValueError(
            f"Latest CSI300 date must contain exactly 300 stocks; date={latest_date}, rows={len(latest)}"
        )
    universe_columns = ["symbol", "stock_name"]
    if "industry_name" in latest.columns:
        universe_columns.append("industry_name")
    universe = latest[universe_columns].reset_index(drop=True)
    symbols = universe["symbol"].tolist()

    frame = frame[frame["symbol"].isin(symbols)].copy()
    numeric_columns = ["open", "close", "high", "low", "amount", "volume", "turnover_rate"]
    for column in numeric_columns:
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    frame = frame.sort_values(["symbol", "trade_date"]).drop_duplicates(
        ["symbol", "trade_date"], keep="last"
    )
    first_dates = frame.dropna(subset=["close"]).groupby("symbol")["trade_date"].min()
    if len(first_dates) != len(symbols):
        raise ValueError("At least one latest-universe stock has no historical close data")
    common_start_date = str(first_dates.max())
    calendar_dates = sorted(frame["trade_date"].unique().tolist())
    full_index = pd.MultiIndex.from_product(
        [calendar_dates, symbols], names=["trade_date", "symbol"]
    )
    frame = frame.set_index(["trade_date", "symbol"]).reindex(full_index).reset_index()
    frame["imputed_suspension_day"] = frame["close"].isna()
    frame["close"] = frame.groupby("symbol", sort=False)["close"].ffill()
    missing_market_row = frame["imputed_suspension_day"]
    for column in ["open", "high", "low"]:
        frame.loc[missing_market_row, column] = frame.loc[missing_market_row, "close"]
    for column in ["amount", "volume", "turnover_rate"]:
        frame.loc[missing_market_row, column] = 0.0
    universe_by_symbol = universe.set_index("symbol")
    frame["stock_name"] = frame["symbol"].map(universe_by_symbol["stock_name"])
    if "industry_name" in universe_by_symbol.columns:
        frame["industry_name"] = frame["symbol"].map(universe_by_symbol["industry_name"])
    frame = frame[frame["trade_date"].ge(common_start_date)].copy()
    frame = frame.sort_values(["symbol", "trade_date"])
    grouped = frame.groupby("symbol", sort=False)
    previous_close = grouped["close"].shift(1)
    frame["amplitude"] = (frame["high"] - frame["low"]) / previous_close * 100.0
    frame["momentum"] = (frame["close"] - previous_close) / previous_close * 100.0
    frame["momentum_volume"] = frame["close"] - previous_close
    frame["turnover"] = frame["turnover_rate"]
    frame[FEATURE_COLUMNS] = frame[FEATURE_COLUMNS].replace([np.inf, -np.inf], np.nan)
    return frame, universe


def prepare_current_dataset(market: pd.DataFrame) -> CurrentDataset:
    frame, universe = _prepare_feature_frame(market)
    symbols = universe["symbol"].tolist()
    complete = frame.dropna(subset=FEATURE_COLUMNS)
    counts = complete.groupby("trade_date")["symbol"].nunique()
    valid_dates = counts[counts.eq(len(symbols))].index.astype(str).tolist()
    if len(valid_dates) <= LOOKBACK_WINDOW:
        raise ValueError(
            f"Current COGRASP needs more than {LOOKBACK_WINDOW} complete dates; "
            f"available={len(valid_dates)}"
        )

    indexed = complete.set_index(["trade_date", "symbol"])
    feature_blocks: list[np.ndarray] = []
    target_blocks: list[np.ndarray] = []
    target_dates: list[str] = []
    for index in range(LOOKBACK_WINDOW, len(valid_dates)):
        input_dates = valid_dates[index - LOOKBACK_WINDOW : index]
        target_date = valid_dates[index]
        sequence = np.stack(
            [
                indexed.loc[(date, symbols), FEATURE_COLUMNS].to_numpy(dtype=np.float32)
                for date in input_dates
            ],
            axis=1,
        )
        target = indexed.loc[(target_date, symbols), "momentum"].to_numpy(dtype=np.float32)
        feature_blocks.append(sequence)
        target_blocks.append(target)
        target_dates.append(target_date)

    features = np.stack(feature_blocks).astype(np.float32)
    targets = np.stack(target_blocks).astype(np.float32)
    if features.shape[1:] != (300, LOOKBACK_WINDOW, len(FEATURE_COLUMNS)):
        raise ValueError(f"Unexpected current COGRASP feature shape: {features.shape}")
    if targets.shape[1:] != (300,):
        raise ValueError(f"Unexpected current COGRASP target shape: {targets.shape}")
    return CurrentDataset(
        features=features,
        targets=targets,
        target_dates=target_dates,
        valid_dates=valid_dates,
        universe=universe,
        feature_frame=frame,
    )


def _fit_scaler(features: np.ndarray, targets: np.ndarray) -> dict[str, np.ndarray]:
    feature_mean = features.mean(axis=(0, 1, 2), dtype=np.float64).astype(np.float32)
    feature_std = features.std(axis=(0, 1, 2), dtype=np.float64).astype(np.float32)
    feature_std = np.where(feature_std < 1e-6, 1.0, feature_std).astype(np.float32)
    target_mean = np.asarray([targets.mean(dtype=np.float64)], dtype=np.float32)
    target_std = np.asarray([targets.std(dtype=np.float64)], dtype=np.float32)
    target_std = np.where(target_std < 1e-6, 1.0, target_std).astype(np.float32)
    return {
        "feature_mean": feature_mean,
        "feature_std": feature_std,
        "target_mean": target_mean,
        "target_std": target_std,
    }


def _scale_features(features: np.ndarray, scaler: dict[str, np.ndarray]) -> np.ndarray:
    return ((features - scaler["feature_mean"]) / scaler["feature_std"]).astype(np.float32)


def _scale_targets(targets: np.ndarray, scaler: dict[str, np.ndarray]) -> np.ndarray:
    return ((targets - scaler["target_mean"][0]) / scaler["target_std"][0]).astype(np.float32)


def build_correlation_graph(
    feature_frame: pd.DataFrame,
    symbols: list[str],
    *,
    top_k: int = DEFAULT_TOP_K,
    end_date: str | None = None,
) -> np.ndarray:
    frame = feature_frame
    if end_date is not None:
        frame = frame[frame["trade_date"].le(end_date)]
    close = frame.pivot(index="trade_date", columns="symbol", values="close").reindex(columns=symbols)
    returns = close.pct_change(fill_method=None)
    correlation = returns.corr(min_periods=60).abs().fillna(0.0).to_numpy(dtype=np.float32)
    np.fill_diagonal(correlation, 0.0)
    if top_k <= 0 or top_k >= len(symbols):
        raise ValueError(f"top_k must be between 1 and {len(symbols) - 1}; got {top_k}")
    adjacency = np.zeros_like(correlation, dtype=np.float32)
    for index in range(len(symbols)):
        neighbours = np.argpartition(correlation[index], -top_k)[-top_k:]
        adjacency[index, neighbours] = correlation[index, neighbours]
    adjacency = np.maximum(adjacency, adjacency.T)
    np.fill_diagonal(adjacency, 0.0)
    if (adjacency > 0).sum(axis=1).min() < top_k:
        raise ValueError("Correlation graph contains an under-connected node")
    return adjacency


def _graph_tensors(torch: Any, adjacency: np.ndarray) -> tuple[Any, Any, Any]:
    source, target = np.nonzero(adjacency > 0)
    edge_index = torch.from_numpy(np.vstack([source, target]).astype(np.int64))
    edge_weight = torch.from_numpy(adjacency[source, target].astype(np.float32))
    graph_x = torch.ones((adjacency.shape[0], len(FEATURE_COLUMNS)), dtype=torch.float32)
    return graph_x, edge_index, edge_weight


def _new_model(torch: Any) -> Any:
    model_module = _load_module("cograsp_current_model", UPSTREAM_MODEL)
    return model_module.COGRASP(
        features=10,
        gnn_hidden_dim=10,
        lstm_hidden_dim=64,
        gnn_num_layers=1,
        lstm_num_layers=1,
    )


def _prediction_metrics(prediction: np.ndarray, target: np.ndarray) -> dict[str, float | None]:
    error = prediction - target
    daily_ic: list[float] = []
    daily_rank_ic: list[float] = []
    for predicted_row, target_row in zip(prediction, target, strict=True):
        if np.std(predicted_row) > 0 and np.std(target_row) > 0:
            daily_ic.append(float(np.corrcoef(predicted_row, target_row)[0, 1]))
        predicted_rank = pd.Series(predicted_row).rank(method="average").to_numpy()
        target_rank = pd.Series(target_row).rank(method="average").to_numpy()
        if np.std(predicted_rank) > 0 and np.std(target_rank) > 0:
            daily_rank_ic.append(float(np.corrcoef(predicted_rank, target_rank)[0, 1]))
    return {
        "mse": float(np.mean(np.square(error))),
        "mae": float(np.mean(np.abs(error))),
        "ic_mean": float(np.mean(daily_ic)) if daily_ic else None,
        "rank_ic_mean": float(np.mean(daily_rank_ic)) if daily_rank_ic else None,
    }


def _predict_array(
    torch: Any,
    model: Any,
    graph_data: tuple[Any, Any, Any],
    features: np.ndarray,
    scaler: dict[str, np.ndarray],
    *,
    batch_size: int,
) -> np.ndarray:
    model.eval()
    outputs: list[np.ndarray] = []
    scaled = _scale_features(features, scaler)
    with torch.inference_mode():
        for start in range(0, len(scaled), batch_size):
            batch = torch.from_numpy(scaled[start : start + batch_size])
            outputs.append(model(graph_data, batch).cpu().numpy())
    normalized = np.concatenate(outputs, axis=0)
    return normalized * scaler["target_std"][0] + scaler["target_mean"][0]


def _fit_model(
    torch: Any,
    model: Any,
    graph_data: tuple[Any, Any, Any],
    train_features: np.ndarray,
    train_targets: np.ndarray,
    scaler: dict[str, np.ndarray],
    *,
    epochs: int,
    batch_size: int,
    learning_rate: float,
    weight_decay: float,
    validation_features: np.ndarray | None = None,
    validation_targets: np.ndarray | None = None,
    patience: int | None = None,
    log: Callable[[str], None] | None = None,
) -> tuple[Any, list[dict[str, float]], int]:
    from torch.utils.data import DataLoader, TensorDataset

    scaled_features = _scale_features(train_features, scaler)
    scaled_targets = _scale_targets(train_targets, scaler)
    loader = DataLoader(
        TensorDataset(torch.from_numpy(scaled_features), torch.from_numpy(scaled_targets)),
        batch_size=batch_size,
        shuffle=True,
        generator=torch.Generator().manual_seed(42),
    )
    optimizer = torch.optim.Adam(model.parameters(), lr=learning_rate, weight_decay=weight_decay)
    scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(
        optimizer, mode="min", factor=0.5, patience=4
    )
    criterion = torch.nn.MSELoss()
    history: list[dict[str, float]] = []
    best_state = copy.deepcopy(model.state_dict())
    best_value = float("inf")
    best_epoch = 1
    stale_epochs = 0

    for epoch in range(1, epochs + 1):
        model.train()
        total_loss = 0.0
        example_count = 0
        for feature_batch, target_batch in loader:
            optimizer.zero_grad(set_to_none=True)
            prediction = model(graph_data, feature_batch)
            loss = criterion(prediction, target_batch)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=5.0)
            optimizer.step()
            total_loss += float(loss.item()) * len(feature_batch)
            example_count += len(feature_batch)
        train_loss = total_loss / max(example_count, 1)
        monitor_value = train_loss
        validation_loss = float("nan")
        if validation_features is not None and validation_targets is not None:
            validation_prediction = _predict_array(
                torch,
                model,
                graph_data,
                validation_features,
                scaler,
                batch_size=batch_size,
            )
            validation_loss = float(np.mean(np.square(validation_prediction - validation_targets)))
            monitor_value = validation_loss
        scheduler.step(monitor_value)
        history.append(
            {
                "epoch": float(epoch),
                "train_loss_normalized": train_loss,
                "validation_mse_pct2": validation_loss,
                "learning_rate": float(optimizer.param_groups[0]["lr"]),
            }
        )
        if monitor_value < best_value - 1e-7:
            best_value = monitor_value
            best_epoch = epoch
            best_state = copy.deepcopy(model.state_dict())
            stale_epochs = 0
        else:
            stale_epochs += 1
        if log is not None:
            validation_text = "n/a" if math.isnan(validation_loss) else f"{validation_loss:.6f}"
            log(
                f"epoch={epoch:03d} train_loss={train_loss:.6f} "
                f"validation_mse={validation_text} lr={optimizer.param_groups[0]['lr']:.6g}"
            )
        if patience is not None and stale_epochs >= patience:
            break
    model.load_state_dict(best_state)
    return model, history, best_epoch


def train_current_cograsp(
    market: pd.DataFrame,
    *,
    epochs: int = 60,
    patience: int = 12,
    batch_size: int = 1,
    top_k: int = DEFAULT_TOP_K,
    learning_rate: float = 1e-3,
    weight_decay: float = 1e-4,
    log: Callable[[str], None] | None = print,
) -> dict[str, Any]:
    try:
        import torch
    except ImportError as exc:
        raise RuntimeError("Install COGRASP dependencies with: uv sync --extra cograsp") from exc

    if epochs < 1 or patience < 1 or batch_size < 1:
        raise ValueError("epochs, patience and batch_size must be positive")
    if batch_size != 1:
        raise ValueError(
            "The unmodified upstream COGRASP forward pass only supports batch_size=1"
        )
    torch.manual_seed(42)
    np.random.seed(42)
    torch.set_num_threads(max(1, min(4, os.cpu_count() or 1)))

    dataset = prepare_current_dataset(market)
    sample_count = len(dataset.target_dates)
    test_count = max(8, int(round(sample_count * 0.15)))
    validation_count = max(8, int(round(sample_count * 0.15)))
    train_count = sample_count - validation_count - test_count
    if train_count < 20:
        raise ValueError(
            f"Not enough complete samples for chronological split: total={sample_count}, train={train_count}"
        )
    train_end = train_count
    validation_end = train_count + validation_count
    evaluation_scaler = _fit_scaler(
        dataset.features[:train_end], dataset.targets[:train_end]
    )
    evaluation_graph = build_correlation_graph(
        dataset.feature_frame,
        dataset.universe["symbol"].tolist(),
        top_k=top_k,
        end_date=dataset.target_dates[train_end - 1],
    )
    evaluation_graph_data = _graph_tensors(torch, evaluation_graph)
    evaluation_model = _new_model(torch)
    evaluation_model, history, best_epoch = _fit_model(
        torch,
        evaluation_model,
        evaluation_graph_data,
        dataset.features[:train_end],
        dataset.targets[:train_end],
        evaluation_scaler,
        epochs=epochs,
        batch_size=batch_size,
        learning_rate=learning_rate,
        weight_decay=weight_decay,
        validation_features=dataset.features[train_end:validation_end],
        validation_targets=dataset.targets[train_end:validation_end],
        patience=patience,
        log=log,
    )
    test_prediction = _predict_array(
        torch,
        evaluation_model,
        evaluation_graph_data,
        dataset.features[validation_end:],
        evaluation_scaler,
        batch_size=batch_size,
    )
    test_metrics = _prediction_metrics(test_prediction, dataset.targets[validation_end:])

    final_scaler = _fit_scaler(dataset.features, dataset.targets)
    final_graph = build_correlation_graph(
        dataset.feature_frame,
        dataset.universe["symbol"].tolist(),
        top_k=top_k,
        end_date=dataset.target_dates[-1],
    )
    final_graph_data = _graph_tensors(torch, final_graph)
    torch.manual_seed(43)
    final_model = _new_model(torch)
    final_epochs = max(1, best_epoch)
    if log is not None:
        log(f"retraining_final_model samples={sample_count} epochs={final_epochs}")
    final_model, final_history, _ = _fit_model(
        torch,
        final_model,
        final_graph_data,
        dataset.features,
        dataset.targets,
        final_scaler,
        epochs=final_epochs,
        batch_size=batch_size,
        learning_rate=learning_rate,
        weight_decay=weight_decay,
        log=None,
    )

    latest_date = dataset.target_dates[-1]
    model_version = f"cograsp-current-csi300-{latest_date.replace('-', '')}-v001"
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    temporary_checkpoint = CHECKPOINT_PATH.with_suffix(".pt.tmp")
    torch.save(final_model.state_dict(), temporary_checkpoint)
    temporary_checkpoint.replace(CHECKPOINT_PATH)
    np.save(GRAPH_PATH, final_graph)
    np.savez(SCALER_PATH, **final_scaler)
    dataset.universe.to_parquet(UNIVERSE_PATH, index=False)
    checkpoint_hash = hashlib.sha256(CHECKPOINT_PATH.read_bytes()).hexdigest()
    metadata = {
        "status": "ok",
        "model_family": MODEL_FAMILY,
        "model_family_zh": MODEL_FAMILY_ZH,
        "model_version": model_version,
        "architecture_source": UPSTREAM_URL,
        "architecture_commit": UPSTREAM_COMMIT,
        "architecture_modified": False,
        "data_pipeline_adapted": True,
        "graph_method": GRAPH_METHOD,
        "graph_top_k": top_k,
        "graph_is_sentiment": False,
        "graph_description": (
            "Static symmetric graph built from absolute pairwise daily-return correlation; "
            "used because the local news cache does not cover the current 300-stock universe."
        ),
        "feature_columns": FEATURE_COLUMNS,
        "lookback_window": LOOKBACK_WINDOW,
        "feature_scaling": "z-score fitted on the applicable training samples",
        "target": "next complete trading date close-to-close relative change in percent",
        "target_scaling": "global z-score fitted on the applicable training samples",
        "latest_training_label_date": latest_date,
        "complete_date_count": len(dataset.valid_dates),
        "sample_count": sample_count,
        "stock_count": len(dataset.universe),
        "sequence_calendar_policy": (
            "Use every observed market trading date from the latest common stock-history start; "
            "a missing/suspended stock-day carries the previous close and uses zero volume, amount and turnover."
        ),
        "imputed_stock_day_count": int(dataset.feature_frame["imputed_suspension_day"].sum()),
        "chronological_split": {
            "train_count": train_count,
            "train_end_date": dataset.target_dates[train_end - 1],
            "validation_count": validation_count,
            "validation_start_date": dataset.target_dates[train_end],
            "validation_end_date": dataset.target_dates[validation_end - 1],
            "test_count": test_count,
            "test_start_date": dataset.target_dates[validation_end],
            "test_end_date": dataset.target_dates[-1],
        },
        "selection_best_epoch": best_epoch,
        "selection_epochs_ran": len(history),
        "final_retraining_epochs": final_epochs,
        "final_training_loss_normalized": final_history[-1]["train_loss_normalized"],
        "test_metrics": test_metrics,
        "checkpoint_sha256": checkpoint_hash,
        "checkpoint": str(CHECKPOINT_PATH.relative_to(ROOT)).replace("\\", "/"),
        "graph": str(GRAPH_PATH.relative_to(ROOT)).replace("\\", "/"),
        "scaler": str(SCALER_PATH.relative_to(ROOT)).replace("\\", "/"),
        "universe": str(UNIVERSE_PATH.relative_to(ROOT)).replace("\\", "/"),
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "limitations": [
            "The current-universe complete-date training sample is small.",
            "The relationship graph is market-correlation based, not the paper's news/social co-occurrence graph.",
            "No positive/negative text sentiment classifier is used because current-universe news coverage is insufficient.",
        ],
    }
    METADATA_PATH.write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2, default=_json_default),
        encoding="utf-8",
    )
    return metadata


def _next_business_date(date_text: str) -> str:
    return (pd.Timestamp(date_text) + pd.offsets.BDay(1)).strftime("%Y-%m-%d")


def predict_current_cograsp(market: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, Any]]:
    try:
        import torch
    except ImportError as exc:
        raise RuntimeError("Install COGRASP dependencies with: uv sync --extra cograsp") from exc
    required_artifacts = [CHECKPOINT_PATH, SCALER_PATH, GRAPH_PATH, UNIVERSE_PATH, METADATA_PATH]
    missing = [str(path) for path in required_artifacts if not path.exists()]
    if missing:
        raise FileNotFoundError(
            "Current COGRASP artifacts are missing; run scripts/train_cograsp_current.py first: "
            + ", ".join(missing)
        )

    metadata = json.loads(METADATA_PATH.read_text(encoding="utf-8"))
    artifact_universe = pd.read_parquet(UNIVERSE_PATH).sort_values("symbol").reset_index(drop=True)
    frame, latest_universe = _prepare_feature_frame(market)
    symbols = artifact_universe["symbol"].astype(str).tolist()
    latest_symbols = latest_universe["symbol"].astype(str).tolist()
    if symbols != latest_symbols:
        raise ValueError("Latest CSI300 universe differs from the trained artifact universe; retrain first")
    complete = frame.dropna(subset=FEATURE_COLUMNS)
    counts = complete.groupby("trade_date")["symbol"].nunique()
    valid_dates = counts[counts.eq(len(symbols))].index.astype(str).tolist()
    if len(valid_dates) < LOOKBACK_WINDOW:
        raise ValueError(f"Not enough complete dates for inference: {len(valid_dates)}")
    input_dates = valid_dates[-LOOKBACK_WINDOW:]
    indexed = complete.set_index(["trade_date", "symbol"])
    sequence = np.stack(
        [indexed.loc[(date, symbols), FEATURE_COLUMNS].to_numpy(dtype=np.float32) for date in input_dates],
        axis=1,
    )[None, ...]
    with np.load(SCALER_PATH) as scaler_file:
        scaler = {key: scaler_file[key] for key in scaler_file.files}
    adjacency = np.load(GRAPH_PATH)
    graph_data = _graph_tensors(torch, adjacency)
    model = _new_model(torch)
    state_dict = torch.load(CHECKPOINT_PATH, map_location="cpu", weights_only=True)
    model.load_state_dict(state_dict, strict=True)
    raw_prediction = _predict_array(
        torch, model, graph_data, sequence, scaler, batch_size=1
    ).squeeze(0)
    if raw_prediction.shape != (300,) or not np.isfinite(raw_prediction).all():
        raise ValueError(f"Invalid current COGRASP output: shape={raw_prediction.shape}")

    predictions = artifact_universe.copy()
    predictions["predicted_relative_change_pct"] = raw_prediction.astype(float)
    predictions["predicted_relative_change"] = predictions["predicted_relative_change_pct"] / 100.0
    predictions["score"] = predictions["predicted_relative_change_pct"]
    predictions["rank"] = predictions["score"].rank(ascending=False, method="first").astype(int)
    predictions["percentile"] = predictions["score"].rank(pct=True)
    predictions = predictions.sort_values(["rank", "symbol"]).reset_index(drop=True)
    latest_input_date = input_dates[-1]
    inference_metadata = {
        **metadata,
        "latest_input_date": latest_input_date,
        "input_dates": input_dates,
        "prediction_target_date": _next_business_date(latest_input_date),
        "prediction_target_date_is_estimated": True,
        "prediction_target_date_note": (
            "Estimated as the next weekday because the local trading calendar is only covered "
            "through the latest observed market date."
        ),
        "output_semantics": "next-trading-day relative price change in percent",
    }
    return predictions, inference_metadata
