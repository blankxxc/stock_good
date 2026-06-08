-- Day 4 local DuckDB report/API helper queries.
-- These queries operate on generated local parquet artifacts and never imply real-time trading advice.

-- Factor catalog coverage by category.
select
  category,
  count(distinct factor_name) as factor_count,
  count(*) as non_null_observations,
  min(trade_date) as first_trade_date,
  max(trade_date) as last_trade_date
from read_parquet('data/gold/factor_daily_panel_long/**/*.parquet')
group by category
order by factor_count desc, category;

-- Feature matrix readiness.
select
  count(*) as feature_matrix_rows,
  count(distinct symbol) as symbol_count,
  min(trade_date) as first_trade_date,
  max(trade_date) as last_trade_date,
  any_value(feature_set_version) as feature_set_version
from read_parquet('data/gold/model_feature_matrix_wide/**/*.parquet');

-- Factor card data for the website/API layer.
select
  factor_name,
  category,
  count(*) as non_null_observations,
  avg(factor_value) as mean_value,
  stddev(factor_value) as std_value,
  min(factor_value) as min_value,
  max(factor_value) as max_value,
  any_value(factor_version) as factor_version
from read_parquet('data/gold/factor_daily_panel_long/**/*.parquet')
group by factor_name, category
order by non_null_observations desc, factor_name
limit 100;

-- Risk exposure coverage.
select
  risk_factor_name,
  count(*) as exposure_rows,
  count(distinct symbol) as symbol_count,
  min(trade_date) as first_trade_date,
  max(trade_date) as last_trade_date,
  any_value(version) as version
from read_parquet('data/gold/risk_factor_exposure/**/*.parquet')
group by risk_factor_name
order by exposure_rows desc, risk_factor_name;
