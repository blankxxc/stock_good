from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

PROJECT_ROOT = Path(__file__).resolve().parents[1]
FRONTEND = PROJECT_ROOT / "frontend" / "src"
APP = FRONTEND / "app"
COMPONENTS = FRONTEND / "components"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_homepage_market_board_keeps_stock_universe_without_redundant_intro_copy() -> None:
    home = _read(APP / "page.tsx")
    layout = _read(APP / "layout.tsx") + _read(COMPONENTS / "ApplicationShell.tsx")
    css = _read(APP / "globals.css")
    component = _read(COMPONENTS / "MarketOverviewBoard.tsx")
    combined = home + layout + css + component

    assert "MarketOverviewBoard" in home
    assert "home-intro" not in home
    assert "alpha-command-deck" not in home
    assert "market overview binds" not in home
    assert "智能选股平台" not in home
    assert "沪深300股票全景" in combined
    assert "类似同花顺" not in combined
    assert "首页直接展示所有股票" not in combined
    assert "股票代码" in combined and "股票名称" in combined
    assert "最新价" in combined and "涨跌幅" in combined and "成交额" in combined
    assert "平盘/无变化" in combined and "未定价/停牌" in combined
    assert "breadth_summary" in component and "data_refresh_policy" in component
    assert "每日更新" not in combined and "update_daily_market_data.py" not in combined
    assert "查看详情" in combined and "/stocks/" in combined
    assert "console-nav-section" not in layout
    assert "股票预测选股" in layout
    assert "股票全景" in layout
    assert "因子库" in layout and "模型表现" in layout


def test_scores_page_renders_top10_multi_horizon_with_names_probabilities_and_detail_links() -> None:
    scores_page = _read(APP / "scores" / "page.tsx")
    component = _read(COMPONENTS / "HorizonProbabilityTable.tsx")
    combined = scores_page + component

    assert "股票预测选股" in combined
    assert "未来1d" in combined
    assert "未来5d" not in component and "未来14d" not in component
    assert "slice(0, 10)" in component
    assert "selectedCandidateHorizon" in component
    assert "selectedCandidateLimit" in component
    assert "candidate-horizon-select" in component
    assert "candidate-limit-input" in component
    assert 'type="number"' in component
    assert "candidate-limit-select" not in component
    assert "candidateLimitOptions" not in component
    assert "Top数量" in component
    assert "选择周期" in component
    assert "研究候选池 Top{normalizedCandidateLimit}" in component
    assert "研究候选池 Top20" not in component
    assert "initialPayload" in component
    assert "loadInitialScoresPayload" in scores_page
    assert "force-dynamic" in scores_page
    assert "section-heading-row" not in scores_page
    assert "上涨概率排行与研究候选池" not in scores_page
    assert "查看未来1d、未来5d、未来14d 的上涨概率 Top10" not in scores_page
    assert "进入条件选股" not in scores_page
    assert "stock_name" in component
    assert "candidate_pool" in component and "candidate_summary" in component
    assert "payload?.candidate_summary?.pool_definition" not in component
    assert "candidate-workflow" not in component
    assert "next_checks" not in component
    assert "默认取 5d probability_up/rank" not in combined
    assert "默认取模型排名靠前股票" not in combined
    assert "作为后续个股详情、条件测试、回测风险的研究对象" not in combined
    assert "候选池功能已合并到本页" not in combined
    assert "直接读取 /api/scores" not in combined
    assert "terminal-strip" not in scores_page
    assert "ArtifactStatusCard" not in scores_page
    assert "compatibility-checkpoints" not in scores_page
    assert "验收兼容说明" not in scores_page
    assert "API path prefix" not in scores_page
    assert "可追溯字段" not in scores_page
    assert "data_mode" not in scores_page
    assert "multi-horizon probability" not in combined
    assert "看回测风险" in component
    assert "predicted_relative_change_pct" in component
    assert "<tr><th>排名</th><th>股票代码</th><th>股票名称</th><th>预测相对涨跌</th>" in component
    assert "<tr><th>排名</th><th>股票代码</th><th>股票名称</th><th>上涨概率</th><th>下跌概率</th><th>score</th></tr>" not in component
    assert "可切换模型回归输出" in component
    assert "selectedModel" in component
    assert "FinMamba 官方模型" in component
    assert "环境待就绪" in component
    assert "model-selector" in component
    assert "sentiment_event" in component
    assert "情绪/事件融合 LightGBM" in component
    assert "/api/scores?model=" in component
    assert "sentiment-evidence-grid" in component
    assert "prediction_target_date" in component
    assert "样本外 MAE" in component
    assert "/stocks/" in component


