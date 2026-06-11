from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

PROJECT_ROOT = Path(__file__).resolve().parents[1]
FRONTEND = PROJECT_ROOT / "frontend" / "src"
APP = FRONTEND / "app"
COMPONENTS = FRONTEND / "components"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_homepage_market_board_sidebar_and_stock_universe_contract_are_ready() -> None:
    home = _read(APP / "page.tsx")
    layout = _read(APP / "layout.tsx")
    css = _read(APP / "globals.css")
    component = _read(COMPONENTS / "MarketOverviewBoard.tsx")
    combined = home + layout + css + component

    assert "MarketOverviewBoard" in home
    assert "沪深300股票全景" in combined
    assert "类似同花顺" in combined
    assert "股票代码" in combined and "股票名称" in combined
    assert "最新价" in combined and "涨跌幅" in combined and "成交额" in combined
    assert "平盘/无变化" in combined and "未定价/停牌" in combined
    assert "breadth_summary" in component and "data_refresh_policy" in component
    assert "每日更新" in combined and "update_daily_market_data.py" in combined
    assert "查看详情" in combined and "/stocks/" in combined
    assert "console-nav-section" in layout
    assert "股票预测选股" in layout
    assert "股票全景" in layout
    assert "因子与模型" in layout


def test_scores_page_renders_top10_multi_horizon_with_names_probabilities_and_detail_links() -> None:
    scores_page = _read(APP / "scores" / "page.tsx")
    component = _read(COMPONENTS / "HorizonProbabilityTable.tsx")
    combined = scores_page + component

    assert "股票预测选股" in combined
    assert "未来1d" in combined and "未来5d" in combined and "未来14d" in combined
    assert "slice(0, 10)" in component
    assert "initialPayload" in component
    assert "loadInitialScoresPayload" in scores_page
    assert "force-dynamic" in scores_page
    assert "stock_name" in component
    assert "candidate_pool" in component and "candidate_summary" in component
    assert "候选池功能已合并到本页" in combined
    assert "研究候选池 Top20" in component
    assert "看回测风险" in component
    assert "probability_up" in component and "probability_down" in component
    assert "上涨概率" in component
    assert "/stocks/" in component


def test_stock_detail_page_shows_kline_style_chart_factors_predictions_and_market_notes() -> None:
    detail_page = _read(APP / "stocks" / "[symbol]" / "page.tsx")
    component = _read(COMPONENTS / "StockDetailPanel.tsx")
    combined = detail_page + component

    assert "StockDetailPanel" in detail_page
    assert "loadInitialStockDetail" in detail_page
    assert "initialPayload" in component
    assert "force-dynamic" in detail_page
    assert "证券软件式个股面板" in combined
    assert "价格折线图" in combined
    assert "证券软件K线形态" in combined
    assert "chart-axis-label" in component
    assert "chart-grid-line" in component
    assert "kline-candle" in component
    assert "legend-close" in component and "legend-ma5" in component and "legend-ma20" in component
    assert "volume-bar--up" in component and "volume-bar--down" in component
    assert "成交量" in combined
    assert "最近因子结果" in combined
    assert "因子是什么" in combined
    assert "干什么用" in combined
    assert "IC / RankIC 怎么看" in combined
    assert "factor-help-panel" in component
    assert "factor-description" in component
    assert "factor-usage" in component
    assert "市场相关资讯" in combined
    assert "1d" in combined and "5d" in combined and "14d" in combined
    assert "research_signals_only_not_investment_advice" in combined


