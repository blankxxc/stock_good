CREATE TABLE IF NOT EXISTS ads_dashboard_summary (
    data_version String,
    latest_trade_date Date,
    total_rows UInt64,
    snapshot_count UInt64,
    authorized_source_count UInt64,
    restricted_or_blocked UInt64,
    research_boundary String
) ENGINE = MergeTree ORDER BY (data_version, latest_trade_date);

CREATE TABLE IF NOT EXISTS ads_score_latest (
    trade_date Date,
    symbol String,
    score Float64,
    rank UInt32,
    percentile Float64,
    model_version String,
    data_version String,
    factor_version String,
    label_version String,
    trace_id String
) ENGINE = MergeTree ORDER BY (trade_date, rank, symbol);

CREATE TABLE IF NOT EXISTS ads_backtest_summary (
    run_id String,
    start_date Date,
    end_date Date,
    topk UInt32,
    long_short_return Float64,
    turnover Float64,
    max_drawdown Float64,
    sharpe Float64,
    data_version String,
    factor_version String,
    model_version String
) ENGINE = MergeTree ORDER BY (data_version, run_id);
