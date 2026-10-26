from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd
import pyarrow.parquet as pq
import yaml

ROOT = Path(__file__).resolve().parents[2]
FACTOR_LONG_DIR = ROOT / "data" / "gold" / "factor_daily_panel_long"
FEATURE_WIDE_DIR = ROOT / "data" / "gold" / "model_feature_matrix_wide"
REPORT_PATH = ROOT / "reports" / "factor_store" / "point_in_time_join_report.json"
FEATURE_SET_VERSION = "feature_set_factor_store_v001"
RUN_ID = "factor_store_offline_factor_store_v001"
RESEARCH_BOUNDARY = "research_signals_only_not_investment_advice"
FEATURE_REGISTRY_PATH = ROOT / "feature_store" / "feature_registry.yaml"


def _feature_names_from_registry(long: pd.DataFrame) -> list[str]:
    if FEATURE_REGISTRY_PATH.exists():
        registry = yaml.safe_load(FEATURE_REGISTRY_PATH.read_text(encoding="utf-8")) or {}
        names = [item.get("feature_name") for item in registry.get("features", [])]
        clean_names = [str(name) for name in names if name]
        if clean_names:
            return clean_names
    return sorted(long["factor_name"].dropna().astype(str).unique())


def _read_factor_long() -> pd.DataFrame:
    files = list(FACTOR_LONG_DIR.glob("**/*.parquet"))
    if not files:
        from factors.offline.polars_factor_engine import materialize_factor_store

        # Clean CI checkouts intentionally do not commit generated data/gold artifacts.
        # Build the deterministic synthetic factor store on demand instead of relying
        # on local workspace residue from a previous validation run.
        materialize_factor_store(write_outputs=True)
        files = list(FACTOR_LONG_DIR.glob("**/*.parquet"))
    if not files:
        raise FileNotFoundError(f"Missing factor long parquet files under {FACTOR_LONG_DIR}")
    return pd.concat([pd.read_parquet(path) for path in files], ignore_index=True)


def _write_join_report(input_rows: int, wide: pd.DataFrame, feature_names: list[str], violations: int) -> dict[str, Any]:
    report = {
        "status": "ok",
        "feature_set_version": FEATURE_SET_VERSION,
        "input_rows": input_rows,
        "output_rows": int(len(wide)),
        "feature_count": int(len(feature_names)),
        "point_in_time_violations": violations,
        "latest_trade_date": None if wide.empty else str(wide["trade_date"].max()),
        "output": str(FEATURE_WIDE_DIR.relative_to(ROOT)),
        "research_boundary": RESEARCH_BOUNDARY,
    }
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def _validate_existing_feature_matrix() -> dict[str, Any]:
    """Validate freshly materialized features without pivoting or rewriting them."""
    files = sorted(FEATURE_WIDE_DIR.glob("**/*.parquet"))
    long_files = sorted(FACTOR_LONG_DIR.glob("**/*.parquet"))
    if not files or not long_files:
        raise FileNotFoundError("Both materialized factor panels and feature matrices are required")
    feature_names = _feature_names_from_registry(pd.DataFrame(columns=["factor_name"]))
    if not feature_names:
        raise AssertionError("Feature registry is empty")
    id_cols = ["trade_date", "symbol", "prediction_time", "available_time"]
    frames = []
    for path in files:
        with pq.ParquetFile(path) as parquet:
            missing = sorted(set(id_cols + feature_names) - set(parquet.schema_arrow.names))
            if missing:
                raise AssertionError(f"model_feature_matrix_wide missing columns: {missing}")
            frames.append(parquet.read(columns=id_cols).to_pandas())
    wide = pd.concat(frames, ignore_index=True)
    available = pd.to_datetime(wide["available_time"], errors="coerce", utc=True)
    prediction = pd.to_datetime(wide["prediction_time"], errors="coerce", utc=True)
    if wide.empty or available.isna().any() or prediction.isna().any():
        raise AssertionError("Point-in-time validation requires nonempty features and valid availability/prediction times")
    violations = int(available.gt(prediction).sum())
    if violations:
        raise AssertionError(f"Point-in-time join blocked {violations} future-available feature rows")
    input_rows = 0
    for path in long_files:
        with pq.ParquetFile(path) as parquet:
            input_rows += parquet.metadata.num_rows
    return _write_join_report(input_rows, wide, feature_names, violations)


def build_model_feature_matrix(*, validate_existing: bool = False) -> dict[str, Any]:
    if validate_existing:
        return _validate_existing_feature_matrix()
    long = _read_factor_long()
    required = {"trade_date", "symbol", "prediction_time", "available_time", "factor_name", "factor_value"}
    missing = sorted(required - set(long.columns))
    if missing:
        raise AssertionError(f"factor_daily_panel_long missing columns: {missing}")
    # Point-in-time safety gate: every feature value must be available at or before prediction_time.
    long["available_ts"] = pd.to_datetime(long["available_time"], errors="coerce", utc=True)
    long["prediction_ts"] = pd.to_datetime(long["prediction_time"], errors="coerce", utc=True)
    violations = long[long["available_ts"] > long["prediction_ts"]]
    if not violations.empty:
        raise AssertionError(f"Point-in-time join blocked {len(violations)} future-available rows")
    id_cols = ["trade_date", "symbol", "prediction_time", "available_time"]
    feature_names = _feature_names_from_registry(long)
    wide = long.pivot_table(index=id_cols, columns="factor_name", values="factor_value", aggfunc="last").reset_index()
    for feature_name in feature_names:
        if feature_name not in wide.columns:
            wide[feature_name] = pd.NA
    wide = wide[id_cols + feature_names]
    wide.insert(0, "run_id", RUN_ID)
    wide.insert(4, "feature_set_version", FEATURE_SET_VERSION)
    wide["research_boundary"] = RESEARCH_BOUNDARY
    FEATURE_WIDE_DIR.mkdir(parents=True, exist_ok=True)
    for old in FEATURE_WIDE_DIR.glob("**/*.parquet"):
        old.unlink()
    wide.to_parquet(FEATURE_WIDE_DIR / "part-000.parquet", index=False)
    return _write_join_report(int(len(long)), wide, feature_names, int(len(violations)))


def main() -> None:
    print(json.dumps(build_model_feature_matrix(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
