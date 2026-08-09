from __future__ import annotations

import importlib.util
import json
import math
import platform
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
UPSTREAM_ROOT = ROOT / "third_party" / "FinMamba"
UPSTREAM_REPOSITORY = "https://github.com/TROUBADOUR000/FinMamba"
UPSTREAM_COMMIT = "e4f8ce33e4ddbc4a46b738de9265771aec2c4d16"
UPSTREAM_PAPER = "https://arxiv.org/abs/2502.06707"
MODEL_VERSION = f"finmamba-official-{UPSTREAM_COMMIT[:12]}"
MODEL_FAMILY = "FinMamba official current CSI300"

CURRENT_DAILY = ROOT / "data" / "real" / "csi300_daily" / "part-000.parquet"
DATA_DIR = ROOT / "data" / "real" / "finmamba_csi300"
RELATION_DIR = ROOT / "data" / "real" / "finmamba_relations"
CHECKPOINT_DIR = ROOT / "models" / "checkpoints" / "finmamba_current_csi300"
CHECKPOINT_PATH = CHECKPOINT_DIR / "best_model.pth"
SCORES_PATH = CHECKPOINT_DIR / "scores.csv"
PREDICTIONS_PATH = ROOT / "reports" / "research_loop" / "finmamba_predictions.parquet"
REPORT_PATH = ROOT / "reports" / "research_loop" / "finmamba_predictions_report.json"

# This order is the six-feature CSI input documented by the FinMamba authors.
FEATURE_COLUMNS = ("high", "low", "open", "close", "volume", "turnover")
SOURCE_COLUMNS = {
    "high": "high",
    "low": "low",
    "open": "open",
    "close": "close",
    "volume": "volume",
    "turnover": "turnover_rate",
}
SEQ_LEN = 20
RESEARCH_BOUNDARY = "research_signals_only_not_investment_advice"


@dataclass(frozen=True)
class PreparedFinMambaPanel:
    training_features: pd.DataFrame
    training_labels: pd.DataFrame
    all_features: pd.DataFrame
    industry_relation: np.ndarray
    symbols: tuple[str, ...]
    labeled_dates: tuple[str, ...]
    all_dates: tuple[str, ...]
    stock_metadata: pd.DataFrame
    metadata: dict[str, Any]


def _json_default(value: Any) -> Any:
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        number = float(value)
        return None if math.isnan(number) or math.isinf(number) else number
    if isinstance(value, (pd.Timestamp, datetime, Path)):
        return str(value)
    return str(value)


def upstream_source_status() -> dict[str, Any]:
    license_path = UPSTREAM_ROOT / "LICENSE"
    source_files = [
        UPSTREAM_ROOT / "finmamba" / "models.py",
        UPSTREAM_ROOT / "finmamba" / "trainer.py",
        UPSTREAM_ROOT / "finmamba" / "data.py",
        UPSTREAM_ROOT / "genRelation.py",
        UPSTREAM_ROOT / "train_finmamba.py",
    ]
    license_name = None
    if license_path.exists():
        first_lines = license_path.read_text(encoding="utf-8", errors="replace")[:200]
        if "Apache License" in first_lines and "Version 2.0" in first_lines:
            license_name = "Apache-2.0"
    return {
        "repository": UPSTREAM_REPOSITORY,
        "paper": UPSTREAM_PAPER,
        "commit": UPSTREAM_COMMIT,
        "model_version": MODEL_VERSION,
        "source_present": UPSTREAM_ROOT.exists() and all(path.exists() for path in source_files),
        "license": license_name,
        "architecture_modified": False,
    }


def runtime_status() -> dict[str, Any]:
    system = platform.system().lower()
    torch_available = importlib.util.find_spec("torch") is not None
    pyg_available = importlib.util.find_spec("torch_geometric") is not None
    mamba_available = importlib.util.find_spec("mamba_ssm") is not None
    cuda_available = False
    torch_version = None
    if torch_available:
        import torch

        torch_version = torch.__version__
        cuda_available = bool(torch.cuda.is_available())

    blockers: list[str] = []
    if system != "linux":
        blockers.append("mamba-ssm 官方运行环境要求 Linux")
    if not torch_available:
        blockers.append("缺少 PyTorch")
    if not pyg_available:
        blockers.append("缺少 torch-geometric")
    if not mamba_available:
        blockers.append("缺少 mamba-ssm")
    if not cuda_available:
        blockers.append("未检测到作者实验所需的 NVIDIA CUDA 运行设备")

    return {
        "status": "ready" if not blockers else "blocked_runtime",
        "platform": platform.platform(),
        "python": platform.python_version(),
        "torch_version": torch_version,
        "torch_available": torch_available,
        "torch_geometric_available": pyg_available,
        "mamba_ssm_available": mamba_available,
        "cuda_available": cuda_available,
        "blockers": blockers,
        "required_environment": "Linux + Python 3.10+ + PyTorch + torch-geometric + mamba-ssm + NVIDIA CUDA",
    }