def test_condition_screen_page_and_api_support_custom_multifactor_backtest_table() -> None:
    from backend.app.main import app

    layout = _read(APP / "layout.tsx")
    page = _read(APP / "condition-screen" / "page.tsx")
    component = _read(COMPONENTS / "ConditionScreenTable.tsx")
    combined = layout + page + component

    assert "条件测试" in layout
    assert "/condition-screen" in layout
    assert "条件实验室" in combined
    assert "非ST" in combined
    assert "均线多头排列" in combined
    assert "10个交易日内涨幅大于15%" in combined
    assert "股价在10日均线上" in combined
    assert "市值大于100亿" in combined
    assert "综合条件通过" in combined
    assert "沪深300样本逐行核验" in combined
    assert "3个交易日涨跌幅" not in combined
    assert "5个交易日涨跌幅" not in combined
    assert "10个交易日涨跌幅" not in combined
    assert "待观察" not in combined
    assert "column-filter-input" in component
    assert "numeric-filter-operator" in component
    assert "discrete-filter-select" in component
    assert "factor-column-picker" in component
    assert "available_factor_columns" in component
    assert "column_schema" in component
    assert "ST / *ST 触发条件说明" in combined
    assert "estimated_market_cap_billion" in component
    assert "value_proxy" in component
    assert "quality_proxy" in component
    assert "growth_proxy_20d" in component
    assert "beta_20d" in component
    assert "否" in component

    client = TestClient(app)
    response = client.get("/api/condition-screen")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "condition_screen_ready"
    assert payload["mode"] == "latest_stock_universe_condition_table"
    assert payload["research_boundary"] == "research_signals_only_not_investment_advice"
    assert payload["criteria"]["non_st"]["label"] == "非ST"
    assert payload["criteria"]["ma_bullish"]["label"] == "均线多头排列"
    assert payload["criteria"]["return_10d_gt_15"]["label"] == "10个交易日内涨幅大于15%"
    assert payload["criteria"]["close_above_ma10"]["label"] == "股价在10日均线上"
    assert payload["criteria"]["market_cap_gt_100b"]["label"] == "市值大于100亿"
    assert {"return_3d_forward", "return_5d_forward", "return_10d_forward"}.isdisjoint(set(payload["base_columns"]))
    assert "all_conditions_met" in payload["base_columns"]
    assert "estimated_market_cap_billion" in payload["available_factor_columns"]
    assert "ma250" in payload["available_factor_columns"]
    for financial_factor in ["market_cap_proxy", "float_market_cap_proxy", "value_proxy", "quality_proxy", "growth_proxy_20d", "low_volatility_proxy", "liquidity_proxy", "beta_20d", "beta_60d"]:
        assert financial_factor in payload["available_factor_columns"]
    assert isinstance(payload["rows"], list)
    expected_count = payload["expected_symbol_count"]
    assert expected_count >= 298
    assert payload["row_count"] == len(payload["rows"]) == expected_count
    assert payload["summary"]["sample_count"] == expected_count
    assert payload["summary"]["matched_count"] == sum(1 for row in payload["rows"] if row["all_conditions_met"])
    assert payload["summary"]["latest_signal_date"] == payload["latest_trade_date"]
    if payload.get("raw_latest_trade_date") != payload["latest_trade_date"]:
        assert payload["raw_latest_stock_count"] < expected_count
    assert payload["column_schema"]["close"]["type"] == "number"
    assert "gt" in payload["column_schema"]["close"]["operators"]
    assert payload["column_schema"]["non_st"]["type"] == "boolean"
    assert payload["column_schema"]["industry_name"]["type"] == "category"
    assert payload["column_schema"]["symbol"]["type"] == "text"
    assert "future_return_status" not in payload["summary"]
    assert set(payload["summary"]["displayed_trade_dates"]) <= set(payload["summary"]["data_dates"])
    if payload["rows"]:
        row = payload["rows"][0]
        for field in ["stock_name", "symbol", "trade_date", "non_st", "ma_bullish", "return_10d_gt_15", "close_above_ma10", "market_cap_gt_100b", "all_conditions_met"]:
            assert field in row
        for deleted_field in ["return_3d_forward", "return_5d_forward", "return_10d_forward"]:
            assert deleted_field not in row
        assert any(not row["ma_bullish"] for row in payload["rows"])
        assert any(not row["return_10d_gt_15"] for row in payload["rows"])


