from __future__ import annotations

import pandas as pd


def test_financial_lexicon_and_event_type_are_deterministic() -> None:
    from data.adapters.sentiment_event_data import (
        classify_event_type,
        score_chinese_financial_sentiment,
    )

    positive, positive_hits, negative_hits = score_chinese_financial_sentiment(
        "公司业绩增长超预期并宣布回购"
    )
    negative, _, negative_term_hits = score_chinese_financial_sentiment(
        "公司亏损下滑并收到监管处罚"
    )
    assert positive > 0 and positive_hits > negative_hits
    assert negative < 0 and negative_term_hits > 0
    assert classify_event_type("公司发布年度业绩预告，净利润增长") == "earnings"
    assert classify_event_type("证监会立案调查并作出处罚") == "regulation"


def test_news_availability_maps_to_the_feature_date_before_next_open() -> None:
    from models.sentiment_event_fusion import _map_news_to_feature_dates

    trading_dates = [
        pd.Timestamp("2026-07-24"),
        pd.Timestamp("2026-07-27"),
        pd.Timestamp("2026-07-28"),
    ]
    news = pd.DataFrame(
        [
            {
                "event_id": "weekend",
                "symbol": "600000.SH",
                "available_time": "2026-07-26T12:00:00+08:00",
                "sentiment_score": 0.5,
                "source_authority_weight": 0.8,
                "event_type": "macro",
            },
            {
                "event_id": "monday-session",
                "symbol": "600000.SH",
                "available_time": "2026-07-27T10:00:00+08:00",
                "sentiment_score": -0.5,
                "source_authority_weight": 0.8,
                "event_type": "regulation",
            },
        ]
    )

    mapped = _map_news_to_feature_dates(news, trading_dates).set_index("event_id")
    assert mapped.loc["weekend", "feature_trade_date"] == "2026-07-24"
    assert mapped.loc["monday-session", "feature_trade_date"] == "2026-07-27"


def test_market_sentiment_panel_uses_only_same_or_past_market_rows() -> None:
    from data.adapters.sentiment_event_data import build_market_sentiment_panel

    dates = pd.date_range("2026-01-05", periods=30, freq="B")
    rows = []
    for symbol, offset in (("600000.SH", 0.0), ("000001.SZ", 0.2), ("300001.SZ", -0.1)):
        for index, date in enumerate(dates):
            close = 10.0 + offset + index * 0.03
            rows.append(
                {
                    "trade_date": date,
                    "symbol": symbol,
                    "close": close,
                    "amount": 1_000_000 + index * 10_000,
                    "turnover_rate": 1.0 + index * 0.01,
                }
            )
    market = pd.DataFrame(rows)
    original = build_market_sentiment_panel(market)
    changed = market.copy()
    changed.loc[changed["trade_date"].eq(dates[-1]), "close"] *= 1.5
    changed_panel = build_market_sentiment_panel(changed)

    columns = ["market_sentiment_proxy", "risk_appetite_proxy"]
    pd.testing.assert_frame_equal(original.iloc[:-1][columns], changed_panel.iloc[:-1][columns])
    assert original.iloc[-1]["market_sentiment_proxy"] != changed_panel.iloc[-1]["market_sentiment_proxy"]
