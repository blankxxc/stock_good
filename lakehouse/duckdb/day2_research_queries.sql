-- Day 2 local research path: Parquet + DuckDB
-- Example usage from project root:
--   duckdb -c ".read lakehouse/duckdb/day2_research_queries.sql"

CREATE OR REPLACE VIEW dwd_stock_daily_bar AS
SELECT * FROM read_parquet('data/silver/dwd_stock_daily_bar/**/*.parquet');

CREATE OR REPLACE VIEW factor_daily_panel AS
SELECT * FROM read_parquet('data/gold/factor_daily_panel/**/*.parquet');

CREATE OR REPLACE VIEW ads_dashboard_summary AS
SELECT * FROM read_parquet('data/ads/ads_dashboard_summary/*.parquet');

SELECT trade_date, symbol, close, volume
FROM dwd_stock_daily_bar
ORDER BY trade_date, symbol;