def test_market_and_stock_detail_api_payloads_are_real_data_backed() -> None:
    from backend.app.main import app

    client = TestClient(app)
    market = client.get("/api/market")
    assert market.status_code == 200
    payload = market.json()
    assert payload["status"] == "market_universe_ready"
    assert payload["stock_count"] >= 298
    assert len(payload["stocks"]) >= 298
    breadth = payload["breadth_summary"]
    assert breadth["up_count"] + breadth["down_count"] + breadth["flat_count"] + breadth["unknown_count"] == payload["stock_count"]
    assert breadth["flat_count"] >= 0 and breadth["unknown_count"] >= 0
    assert payload["data_refresh_policy"]["frequency"] == "daily_after_market_close"
    assert "scripts/update_daily_market_data.py" in payload["data_refresh_policy"]["command"]
    assert (PROJECT_ROOT / "scripts" / "update_daily_market_data.py").is_file()
    first = payload["stocks"][0]
    for field in ["symbol", "stock_name", "trade_date", "close", "pct_change", "amount", "industry_name"]:
        assert field in first
    bank_row = next(row for row in payload["stocks"] if row["industry_name"] == "银行")
    assert "unknown" not in bank_row["industry_name"].lower()

    symbol = bank_row["symbol"]
    detail = client.get(f"/api/stocks/{symbol}")
    assert detail.status_code == 200
    detail_payload = detail.json()
    assert detail_payload["status"] == "stock_detail_ready"
    assert detail_payload["symbol"] == symbol
    assert detail_payload["stock_name"]
    assert detail_payload["industry_name"] == "银行"
    assert "unknown" not in detail_payload["industry_name"].lower()
    assert len(detail_payload["price_series"]) >= 60
    assert {row["horizon"] for row in detail_payload["predictions"]} >= {"1d", "5d", "14d"}
    assert len(detail_payload["recent_factors"]) >= 5
    assert len(detail_payload["market_notes"]) >= 3
    assert detail_payload["research_boundary"] == "research_signals_only_not_investment_advice"


def test_scores_candidate_pool_and_backtest_risk_dashboard_are_integrated() -> None:
    from backend.app.main import app

    layout = _read(APP / "layout.tsx")
    scores_page = _read(APP / "scores" / "page.tsx")
    candidates_page = _read(APP / "candidates" / "page.tsx")
    backtests_page = _read(APP / "backtests" / "page.tsx")
    risk_component = _read(COMPONENTS / "BacktestRiskDashboard.tsx")
    combined = layout + scores_page + candidates_page + backtests_page + risk_component

    assert "股票预测选股/候选池" in layout
    assert "['候选池', '/candidates']" not in layout
    assert "候选池已放入“股票预测选股”页面" in candidates_page
    assert "/scores#candidate-pool" in candidates_page
    assert "BacktestRiskDashboard" in backtests_page
    assert "risk_summary" in risk_component
    assert "risk_flags" in risk_component
    assert "capacity_curve" in risk_component
    assert "最近30个回测点" in risk_component
    assert "策略回测与风险评估" in risk_component
    assert "回测风险" in combined

    client = TestClient(app)
    scores = client.get("/api/scores")
    assert scores.status_code == 200
    scores_payload = scores.json()
    assert scores_payload["status"] == "research_loop_scores_ready"
    assert scores_payload["candidate_summary"]["candidate_count"] == len(scores_payload["candidate_pool"])
    assert scores_payload["candidate_summary"]["source_horizon"] == "5d"
    assert len(scores_payload["candidate_pool"]) > 0
    assert "candidate_reason" in scores_payload["candidate_pool"][0]

    backtests = client.get("/api/backtests")
    assert backtests.status_code == 200
    backtest_payload = backtests.json()
    assert backtest_payload["status"] == "research_loop_backtest_ready"
    assert "risk_summary" in backtest_payload
    assert "risk_flags" in backtest_payload["risk_summary"]
    assert "capacity_curve" in backtest_payload
    assert "style_attribution" in backtest_payload
    assert "risk_explainers" in backtest_payload
    assert len(backtest_payload["curve_tail"]) <= 30
