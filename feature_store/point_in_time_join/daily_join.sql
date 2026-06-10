-- foundation stub: factor_store turns this into executable DuckDB/Spark SQL.
select *
from model_training_sample s
join factor_daily_panel f
  on s.symbol = f.symbol
 and f.trade_date <= s.trade_date
where f.compute_time <= s.trade_date;
