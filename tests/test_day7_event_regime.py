from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
from fastapi.testclient import TestClient

PROJECT_ROOT = Path(__file__).resolve().parents[1]
RESEARCH_BOUNDARY = "research_signals_only_not_investment_advice"


def _ensure_day7() -> dict:
    from models.day7_event_regime_ablation import run_day7_event_regime_pipeline

    return run_day7_event_regime_pipeline(write_outputs=True)


def _read_parquet_dir(path: Path) -> pd.DataFrame:
    files = sorted(path.glob("**/*.parquet"))
    assert files, f"no parquet files under {path}"
    return pd.concat([pd.read_parquet(file) for file in files], ignore_index=True, sort=False)


def test_day7_event_documents_and_entity_mapping_are_ready():
    report = _ensure_day7()
    assert report["status"] == "ok"
    assert report["event_document_rows"] >= 12
    assert report["announcement_document_rows"] >= 6
    assert report["entity_mapping_rows"] >= 20
    assert report["leakage_check_status"] == "passed"

    news = _read_parquet_dir(PROJECT_ROOT / "data" / "silver" / "news_document")
    ann = _read_parquet_dir(PROJECT_ROOT / "data" / "silver" / "announcement_document")
    mapping = _read_parquet_dir(PROJECT_ROOT / "data" / "silver" / "entity_symbol_mapping")
    required_doc_cols = {"document_id", "publish_time", "available_time", "source", "title", "content", "license_id", "research_boundary"}
    assert required_doc_cols.issubset(news.columns)
    assert required_doc_cols.issubset(ann.columns)
    assert {"entity_name", "symbol", "mapping_confidence", "as_of_date", "available_time"}.issubset(mapping.columns)
    assert pd.to_datetime(news["available_time"], utc=True, format="mixed").ge(pd.to_datetime(news["publish_time"], utc=True, format="mixed")).all()
    assert pd.to_datetime(ann["available_time"], utc=True, format="mixed").ge(pd.to_datetime(ann["publish_time"], utc=True, format="mixed")).all()
    assert news["research_boundary"].eq(RESEARCH_BOUNDARY).all()


def test_day7_financial_text_event_factor_panels_have_time_semantics():
    report = _ensure_day7()
    assert report["text_model_status"] == "lexicon_finbert_compatible_baseline_ready"
    assert report["event_factor_rows"] > 0

    event_result = _read_parquet_dir(PROJECT_ROOT / "data" / "silver" / "event_extraction_result")
    dwd_news = _read_parquet_dir(PROJECT_ROOT / "data" / "silver" / "dwd_news_event")
    dwd_ann = _read_parquet_dir(PROJECT_ROOT / "data" / "silver" / "dwd_announcement_event")
    event_factors = _read_parquet_dir(PROJECT_ROOT / "data" / "gold" / "factor_news_sentiment_panel")

    assert {"sentiment_score", "event_type", "source_authority_weight", "novelty_score", "impact_scope"}.issubset(event_result.columns)
    assert set(event_result["impact_scope"].astype(str)).issubset({"single_stock", "industry", "concept", "supply_chain", "market"})
    assert {"event_decay_5m", "event_decay_1h", "event_decay_1d", "event_decay_5d"}.issubset(event_result.columns)
    assert {"publish_time", "available_time", "symbol", "event_type", "sentiment_score"}.issubset(dwd_news.columns)
    assert {"publish_time", "available_time", "symbol", "event_type", "sentiment_score"}.issubset(dwd_ann.columns)
    assert pd.to_datetime(event_factors["available_time"], utc=True).le(pd.to_datetime(event_factors["prediction_time"], utc=True)).all()

    required_factors = {
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
    assert required_factors.issubset(set(event_factors["factor_name"].astype(str)))
    assert event_factors["leakage_check_status"].eq("passed").all()


def test_day7_market_regime_features_and_ablation_are_ready():
    report = _ensure_day7()
    assert report["market_regime_rows"] > 0
    assert report["enhanced_feature_rows"] > 0
    assert report["ablation_status"] in {"lightgbm_smoke_trained", "linear_fallback_smoke_trained"}

    market = _read_parquet_dir(PROJECT_ROOT / "data" / "gold" / "factor_market_regime_panel")
    feature = _read_parquet_dir(PROJECT_ROOT / "data" / "gold" / "model_feature_matrix_wide_day7")
    ablation = json.loads((PROJECT_ROOT / "reports" / "day7" / "event_regime_ablation_report.json").read_text(encoding="utf-8"))

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
    assert required_market.issubset(market.columns)
    assert market["regime_feature_role"].eq("ex_ante_model_feature").all()
    assert market["ex_post_regime_label_role"].eq("report_only_not_training_feature").all()
    assert pd.to_datetime(market["available_time"], utc=True).le(pd.to_datetime(market["prediction_time"], utc=True)).all()

    for col in ["news_sentiment_1d", "market_breadth", "risk_appetite_proxy", "event_decay_1d"]:
        assert col in feature.columns
    expected_configs = {
        "base_price_volume",
        "base_plus_market_regime",
        "base_plus_news_event",
        "base_plus_relation_spillover",
        "base_plus_market_news_relation",
        "full_minus_market_regime",
        "full_minus_news_event",
        "full_minus_relation_spillover",
    }
    assert expected_configs.issubset(set(ablation["configs"].keys()))
    assert ablation["leakage_check_status"] == "passed"


def test_day7_backend_frontend_and_acceptance_are_ready():
    result = _ensure_day7()
    from backend.app.main import app

    client = TestClient(app)
    factors = client.get("/api/factors")
    health = client.get("/health")
    assert factors.status_code == 200
    assert factors.json()["event_regime"]["status"] == "day7_event_regime_ready"
    assert factors.json()["event_regime"]["latest_available_time"] == result["latest_available_time"]
    assert health.status_code == 200
    assert health.json()["modules"]["event_regime"] == "day7_event_market_regime_ablation_ready"

    page = (PROJECT_ROOT / "frontend" / "src" / "app" / "factors" / "page.tsx").read_text(encoding="utf-8")
    assert "Day 7" in page
    assert "事件因子" in page
    assert "market regime" in page
    assert "publish_time / available_time" in page
    assert "/api/factors" in page

    from scripts.check_day7_acceptance import run_acceptance

    acceptance = run_acceptance()
    assert acceptance["status"] == "ok"
    assert acceptance["checks"] == 18
    assert acceptance["failed"] == []