def test_stock_detail_page_is_compact_and_chart_points_have_hover_tooltips() -> None:
    detail_page = _read(APP / "stocks" / "[symbol]" / "page.tsx")
    component = _read(COMPONENTS / "StockDetailPanel.tsx")
    combined = detail_page + component

    assert "StockDetailPanel" in detail_page
    assert "loadInitialStockDetail" in detail_page
    assert "initialPayload" in component
    assert "force-dynamic" in detail_page
    assert "证券软件式个股面板" not in combined
    assert "价格折线图、K线、成交量" not in combined
    assert "证券软件K线形态" not in combined
    assert "chart-axis-label" in component
    assert "chart-grid-line" in component
    assert "kline-candle" in component
    assert "chart-hover-column" not in component
    assert "chart-hover-point" not in component
    assert "chart-hover-layer" not in component
    assert "chart-hover-tooltip" in component
    assert "setHoveredPoint" in component
    assert "onMouseEnter={() => setHoveredPoint" in component
    assert "开盘" in component and "最高" in component and "最低" in component and "收盘" in component
    assert "legend-close" in component and "legend-ma5" in component and "legend-ma20" in component
    assert "moving-average-explain" in component
    assert "MA5" in component and "5日均线" in component
    assert "MA20" in component and "20日均线" in component
    assert "短期走势" in component and "中期趋势" in component
    assert "volume-bar--up" in component and "volume-bar--down" in component
    assert "成交量" in combined
    assert "chart-lines-layer" in component
    assert "常显折线" in component
    assert component.index("chart-lines-layer") < component.index("chart-hover-tooltip")
    assert "line-close" in component and "line-ma5" in component and "line-ma20" in component
    assert "security-chart-card--full" in component
    assert "gridColumn: '1 / -1'" in component or "security-chart-card--full" in _read(APP / "globals.css")
    assert "prediction-card--below-chart" in component
    assert "prediction-list-horizontal" in component
    assert "prediction-probability--up" in component
    assert "prediction-probability--down" in component
    assert "prediction-probability--flat" in component
    assert "predictionTone" in component
    assert "最近因子结果" in combined
    assert "factor-filter-panel" in component
    assert "selectedFactorNames" in component
    assert "toggleFactor" in component
    assert "因子筛选" in component
    assert "factor-compact-note" in component
    assert "factor-count-pill" in component
    assert "共" in component and "个因子" in component
    assert "factor-ic-overview" in component
    assert "IC和RankIC含义" in component
    assert "因子值与未来收益" in component
    assert "因子排序与未来收益排序" in component
    assert "factor-quick-row" in component
    assert "factor-stock-value" in component
    assert "factor-meaning" in component
    assert "factorMeaning" in component
    assert "factor-metrics-line" in component
    assert "factor_value" in component
    assert "value_trade_date" in component
    assert "valueInterpretation" in component
    assert "该股取值" in component
    assert "取值日" in component
    assert "含义" in component
    assert "收益表现" in component and "动量" in component and "波动" in component
    assert "参考" in component and "IC" in component and "RankIC" in component
    assert "factorSummary" not in component
    assert "factor-summary" not in component
    assert "factorMetricInterpretation" not in component
    assert "factor-metric-interpretation" not in component
    assert "指标解读" not in component
    assert "简要说明" not in component
    assert "IC 越高" not in component
    assert "正相关" not in component and "反向关系" not in component
    assert "因子是什么" not in component
    assert "干什么用" not in component
    assert "IC / RankIC 怎么看" not in component
    assert "factor-help-panel" not in component
    assert "factor-description" not in component
    assert "factor-usage" not in component
    assert "市场相关资讯" in combined
    assert "1d" in combined and "5d" in combined and "14d" in combined
    assert "research_signals_only_not_investment_advice" not in component