def _validate_market_frame(market: pd.DataFrame) -> pd.DataFrame:
    required = {"trade_date", "symbol", *SOURCE_COLUMNS.values()}
    missing = required - set(market.columns)
    if missing:
        raise ValueError(f"FinMamba market data is missing columns: {sorted(missing)}")
    frame = market.copy()
    frame["trade_date"] = pd.to_datetime(frame["trade_date"]).dt.strftime("%Y-%m-%d")
    frame["symbol"] = frame["symbol"].astype(str)
    frame = frame.drop_duplicates(["trade_date", "symbol"], keep="last")
    for column in SOURCE_COLUMNS.values():
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    if frame[list(SOURCE_COLUMNS.values())].isna().any().any():
        raise ValueError("FinMamba official six-feature input contains missing numeric values")
    return frame.sort_values(["trade_date", "symbol"]).reset_index(drop=True)


def _fixed_complete_universe(frame: pd.DataFrame) -> tuple[list[str], list[str]]:
    dates = sorted(frame["trade_date"].unique().tolist())
    latest_date = dates[-1]
    coverage = frame.groupby("symbol", sort=False)["trade_date"].nunique()
    latest_symbols = set(frame.loc[frame["trade_date"].eq(latest_date), "symbol"])
    symbols = sorted(
        symbol
        for symbol, count in coverage.items()
        if int(count) == len(dates) and symbol in latest_symbols
    )
    if len(symbols) < 2:
        raise ValueError("FinMamba requires at least two stocks with a complete fixed panel")
    if len(dates) < SEQ_LEN * 3:
        raise ValueError(
            f"FinMamba requires at least {SEQ_LEN * 3} complete trading days, found {len(dates)}"
        )
    return symbols, dates


def _industry_decay_matrix(
    stock_metadata: pd.DataFrame,
    symbols: list[str],
    *,
    different_industry_decay: float = 0.1,
) -> tuple[np.ndarray, int]:
    relation = np.full(
        (len(symbols), len(symbols)),
        float(different_industry_decay),
        dtype=np.float32,
    )
    np.fill_diagonal(relation, 1.0)
    industry_by_symbol: dict[str, str] = {}
    if "industry_name" in stock_metadata.columns:
        for row in stock_metadata[["symbol", "industry_name"]].itertuples(index=False):
            value = str(row.industry_name or "").strip()
            if value and not value.lower().startswith("unknown") and value not in {"未知", "未知行业"}:
                industry_by_symbol[str(row.symbol)] = value
    for left, left_symbol in enumerate(symbols):
        left_industry = industry_by_symbol.get(left_symbol)
        if not left_industry:
            continue
        for right in range(left + 1, len(symbols)):
            if industry_by_symbol.get(symbols[right]) == left_industry:
                relation[left, right] = 1.0
                relation[right, left] = 1.0
    return relation, len(industry_by_symbol)


def split_labeled_dates(labeled_dates: list[str]) -> dict[str, str]:
    count = len(labeled_dates)
    train_stop = max(SEQ_LEN, int(count * 0.70))
    valid_stop = max(train_stop + SEQ_LEN, int(count * 0.85))
    if valid_stop >= count:
        raise ValueError(
            f"FinMamba needs train/validation/test history; {count} labeled days are insufficient"
        )
    return {
        "train_start": labeled_dates[0],
        "train_end": labeled_dates[train_stop - 1],
        "valid_start": labeled_dates[train_stop],
        "valid_end": labeled_dates[valid_stop - 1],
        "test_start": labeled_dates[valid_stop],
        "test_end": labeled_dates[-1],
    }


