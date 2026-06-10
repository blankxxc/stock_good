from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

RESEARCH_BOUNDARY = "research_signals_only_not_investment_advice"
event_regime_DIR = ROOT / "reports" / "event_regime"


def _json_default(value: Any) -> Any:
    try:
        if pd.isna(value):
            return None
    except Exception:
        pass
    return str(value)


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _read_parquet_dir(path: Path) -> pd.DataFrame:
    files = sorted(path.glob("**/*.parquet"))
    if not files:
        return pd.DataFrame()
    return pd.concat([pd.read_parquet(file) for file in files], ignore_index=True, sort=False)


def run_acceptance() -> dict[str, Any]:
    from backend.app.main import app
    from fastapi.testclient import TestClient
    from models.event_regime_event_regime_ablation import run_event_regime_event_regime_pipeline

    report = run_event_regime_event_regime_pipeline(write_outputs=True)
    news = _read_parquet_dir(ROOT / "data" / "silver" / "news_document")
    ann = _read_parquet_dir(ROOT / "data" / "silver" / "announcement_document")
    events = _read_parquet_dir(ROOT / "data" / "silver" / "event_extraction_result")
    event_factors = _read_parquet_dir(ROOT / "data" / "gold" / "factor_news_sentiment_panel")
    market = _read_parquet_dir(ROOT / "data" / "gold" / "factor_market_regime_panel")
    feature = _read_parquet_dir(ROOT / "data" / "gold" / "model_feature_matrix_wide_event_regime")
    ablation = _read_json(event_regime_DIR / "event_regime_ablation_report.json")
    client = TestClient(app)
    api_factors = client.get("/api/factors")

    failed: list[str] = []

    def check(name: str, condition: bool) -> None:
        if not condition:
            failed.append(name)

    required_event_factors = {
        "news_sentiment_1d",
        "news_sentiment_3d",
        "news_sentiment_5d",
        "announcement_sentiment",
        "event_count",
        "negative_event_count",
        "source_weighted_sentiment",
        "novelty_score",
        "event_authority_score",
        "event_decay_5m",
        "event_decay_1h",
        "event_decay_1d",
        "event_decay_5d",
        "policy_event_score",
        "macro_event_score",
    }
    required_market = {
        "market_breadth",
        "market_ret_1d",
        "market_ret_5d",
        "market_ret_20d",
        "market_vol_20d",
        "market_drawdown_20d",
        "limit_up_count",
        "limit_down_count",
        "amount_percentile_252d",
        "small_vs_large_return",
        "growth_vs_value_return",
        "industry_dispersion",
        "northbound_flow_zscore",
        "liquidity_regime",
        "risk_appetite_proxy",
        "ex_ante_regime_feature",
        "ex_post_regime_label",
    }
    expected_ablation = {
        "base_price_volume",
        "base_plus_market_regime",
        "base_plus_news_event",
        "base_plus_relation_spillover",
        "base_plus_market_news_relation",
        "full_minus_market_regime",
        "full_minus_news_event",
        "full_minus_relation_spillover",
    }

    check("sample_news_and_announcement_documents_ingested", not news.empty and not ann.empty and len(news) >= 12 and len(ann) >= 6)
    check("publish_available_time_no_travel", not news.empty and pd.to_datetime(news["available_time"], utc=True, format="mixed").ge(pd.to_datetime(news["publish_time"], utc=True, format="mixed")).all() and pd.to_datetime(ann["available_time"], utc=True, format="mixed").ge(pd.to_datetime(ann["publish_time"], utc=True, format="mixed")).all())
    check("finbert_compatible_baseline_ready", report.get("text_model_status") == "lexicon_finbert_compatible_baseline_ready")
    check("event_extraction_fields_ready", not events.empty and {"sentiment_score", "event_type", "source_authority_weight", "novelty_score", "impact_scope"}.issubset(events.columns))
    check("event_decay_features_ready", not events.empty and {"event_decay_5m", "event_decay_1h", "event_decay_1d", "event_decay_5d"}.issubset(events.columns))
    check("event_factor_panel_written", not event_factors.empty and required_event_factors.issubset(set(event_factors.get("factor_name", pd.Series(dtype=str)).astype(str))))
    check("event_factor_time_semantics", not event_factors.empty and pd.to_datetime(event_factors["available_time"], utc=True).le(pd.to_datetime(event_factors["prediction_time"], utc=True)).all())
    check("market_regime_panel_written", not market.empty and required_market.issubset(market.columns))
    check("market_regime_roles_separated", not market.empty and market["regime_feature_role"].eq("ex_ante_model_feature").all() and market["ex_post_regime_label_role"].eq("report_only_not_training_feature").all())
    check("enhanced_model_feature_matrix_written", not feature.empty and {"news_sentiment_1d", "market_breadth", "risk_appetite_proxy", "event_decay_1d"}.issubset(feature.columns))
    check("lightgbm_or_smoke_training_done", report.get("ablation_status") in {"lightgbm_smoke_trained", "linear_fallback_smoke_trained"})
    check("ablation_report_written", bool(ablation) and expected_ablation.issubset(set(ablation.get("configs", {}).keys())))
    check("ablation_has_no_time_leakage", ablation.get("leakage_check_status") == "passed" and report.get("leakage_check_status") == "passed")
    check("backend_factors_api_has_event_regime_payload", api_factors.status_code == 200 and api_factors.json().get("event_regime", {}).get("status") == "event_regime_event_regime_ready")
    factors_page = (ROOT / "frontend" / "src" / "app" / "factors" / "page.tsx").read_text(encoding="utf-8")
    check("frontend_factors_page_event_regime_ready", "event_regime" in factors_page and "事件因子" in factors_page and "market regime" in factors_page and "publish_time / available_time" in factors_page)
    check("research_boundary_present", report.get("research_boundary") == RESEARCH_BOUNDARY and (not event_factors.empty and event_factors["research_boundary"].eq(RESEARCH_BOUNDARY).all()))
    check("artifacts_manifest_present", bool(report.get("artifacts")) and (event_regime_DIR / "event_regime_event_regime_report.json").is_file())
    check("report_counts_positive", report.get("event_factor_rows", 0) > 0 and report.get("market_regime_rows", 0) > 0 and report.get("enhanced_feature_rows", 0) > 0)

    result = {
        "status": "ok" if not failed else "failed",
        "checks": 18,
        "failed": failed,
        "text_model_status": report.get("text_model_status"),
        "event_factor_rows": report.get("event_factor_rows"),
        "market_regime_rows": report.get("market_regime_rows"),
        "enhanced_feature_rows": report.get("enhanced_feature_rows"),
        "ablation_status": report.get("ablation_status"),
        "latest_available_time": report.get("latest_available_time"),
        "artifacts": report.get("artifacts", {}),
    }
    event_regime_DIR.mkdir(parents=True, exist_ok=True)
    (event_regime_DIR / "acceptance_report.json").write_text(json.dumps(result, ensure_ascii=False, indent=2, default=_json_default), encoding="utf-8")
    return result


if __name__ == "__main__":
    print(json.dumps(run_acceptance(), ensure_ascii=False, indent=2, default=_json_default))