def test_condition_screen_page_and_api_support_custom_multifactor_backtest_table() -> None:
    from backend.app.main import app

    layout = _read(APP / "layout.tsx") + _read(COMPONENTS / "ApplicationShell.tsx")
    page = _read(APP / "condition-screen" / "page.tsx")
    component = _read(COMPONENTS / "ConditionScreenTable.tsx")
    combined = layout + page + component

    assert "条件选股" in layout
    assert "/condition-screen" in layout
    assert "条件实验室" not in page
    assert "Condition Lab" not in page
    assert "沪深300样本逐行核验" not in page
    assert "展示最近可用行情与条件判断" not in page
    assert "terminal-strip" not in page
    assert "FILTER" not in page
    assert "compatibility-checkpoints" not in page
    assert "验收兼容说明" not in page
    assert "data-api-prefix" not in page
    assert "非ST" in combined
    assert "均线多头排列" in combined
    assert "10个交易日内涨幅大于15%" in combined
    assert "股价在10日均线上" in combined
    assert "市值大于100亿" in combined
    assert "综合条件通过" in combined
    assert "condition-rule-card" not in component
    assert "st-rule-card" not in component
    assert "ST / *ST 触发条件说明" not in combined
    assert "3个交易日涨跌幅" not in combined
    assert "5个交易日涨跌幅" not in combined
    assert "10个交易日涨跌幅" not in combined
    assert "待观察" not in combined
    assert "column-filter-input" in component
    assert "numeric-filter-operator" in component
    assert "discrete-filter-select" in component
    assert "factor-column-picker" in component
    assert "available_factor_columns" in component
    assert "available_factor_columns：" not in component
    assert "暂时无法读取 /api/condition-screen" not in component
    assert "data-api-prefix" not in component
    assert "research_signals_only_not_investment_advice" not in component
    assert "column_schema" in component
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
    assert len(payload["available_factor_columns"]) >= 70
    assert len(payload["factor_column_catalog"]) >= len(payload["available_factor_columns"])
    for required_factor in ["return_1d", "return_5d", "return_10d", "momentum_20d", "volatility_20d", "beta_60d", "value_proxy", "quality_proxy", "growth_proxy_20d", "cs_rank_return_20d"]:
        assert required_factor in payload["available_factor_columns"]
    assert isinstance(payload["rows"], list)
    expected_count = payload["expected_symbol_count"]
    assert expected_count >= 298
    assert payload["row_count"] == len(payload["rows"]) == expected_count
    assert payload["summary"]["sample_count"] == expected_count
    assert payload["summary"]["matched_count"] == sum(1 for row in payload["rows"] if row["all_conditions_met"])
    assert payload["summary"]["latest_signal_date"] == payload["latest_trade_date"]
    if payload.get("raw_latest_trade_date") != payload["latest_trade_date"]:
        assert payload["raw_latest_stock_count"] < expected_count
    assert payload["column_schema"]["return_10d"]["type"] == "number"
    assert "gt" in payload["column_schema"]["return_10d"]["operators"]
    assert payload["column_schema"]["volatility_20d"]["type"] == "number"
    assert payload["column_schema"]["beta_60d"]["type"] == "number"
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
    assert {row["horizon"] for row in detail_payload["predictions"]} == {"1d"}
    assert "predicted_relative_change_pct" in detail_payload["predictions"][0]
    assert detail_payload["factor_count"] >= 70
    assert len(detail_payload["recent_factors"]) == detail_payload["factor_count"]
    assert len(detail_payload["recent_factors"]) >= 70
    factor_names = {row["factor_name"] for row in detail_payload["recent_factors"]}
    assert {"return_1d", "return_5d", "momentum_20d", "volatility_20d", "beta_60d"} <= factor_names
    first_factor = detail_payload["recent_factors"][0]
    for field in ["factor_name", "factor_value", "value_trade_date", "value_interpretation"]:
        assert field in first_factor
    assert first_factor["value_trade_date"] == detail_payload["latest_trade_date"]
    assert isinstance(first_factor["factor_value"], (int, float))
    assert "该股" in first_factor["value_interpretation"]
    assert len(first_factor["value_interpretation"]) <= 48
    assert "当前这只股票" not in first_factor["value_interpretation"]
    assert len(detail_payload["market_notes"]) >= 3
    assert detail_payload["research_boundary"] == "research_signals_only_not_investment_advice"