def prepare_official_panel(market: pd.DataFrame) -> PreparedFinMambaPanel:
    frame = _validate_market_frame(market)
    source_stock_count = int(frame["symbol"].nunique())
    symbols, dates = _fixed_complete_universe(frame)
    frame = frame[frame["symbol"].isin(symbols)].copy()
    expected_rows = len(symbols) * len(dates)
    if len(frame) != expected_rows:
        raise ValueError(
            f"FinMamba fixed panel has {len(frame)} rows, expected {expected_rows}"
        )

    latest_rows = frame[frame["trade_date"].eq(dates[-1])].copy()
    metadata_columns = [
        column
        for column in ("symbol", "stock_name", "industry_name")
        if column in latest_rows.columns
    ]
    stock_metadata = latest_rows[metadata_columns].drop_duplicates("symbol").sort_values("symbol")

    features = pd.DataFrame(
        {
            "instrument": frame["symbol"],
            "datetime": frame["trade_date"],
            **{
                target: frame[source].astype(float)
                for target, source in SOURCE_COLUMNS.items()
            },
        }
    ).sort_values(["datetime", "instrument"])

    close = frame.pivot(index="trade_date", columns="symbol", values="close").reindex(
        index=dates, columns=symbols
    )
    next_day_return = close.shift(-1).div(close).sub(1.0)
    labeled_dates = dates[:-1]
    label_values = next_day_return.loc[labeled_dates].stack(future_stack=True).rename("label")
    labels = label_values.rename_axis(["datetime", "instrument"]).reset_index()
    labels = labels.sort_values(["datetime", "instrument"])

    training_features = features[features["datetime"].isin(labeled_dates)].copy()
    if len(training_features) != len(labels):
        raise ValueError(
            f"FinMamba feature/label rows differ: {len(training_features)} != {len(labels)}"
        )
    industry_relation, industry_coverage = _industry_decay_matrix(
        stock_metadata, symbols
    )
    split = split_labeled_dates(labeled_dates)
    metadata = {
        "status": "ok",
        "model_family": MODEL_FAMILY,
        "model_version": MODEL_VERSION,
        "upstream": upstream_source_status(),
        "feature_columns": list(FEATURE_COLUMNS),
        "label_definition": "next_trading_day_close_return_ratio",
        "relationship_definition": "official_20_day_per_feature_spearman_times_industry_decay",
        "sequence_length": SEQ_LEN,
        "stock_count": len(symbols),
        "source_stock_count": source_stock_count,
        "day_count": len(dates),
        "labeled_day_count": len(labeled_dates),
        "latest_input_date": dates[-1],
        "latest_training_label_date": labeled_dates[-1],
        "industry_symbol_coverage": industry_coverage,
        "industry_fallback": (
            "different_industry_decay_0.1_for_unknown_symbols"
            if industry_coverage < len(symbols)
            else None
        ),
        "universe_policy": "latest CSI300 symbols with complete coverage across the local history",
        "split": split,
        "architecture_modified": False,
        "algorithm_modified": False,
        "data_pipeline_adapted": True,
    }
    return PreparedFinMambaPanel(
        training_features=training_features.set_index(["instrument", "datetime"]),
        training_labels=labels.set_index(["instrument", "datetime"]),
        all_features=features.set_index(["instrument", "datetime"]),
        industry_relation=industry_relation,
        symbols=tuple(symbols),
        labeled_dates=tuple(labeled_dates),
        all_dates=tuple(dates),
        stock_metadata=stock_metadata,
        metadata=metadata,
    )


def write_official_inputs(
    market: pd.DataFrame,
    *,
    output_dir: Path = DATA_DIR,
) -> dict[str, Any]:
    prepared = prepare_official_panel(market)
    output_dir.mkdir(parents=True, exist_ok=True)
    prepared.training_features.to_pickle(output_dir / "csi300fea.pkl")
    prepared.training_labels.to_pickle(output_dir / "csi300lab.pkl")
    prepared.all_features.to_pickle(output_dir / "csi300_allfea.pkl")
    np.save(output_dir / "csi300_industry_relationship.npy", prepared.industry_relation)
    prepared.stock_metadata.to_csv(output_dir / "csi300_symbols.csv", index=False)
    manifest = {
        **prepared.metadata,
        "data_dir": str(output_dir),
        "relation_dir": str(RELATION_DIR),
        "checkpoint_path": str(CHECKPOINT_PATH),
        "prepared_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    (output_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, default=_json_default),
        encoding="utf-8",
    )
    return manifest


