from __future__ import annotations

import json
import math
import sys
from pathlib import Path
from typing import Any

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

RESEARCH_BOUNDARY = "research_signals_only_not_investment_advice"
research_loop_DIR = ROOT / "reports" / "research_loop"


def _json_default(value: Any) -> Any:
    try:
        if pd.isna(value):
            return None
    except Exception:
        pass
    return str(value)


def _read_parquet_file(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    return pd.read_parquet(path)


def _read_parquet_dir(path: Path) -> pd.DataFrame:
    files = sorted(path.glob("**/*.parquet"))
    if not files:
        return pd.DataFrame()
    return pd.concat([pd.read_parquet(file) for file in files], ignore_index=True, sort=False)


def _metric_ok(value: Any) -> bool:
    try:
        value = float(value)
    except Exception:
        return False
    return not math.isnan(value) and not math.isinf(value)


def run_acceptance() -> dict[str, Any]:
    from backend.app.main import app
    from models.research_loop_research_loop import run_research_loop_research_loop
    from tests.auth_helpers import authenticated_admin_client

    report = run_research_loop_research_loop(write_outputs=True)
    client = authenticated_admin_client(app)
    failed: list[str] = []

    def check(name: str, condition: bool) -> None:
        if not condition:
            failed.append(name)

    labels = _read_parquet_dir(ROOT / "data" / "gold" / "label_cross_sectional_return")
    signals = _read_parquet_dir(ROOT / "data" / "gold" / "model_signal_cross_sectional")
    backtest = _read_parquet_dir(ROOT / "data" / "gold" / "portfolio_backtest_result")
    risk_gold = _read_parquet_dir(ROOT / "data" / "gold" / "portfolio_risk_report")
    predictions = _read_parquet_file(research_loop_DIR / "predictions.parquet")
    holdings = _read_parquet_file(research_loop_DIR / "holdings.parquet")
    risk_report = _read_parquet_file(research_loop_DIR / "risk_report.parquet")
    recorder_dir = research_loop_DIR / "experiment_recorder" / str(report.get("run_id"))

    expected_label_columns = {
        "trade_date",
        "symbol",
        "horizon",
        "prediction_time",
        "execution_price_type",
        "execution_window",
        "label_start_time",
        "label_end_time",
        "forward_return",
        "excess_return",
        "industry_neutral_return",
        "cs_zscore_label",
        "quantile_label",
        "tradable_flag",
        "pause_flag",
        "st_flag",
        "limit_up_at_entry",
        "limit_down_at_exit",
        "delist_flag",
        "label_version",
    }
    expected_risk_columns = {
        "run_id",
        "trade_date",
        "portfolio_id",
        "benchmark",
        "active_return",
        "annualized_active_return",
        "tracking_error",
        "information_ratio",
        "beta_to_benchmark",
        "alpha",
        "active_max_drawdown",
        "hit_rate_vs_benchmark",
        "up_capture",
        "down_capture",
        "industry_attribution",
        "style_attribution",
        "stock_selection_attribution",
        "transaction_cost_attribution",
        "implementation_shortfall",
        "capacity_curve",
        "risk_model_version",
    }
    metrics = report.get("metrics", {})
    baseline_metrics = metrics.get("baseline_metrics", {})

    check("research_loop_research_loop_status_ok", report.get("status") == "ok")
    check("label_table_written_with_required_columns", not labels.empty and expected_label_columns.issubset(labels.columns))
    check("label_horizons_5d_10d", set(labels["horizon"].astype(str).unique()) >= {"5d", "10d"})
    check("label_leakage_check_passed", report.get("leakage_check_status") == "passed" and labels["leakage_check_status"].eq("passed").all())
    check("lightgbm_baseline_trained", report.get("lightgbm_status") == "trained" and report.get("prediction_rows", 0) > 0)
    check("walk_forward_three_splits", report.get("split_count", 0) >= 3)
    check("baseline_metrics_recorded", {"equal_weight", "random_industry_neutral", "momentum_baseline", "reversal_baseline", "qlib_alpha158_proxy"}.issubset(baseline_metrics.keys()))
    check("experiment_recorder_complete", recorder_dir.is_dir() and (recorder_dir / "resolved_config.yaml").is_file() and (recorder_dir / "artifact_manifest.json").is_file() and report.get("config_hash"))
    check("research_artifacts_written", all((research_loop_DIR / name).is_file() for name in ["predictions.parquet", "holdings.parquet", "equity_curve.csv", "risk_report.parquet", "backtest_report.html"]))
    check("gold_artifacts_written", not signals.empty and not backtest.empty and not risk_gold.empty)
    check("signals_have_rank_and_research_boundary", not predictions.empty and {"score", "rank", "percentile", "confidence", "research_boundary"}.issubset(predictions.columns) and predictions["research_boundary"].eq(RESEARCH_BOUNDARY).all())
    check("holdings_have_tradeability_cost_capacity", not holdings.empty and {"weight", "transaction_cost_bp", "slippage_model", "capacity_at_1pct_adv"}.issubset(holdings.columns))
    check("risk_report_required_columns", not risk_report.empty and expected_risk_columns.issubset(risk_report.columns))
    check("required_metrics_available", all(_metric_ok(metrics.get(name)) for name in ["IC", "RankIC", "ICIR", "IC_t_stat", "RankIC_t_stat", "TopK_return", "Quantile_spread", "LongShort_spread_research_only", "Turnover", "Cost_adjusted_return", "MaxDrawdown", "Sharpe", "Calmar", "HitRate", "Capacity"]))
    check("qlib_status_or_blocked_reason_recorded", report.get("qlib_status") in {"minimal_qlib_recorder_available", "qlib_workflow_blocked_minimal_recorder_used"} and ((recorder_dir / "qlib_blocked_reason.md").is_file() or report.get("qlib_status") == "minimal_qlib_recorder_available"))

    api_dashboard = client.get("/api/dashboard")
    api_scores = client.get("/api/scores")
    api_backtests = client.get("/api/backtests")
    api_experiments = client.get("/api/experiments")
    check("backend_dashboard_scores_backtests_ready", api_dashboard.status_code == 200 and api_dashboard.json().get("status") == "research_loop_research_loop_ready" and api_scores.status_code == 200 and api_scores.json().get("status") == "research_loop_scores_ready" and api_backtests.status_code == 200 and api_backtests.json().get("status") == "research_loop_backtest_ready")
    check("backend_experiments_ready", api_experiments.status_code == 200 and api_experiments.json().get("status") == "research_loop_experiment_recorder_ready")

    dashboard_page = (ROOT / "frontend" / "src" / "app" / "dashboard" / "page.tsx").read_text(encoding="utf-8")
    scores_page = (ROOT / "frontend" / "src" / "app" / "scores" / "page.tsx").read_text(encoding="utf-8")
    backtests_page = (ROOT / "frontend" / "src" / "app" / "backtests" / "page.tsx").read_text(encoding="utf-8")
    check(
        "frontend_dashboard_scores_backtests_research_loop_ready",
        "/api/" in dashboard_page
        and "/api/scores" in scores_page
        and "/api/backtests" in backtests_page,
    )

    result = {
        "status": "ok" if not failed else "failed",
        "checks": 19,
        "failed": failed,
        "run_id": report.get("run_id"),
        "label_rows": int(len(labels)),
        "prediction_rows": int(len(predictions)),
        "holding_rows": int(len(holdings)),
        "equity_curve_rows": int(report.get("equity_curve_rows", 0)),
        "risk_report_rows": int(len(risk_report)),
        "split_count": report.get("split_count"),
        "feature_count": report.get("feature_count"),
        "lightgbm_status": report.get("lightgbm_status"),
        "qlib_status": report.get("qlib_status"),
        "leakage_check_status": report.get("leakage_check_status"),
        "config_hash": report.get("config_hash"),
        "artifacts": report.get("artifacts", {}),
    }
    report_path = research_loop_DIR / "acceptance_report.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(result, ensure_ascii=False, indent=2, default=_json_default), encoding="utf-8")
    return result


if __name__ == "__main__":
    print(json.dumps(run_acceptance(), ensure_ascii=False, indent=2, default=_json_default))