def test_scores_candidate_pool_and_backtest_risk_dashboard_are_integrated() -> None:
    from backend.app.main import app

    layout = _read(APP / "layout.tsx") + _read(COMPONENTS / "ApplicationShell.tsx")
    scores_page = _read(APP / "scores" / "page.tsx")
    candidates_page = _read(APP / "candidates" / "page.tsx")
    backtests_page = _read(APP / "backtests" / "page.tsx")
    risk_component = _read(COMPONENTS / "BacktestRiskDashboard.tsx")
    combined = layout + scores_page + candidates_page + backtests_page + risk_component

    assert "股票预测选股" in layout
    assert "['候选池', '/candidates']" not in layout
    assert "候选池已放入“股票预测选股”页面" in candidates_page
    assert "/scores#candidate-pool" in candidates_page
    assert "BacktestRiskDashboard" in backtests_page
    assert "backtests-heading" not in backtests_page
    assert "策略回测、风险指标、容量曲线和风险归因" not in backtests_page
    assert "聚焦回答：历史怎么亏" not in backtests_page
    assert "risk_summary" in risk_component
    assert "risk_flags" in risk_component
    assert "capacity_curve" in risk_component
    assert "最近30个回测点" in risk_component
    assert "策略回测与风险评估" not in risk_component
    assert "risk command center" not in risk_component
    assert "run_id <b>" not in risk_component
    assert "portfolio <b>" not in risk_component
    assert "benchmark <b>" not in risk_component
    assert "latest <b>" not in risk_component
    assert "data-api-fields" not in risk_component
    assert "客户端暂时无法读取 /api/backtests" not in risk_component
    assert "数据覆盖" not in risk_component
    assert "equity_curve_rows" not in risk_component
    assert "risk_report_rows" not in risk_component
    assert "风险看板" in risk_component
    assert "历史表现、回撤压力和当前风控状态" in risk_component
    assert "risk-help-panel" not in risk_component
    assert "净值看收益路径，回撤看历史最大亏损压力。" in risk_component
    assert "主动风险衡量策略相对基准多赚/少赚，以及偏离基准的波动。" in risk_component
    assert "相对收益" in risk_component
    assert "策略比基准多赚或少赚了多少。" in risk_component
    assert "跟踪误差" in risk_component
    assert "策略相对基准偏离得有多剧烈。" in risk_component
    assert "信息比率" in risk_component
    assert "每承担一份主动风险换来多少超额收益。" in risk_component
    assert "对基准 Beta" in risk_component
    assert "策略跟随基准涨跌的敏感程度。" in risk_component
    assert "主动最大回撤" in risk_component
    assert "相对基准时，历史最深亏损压力。" in risk_component
    assert "执行损耗" in risk_component
    assert "交易执行和成本拖累了多少收益。" in risk_component
    for raw_risk_label in ["active_return", "tracking_error", "information_ratio", "beta_to_benchmark", "active_max_drawdown", "implementation_shortfall"]:
        assert f"<dt>{raw_risk_label}</dt>" not in risk_component
    assert "容量曲线估算不同参与率下，策略大概能承载多少资金。" in risk_component
    assert "Baseline 是用简单基准策略对照当前策略，避免只看单一结果。" in risk_component
    assert "风格暴露看收益更像哪类因子，行业归因看收益主要来自哪些行业。" in risk_component
    assert "risk-attribution-section" in risk_component
    assert "风格暴露 Top8" in risk_component
    assert "行业归因 Top8" in risk_component
    assert "回测风险" in combined

    client = TestClient(app)
    scores = client.get("/api/scores")
    assert scores.status_code == 200
    scores_payload = scores.json()
    assert scores_payload["status"] == "research_loop_scores_ready"
    assert scores_payload["candidate_summary"]["candidate_count"] == len(scores_payload["candidate_pool"])
    assert scores_payload["candidate_summary"]["source_horizon"] == "1d"
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