def write_runtime_report(
    *,
    preparation: dict[str, Any] | None = None,
    report_path: Path = REPORT_PATH,
) -> dict[str, Any]:
    runtime = runtime_status()
    source = upstream_source_status()
    report = {
        "status": runtime["status"],
        "model_family": MODEL_FAMILY,
        "model_version": MODEL_VERSION,
        "model_description": (
            "作者原版 FinMamba：市场引导动态图 GAT + 多层级 Mamba，使用日频量价和行业衰减关系。"
        ),
        "integration_status": "source_and_data_adapter_ready_training_runtime_blocked"
        if runtime["status"] != "ready"
        else "source_data_and_training_runtime_ready",
        "runtime": runtime,
        "runtime_requirements": runtime["required_environment"],
        "runtime_blockers": runtime["blockers"],
        "upstream_source": source,
        "latest_trade_date": (preparation or {}).get("latest_input_date"),
        "latest_training_label_date": (preparation or {}).get("latest_training_label_date"),
        "training_sample_count": (
            int((preparation or {}).get("stock_count", 0))
            * int((preparation or {}).get("labeled_day_count", 0))
        ),
        "model_methodology": preparation or {},
        "training_command": "python scripts/train_finmamba_official.py --train --device cuda:0",
        "architecture_modified": False,
        "algorithm_modified": False,
        "data_pipeline_adapted": True,
        "paper_references": [UPSTREAM_PAPER, UPSTREAM_REPOSITORY],
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "research_boundary": RESEARCH_BOUNDARY,
    }
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, default=_json_default),
        encoding="utf-8",
    )
    return report


def _next_business_day(value: str) -> str:
    return (pd.Timestamp(value) + pd.offsets.BDay(1)).strftime("%Y-%m-%d")


def _test_metrics(scores: np.ndarray, labels: np.ndarray) -> dict[str, float | None]:
    if scores.shape != labels.shape:
        raise ValueError(f"FinMamba test score/label shapes differ: {scores.shape} != {labels.shape}")
    mse = float(np.mean((scores - labels) ** 2))
    mae = float(np.mean(np.abs(scores - labels)))
    ic_values: list[float] = []
    rank_ic_values: list[float] = []
    for score_row, label_row in zip(scores, labels, strict=True):
        if np.std(score_row) > 0 and np.std(label_row) > 0:
            ic_values.append(float(np.corrcoef(score_row, label_row)[0, 1]))
            rank_score = pd.Series(score_row).rank().to_numpy()
            rank_label = pd.Series(label_row).rank().to_numpy()
            rank_ic_values.append(float(np.corrcoef(rank_score, rank_label)[0, 1]))
    return {
        "mse": mse,
        "mae": mae,
        "ic_mean": float(np.mean(ic_values)) if ic_values else None,
        "rank_ic_mean": float(np.mean(rank_ic_values)) if rank_ic_values else None,
    }


def publish_latest_predictions(
    *,
    data_dir: Path = DATA_DIR,
    relation_dir: Path = RELATION_DIR,
    checkpoint_path: Path = CHECKPOINT_PATH,
    scores_path: Path = SCORES_PATH,
    predictions_path: Path = PREDICTIONS_PATH,
    report_path: Path = REPORT_PATH,
    device_spec: str = "auto",
) -> dict[str, Any]:
    runtime = runtime_status()
    if runtime["status"] != "ready":
        raise RuntimeError("; ".join(runtime["blockers"]))
    if not checkpoint_path.exists():
        raise FileNotFoundError(f"FinMamba checkpoint not found: {checkpoint_path}")
    manifest = json.loads((data_dir / "manifest.json").read_text(encoding="utf-8"))

    if str(UPSTREAM_ROOT) not in sys.path:
        sys.path.insert(0, str(UPSTREAM_ROOT))
    import torch
    from finmamba.data import RelationStore
    from finmamba.models import FinMamba
    from finmamba.utils import resolve_device

    device = resolve_device(device_spec)
    feature_frame = pd.read_pickle(data_dir / "csi300_allfea.pkl").reset_index()
    feature_frame = feature_frame.sort_values(["datetime", "instrument"])
    symbols = sorted(feature_frame["instrument"].astype(str).unique().tolist())
    dates = sorted(feature_frame["datetime"].astype(str).unique().tolist())
    values = feature_frame[list(FEATURE_COLUMNS)].to_numpy(dtype=np.float32)
    tensor = torch.as_tensor(
        values.reshape(len(dates), len(symbols), len(FEATURE_COLUMNS)),
        dtype=torch.float32,
        device=device,
    )
    industry = torch.as_tensor(
        np.load(data_dir / "csi300_industry_relationship.npy"),
        device=device,
    )
    relations = RelationStore(
        relation_dir=relation_dir,
        relation_pattern="day{index}.pkl",
        industry_relation=industry,
        stock_num=len(symbols),
        device=device,
    )
    model = FinMamba(
        input_dim=len(FEATURE_COLUMNS),
        stock_num=len(symbols),
        hidden_channels=32,
        out_channels=len(FEATURE_COLUMNS),
        gat_layers=2,
        gat_heads=2,
        mamba_hidden_sizes=[64, 64],
        mamba_output_size=16,
        mamba_num_heads=2,
        mamba_d_state=128,
        mamba_d_conv=2,
        mamba_expand=1,
        market_kernel_sizes=[4, 10, 20],
        market_init_sparsity=0.2,
        dropout=0.1,
        seq_len=SEQ_LEN,
    ).to(device)
    model.load_state_dict(torch.load(checkpoint_path, map_location=device))
    model.eval()
    window = [
        torch.cat((tensor[index], tensor[index]), dim=1)
        for index in range(len(dates) - SEQ_LEN, len(dates) - 1)
    ]
    market_index = tensor.mean(dim=1)[-SEQ_LEN:]
    with torch.no_grad():
        scores, _, _ = model(
            tensor[-1],
            relations.load(len(dates) - 1),
            market_index,
            window,
            is_training=False,
        )
    score_values = scores.detach().cpu().numpy()
    latest_date = dates[-1]
    target_date = _next_business_day(latest_date)
    output = pd.DataFrame({"symbol": symbols, "score": score_values})
    output["predicted_relative_change"] = output["score"]
    output["predicted_relative_change_pct"] = output["score"] * 100.0
    output["rank"] = output["score"].rank(ascending=False, method="first").astype(int)
    output["percentile"] = output["score"].rank(pct=True)
    output["trade_date"] = latest_date
    output["prediction_target_date"] = target_date
    output["horizon"] = "1d"
    output["model_name"] = "FinMamba"
    output["model_family"] = MODEL_FAMILY
    output["model_version"] = MODEL_VERSION
    output["probability_up"] = np.nan
    output["probability_down"] = np.nan
    output["confidence"] = np.nan
    output["signal_direction"] = np.where(output["score"].ge(0), "up", "down")
    output["information_source"] = "official_finmamba_price_volume_dynamic_graph"
    output["sentiment_polarity_used"] = False
    output["leakage_check_status"] = "chronological_split_latest_unlabeled_inference"
    output["research_boundary"] = RESEARCH_BOUNDARY
    output = output.sort_values(["rank", "symbol"]).reset_index(drop=True)
    predictions_path.parent.mkdir(parents=True, exist_ok=True)
    output.to_parquet(predictions_path, index=False)

    test_scores = pd.read_csv(scores_path, header=None).to_numpy(dtype=float)
    label_frame = pd.read_pickle(data_dir / "csi300lab.pkl").reset_index()
    split = manifest["split"]
    test_labels_frame = label_frame[
        label_frame["datetime"].astype(str).between(split["test_start"], split["test_end"])
    ].sort_values(["datetime", "instrument"])
    test_labels = test_labels_frame["label"].to_numpy(dtype=float).reshape(
        test_labels_frame["datetime"].nunique(), len(symbols)
    )
    metrics = _test_metrics(test_scores, test_labels)
    report = {
        "status": "ok",
        "run_id": f"finmamba_current_csi300_{latest_date.replace('-', '')}",
        "experiment_id": "exp_finmamba_official_current_csi300_v001",
        "model_family": MODEL_FAMILY,
        "model_version": MODEL_VERSION,
        "model_description": "作者原版 FinMamba：市场引导动态图 GAT + 多层级 Mamba。",
        "latest_trade_date": latest_date,
        "prediction_target_date": target_date,
        "prediction_target_date_is_estimated": True,
        "latest_training_label_date": manifest["latest_training_label_date"],
        "training_sample_count": manifest["stock_count"] * manifest["labeled_day_count"],
        "prediction_rows": len(output),
        "model_output_rows": len(output),
        "display_overlap_rows": len(output),
        "test_metrics": metrics,
        "relationship_graph": manifest["relationship_definition"],
        "model_methodology": manifest,
        "runtime": runtime,
        "upstream_source": upstream_source_status(),
        "probability_calibration": "none; raw next-day return ranking score",
        "sentiment_status": "not_used",
        "architecture_modified": False,
        "algorithm_modified": False,
        "data_pipeline_adapted": True,
        "paper_references": [UPSTREAM_PAPER, UPSTREAM_REPOSITORY],
        "artifact": str(predictions_path.relative_to(ROOT)).replace("\\", "/"),
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "research_boundary": RESEARCH_BOUNDARY,
    }
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, default=_json_default),
        encoding="utf-8",
    )
    return report
