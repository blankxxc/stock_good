# stock_good 数仓分层表字段说明

本文档按 ODS / DWD / DWS / ADS 分层整理当前项目实际存在的数据表，并对每个字段做简要说明。

## 阅读提示

- `available_time <= prediction_time` 是防未来函数的核心约束。
- DWS 中的 `forward_return`、`up_label`、`label_*` 等字段属于研究评估标签，不应作为真实选股页面的筛选条件直接展示。
- `trace_id`、各类 `*_version` 字段用于数据血缘、复现实验和版本治理。

## ODS / Bronze

原始数据入湖层：保留源数据原貌，并补充来源、版本、入库时间、可用时间、血缘字段。

### ods_announcement_raw

用途：公告原始事件表，用于公告事件、公告情绪和 RAG 证据。

| 列名 | 简单说明 |
|---|---|
| `event_id` | 事件 ID。 |
| `publish_time` | 数据源发布时间。 |
| `available_time` | 系统/模型可用该数据的时间，防未来函数关键字段。 |
| `symbol` | 股票代码。 |
| `announcement_type` | 项目当前数据资产字段。 |
| `sentiment` | 情绪标签。 |
| `confidence` | 置信度。 |
| `source` | 数据来源。 |
| `source_version` | 源数据版本。 |
| `schema_version` | 表结构版本。 |
| `data_version` | 数据版本。 |
| `ingest_time` | 入库时间。 |
| `trace_id` | 数据血缘追踪 ID。 |
| `ods_table` | 来源 ODS 表名。 |
| `ingest_date` | 入湖日期分区。 |

### ods_financial_statement_raw

用途：财报原始明细表，采用 item_name/item_value 长表结构，是基本面因子来源。

| 列名 | 简单说明 |
|---|---|
| `symbol` | 股票代码。 |
| `report_period` | 财报报告期。 |
| `announce_time` | 公告/财报披露时间。 |
| `statement_type` | 报表类型。 |
| `item_name` | 财务科目名称。 |
| `item_value` | 财务科目值。 |
| `publish_time` | 数据源发布时间。 |
| `source` | 数据来源。 |
| `source_version` | 源数据版本。 |
| `schema_version` | 表结构版本。 |
| `data_version` | 数据版本。 |
| `ingest_time` | 入库时间。 |
| `available_time` | 系统/模型可用该数据的时间，防未来函数关键字段。 |
| `trace_id` | 数据血缘追踪 ID。 |
| `ods_table` | 来源 ODS 表名。 |
| `ingest_date` | 入湖日期分区。 |

### ods_fund_flow_raw

用途：资金流原始表，用于主力净流入和资金行为类因子。

| 列名 | 简单说明 |
|---|---|
| `trade_date` | 交易日期。 |
| `symbol` | 股票代码。 |
| `main_net_inflow` | 项目当前数据资产字段。 |
| `source` | 数据来源。 |
| `source_version` | 源数据版本。 |
| `schema_version` | 表结构版本。 |
| `data_version` | 数据版本。 |
| `ingest_time` | 入库时间。 |
| `available_time` | 系统/模型可用该数据的时间，防未来函数关键字段。 |
| `trace_id` | 数据血缘追踪 ID。 |
| `ods_table` | 来源 ODS 表名。 |
| `ingest_date` | 入湖日期分区。 |

### ods_macro_raw

用途：宏观事件/指标原始表，用于市场 regime、宏观事件和风险偏好因子。

| 列名 | 简单说明 |
|---|---|
| `event_id` | 事件 ID。 |
| `event_time` | 事件发生时间或行情 bar 时间。 |
| `publish_time` | 数据源发布时间。 |
| `available_time` | 系统/模型可用该数据的时间，防未来函数关键字段。 |
| `event_type` | 事件类型。 |
| `indicator_name` | 项目当前数据资产字段。 |
| `indicator_value` | 项目当前数据资产字段。 |
| `source` | 数据来源。 |
| `source_version` | 源数据版本。 |
| `schema_version` | 表结构版本。 |
| `data_version` | 数据版本。 |
| `ingest_time` | 入库时间。 |
| `trace_id` | 数据血缘追踪 ID。 |
| `ods_table` | 来源 ODS 表名。 |
| `ingest_date` | 入湖日期分区。 |

### ods_market_daily_raw

用途：日频行情原始表，作为日频因子、标签、回测的基础输入。

| 列名 | 简单说明 |
|---|---|
| `trade_date` | 交易日期。 |
| `symbol` | 股票代码。 |
| `open` | 开盘价。 |
| `high` | 最高价。 |
| `low` | 最低价。 |
| `close` | 收盘价。 |
| `volume` | 成交量。 |
| `amount` | 成交额。 |
| `event_time` | 事件发生时间或行情 bar 时间。 |
| `publish_time` | 数据源发布时间。 |
| `source` | 数据来源。 |
| `source_version` | 源数据版本。 |
| `schema_version` | 表结构版本。 |
| `data_version` | 数据版本。 |
| `ingest_time` | 入库时间。 |
| `available_time` | 系统/模型可用该数据的时间，防未来函数关键字段。 |
| `trace_id` | 数据血缘追踪 ID。 |
| `ods_table` | 来源 ODS 表名。 |
| `ingest_date` | 入湖日期分区。 |

### ods_market_minute_raw

用途：分钟行情原始表，用于分钟因子、实时特征和回放验证。

| 列名 | 简单说明 |
|---|---|
| `trade_date` | 交易日期。 |
| `symbol` | 股票代码。 |
| `event_time` | 事件发生时间或行情 bar 时间。 |
| `open` | 开盘价。 |
| `high` | 最高价。 |
| `low` | 最低价。 |
| `close` | 收盘价。 |
| `volume` | 成交量。 |
| `amount` | 成交额。 |
| `vwap` | 成交均价。 |
| `source` | 数据来源。 |
| `source_version` | 源数据版本。 |
| `schema_version` | 表结构版本。 |
| `data_version` | 数据版本。 |
| `ingest_time` | 入库时间。 |
| `available_time` | 系统/模型可用该数据的时间，防未来函数关键字段。 |
| `trace_id` | 数据血缘追踪 ID。 |
| `ods_table` | 来源 ODS 表名。 |
| `ingest_date` | 入湖日期分区。 |

### ods_market_tick_raw

用途：tick 行情原始表，用于盘口、微观结构和实时因子研究。

| 列名 | 简单说明 |
|---|---|
| `trade_date` | 交易日期。 |
| `symbol` | 股票代码。 |
| `event_time` | 事件发生时间或行情 bar 时间。 |
| `open` | 开盘价。 |
| `high` | 最高价。 |
| `low` | 最低价。 |
| `close` | 收盘价。 |
| `volume` | 成交量。 |
| `amount` | 成交额。 |
| `vwap` | 成交均价。 |
| `price` | 最新成交价。 |
| `bid_price` | 买盘价格。 |
| `ask_price` | 卖盘价格。 |
| `source` | 数据来源。 |
| `source_version` | 源数据版本。 |
| `schema_version` | 表结构版本。 |
| `data_version` | 数据版本。 |
| `ingest_time` | 入库时间。 |
| `available_time` | 系统/模型可用该数据的时间，防未来函数关键字段。 |
| `trace_id` | 数据血缘追踪 ID。 |
| `ods_table` | 来源 ODS 表名。 |
| `ingest_date` | 入湖日期分区。 |

### ods_news_raw

用途：新闻原始事件表，用于新闻情绪、事件因子和 RAG 文档入口。

| 列名 | 简单说明 |
|---|---|
| `event_id` | 事件 ID。 |
| `event_time` | 事件发生时间或行情 bar 时间。 |
| `publish_time` | 数据源发布时间。 |
| `available_time` | 系统/模型可用该数据的时间，防未来函数关键字段。 |
| `title` | 标题。 |
| `content_hash` | 内容哈希，用于去重和血缘。 |
| `related_symbols` | 关联股票列表。 |
| `related_industries` | 关联行业列表。 |
| `event_type` | 事件类型。 |
| `sentiment` | 情绪标签。 |
| `confidence` | 置信度。 |
| `source` | 数据来源。 |
| `source_version` | 源数据版本。 |
| `schema_version` | 表结构版本。 |
| `data_version` | 数据版本。 |
| `ingest_time` | 入库时间。 |
| `trace_id` | 数据血缘追踪 ID。 |
| `ods_table` | 来源 ODS 表名。 |
| `ingest_date` | 入湖日期分区。 |

### ods_northbound_raw

用途：北向资金原始表，用于外资流入、北向持仓类因子，并受许可证治理约束。

| 列名 | 简单说明 |
|---|---|
| `trade_date` | 交易日期。 |
| `symbol` | 股票代码。 |
| `northbound_net_buy` | 项目当前数据资产字段。 |
| `license_status` | 授权状态。 |
| `source` | 数据来源。 |
| `source_version` | 源数据版本。 |
| `schema_version` | 表结构版本。 |
| `data_version` | 数据版本。 |
| `ingest_time` | 入库时间。 |
| `available_time` | 系统/模型可用该数据的时间，防未来函数关键字段。 |
| `trace_id` | 数据血缘追踪 ID。 |
| `ods_table` | 来源 ODS 表名。 |
| `ingest_date` | 入湖日期分区。 |

### ods_orderbook_raw

用途：盘口原始表，用于买卖盘压力、价差、订单簿不平衡等因子。

| 列名 | 简单说明 |
|---|---|
| `trade_date` | 交易日期。 |
| `symbol` | 股票代码。 |
| `event_time` | 事件发生时间或行情 bar 时间。 |
| `open` | 开盘价。 |
| `high` | 最高价。 |
| `low` | 最低价。 |
| `close` | 收盘价。 |
| `volume` | 成交量。 |
| `amount` | 成交额。 |
| `vwap` | 成交均价。 |
| `bid_volume` | 买盘数量。 |
| `ask_volume` | 卖盘数量。 |
| `bid_price` | 买盘价格。 |
| `ask_price` | 卖盘价格。 |
| `source` | 数据来源。 |
| `source_version` | 源数据版本。 |
| `schema_version` | 表结构版本。 |
| `data_version` | 数据版本。 |
| `ingest_time` | 入库时间。 |
| `available_time` | 系统/模型可用该数据的时间，防未来函数关键字段。 |
| `trace_id` | 数据血缘追踪 ID。 |
| `ods_table` | 来源 ODS 表名。 |
| `ingest_date` | 入湖日期分区。 |

### ods_trade_raw

用途：逐笔成交原始表，用于成交方向、成交冲击和短周期流动性研究。

| 列名 | 简单说明 |
|---|---|
| `trade_date` | 交易日期。 |
| `symbol` | 股票代码。 |
| `event_time` | 事件发生时间或行情 bar 时间。 |
| `open` | 开盘价。 |
| `high` | 最高价。 |
| `low` | 最低价。 |
| `close` | 收盘价。 |
| `volume` | 成交量。 |
| `amount` | 成交额。 |
| `vwap` | 成交均价。 |
| `trade_id` | 逐笔成交 ID。 |
| `trade_price` | 成交价格。 |
| `trade_volume` | 成交数量。 |
| `source` | 数据来源。 |
| `source_version` | 源数据版本。 |
| `schema_version` | 表结构版本。 |
| `data_version` | 数据版本。 |
| `ingest_time` | 入库时间。 |
| `available_time` | 系统/模型可用该数据的时间，防未来函数关键字段。 |
| `trace_id` | 数据血缘追踪 ID。 |
| `ods_table` | 来源 ODS 表名。 |
| `ingest_date` | 入湖日期分区。 |

## DWD / Silver

清洗明细事实层：对 ODS 做标准化、清洗和点时间治理，形成可直接计算因子的事实表。

### announcement_document

用途：公告文档表，保存公告正文和文档元数据，供事件抽取和 RAG 使用。

| 列名 | 简单说明 |
|---|---|
| `document_id` | 文档 ID。 |
| `document_type` | 文档类型。 |
| `publish_time` | 数据源发布时间。 |
| `available_time` | 系统/模型可用该数据的时间，防未来函数关键字段。 |
| `source` | 数据来源。 |
| `title` | 标题。 |
| `content` | 正文内容。 |
| `primary_entity` | 项目当前数据资产字段。 |
| `primary_symbol` | 项目当前数据资产字段。 |
| `expected_polarity` | 项目当前数据资产字段。 |
| `expected_impact_scope` | 项目当前数据资产字段。 |
| `license_id` | 数据许可证 ID。 |
| `data_version` | 数据版本。 |
| `schema_version` | 表结构版本。 |
| `trace_id` | 数据血缘追踪 ID。 |
| `research_boundary` | 研究边界，强调研究用途而非投资建议。 |

### dwd_announcement_event

用途：公告事件标准化结果表，面向公告情绪和事件因子。

| 列名 | 简单说明 |
|---|---|
| `event_id` | 事件 ID。 |
| `document_id` | 文档 ID。 |
| `publish_time` | 数据源发布时间。 |
| `available_time` | 系统/模型可用该数据的时间，防未来函数关键字段。 |
| `prediction_time` | 模型做预测的时间点。 |
| `source` | 数据来源。 |
| `source_authority_weight` | 项目当前数据资产字段。 |
| `symbol` | 股票代码。 |
| `event_type` | 事件类型。 |
| `sentiment_score` | 情绪相关特征。 |
| `novelty_score` | 评分字段。 |
| `impact_scope` | 项目当前数据资产字段。 |
| `event_decay_5m` | 事件衰减特征。 |
| `event_decay_1h` | 事件衰减特征。 |
| `event_decay_1d` | 事件衰减特征。 |
| `event_decay_5d` | 事件衰减特征。 |
| `leakage_check_status` | 未来函数/数据泄漏检查状态。 |
| `data_version` | 数据版本。 |
| `schema_version` | 表结构版本。 |
| `trace_id` | 数据血缘追踪 ID。 |
| `research_boundary` | 研究边界，强调研究用途而非投资建议。 |

### dwd_financial_statement

用途：清洗后的财报明细表，用于构建真实基本面因子。

| 列名 | 简单说明 |
|---|---|
| `symbol` | 股票代码。 |
| `report_period` | 财报报告期。 |
| `event_time` | 事件发生时间或行情 bar 时间。 |
| `statement_type` | 报表类型。 |
| `item_name` | 财务科目名称。 |
| `item_value` | 财务科目值。 |
| `publish_time` | 数据源发布时间。 |
| `source` | 数据来源。 |
| `source_version` | 源数据版本。 |
| `schema_version` | 表结构版本。 |
| `data_version` | 数据版本。 |
| `ingest_time` | 入库时间。 |
| `available_time` | 系统/模型可用该数据的时间，防未来函数关键字段。 |
| `trace_id` | 数据血缘追踪 ID。 |

### dwd_news_event

用途：新闻事件标准化结果表，面向新闻情绪和事件因子。

| 列名 | 简单说明 |
|---|---|
| `event_id` | 事件 ID。 |
| `document_id` | 文档 ID。 |
| `publish_time` | 数据源发布时间。 |
| `available_time` | 系统/模型可用该数据的时间，防未来函数关键字段。 |
| `prediction_time` | 模型做预测的时间点。 |
| `source` | 数据来源。 |
| `source_authority_weight` | 项目当前数据资产字段。 |
| `symbol` | 股票代码。 |
| `event_type` | 事件类型。 |
| `sentiment_score` | 情绪相关特征。 |
| `novelty_score` | 评分字段。 |
| `impact_scope` | 项目当前数据资产字段。 |
| `event_decay_5m` | 事件衰减特征。 |
| `event_decay_1h` | 事件衰减特征。 |
| `event_decay_1d` | 事件衰减特征。 |
| `event_decay_5d` | 事件衰减特征。 |
| `leakage_check_status` | 未来函数/数据泄漏检查状态。 |
| `data_version` | 数据版本。 |
| `schema_version` | 表结构版本。 |
| `trace_id` | 数据血缘追踪 ID。 |
| `research_boundary` | 研究边界，强调研究用途而非投资建议。 |

### dwd_stock_daily_bar

用途：清洗后的日频行情事实表，补充复权、停牌、ST、涨跌停，是离线日频因子的主输入。

| 列名 | 简单说明 |
|---|---|
| `trade_date` | 交易日期。 |
| `symbol` | 股票代码。 |
| `open` | 开盘价。 |
| `high` | 最高价。 |
| `low` | 最低价。 |
| `close` | 收盘价。 |
| `volume` | 成交量。 |
| `amount` | 成交额。 |
| `event_time` | 事件发生时间或行情 bar 时间。 |
| `publish_time` | 数据源发布时间。 |
| `source` | 数据来源。 |
| `source_version` | 源数据版本。 |
| `schema_version` | 表结构版本。 |
| `data_version` | 数据版本。 |
| `ingest_time` | 入库时间。 |
| `available_time` | 系统/模型可用该数据的时间，防未来函数关键字段。 |
| `trace_id` | 数据血缘追踪 ID。 |
| `adj_factor` | 复权因子。 |
| `paused` | 是否停牌。 |
| `st_flag` | 是否 ST。 |
| `limit_up` | 涨停价或涨停标记。 |
| `limit_down` | 跌停价或跌停标记。 |
| `adj_close` | 复权收盘价。 |

### dwd_stock_daily_bar_spark

用途：Spark 检查/验证版本的日频行情事实表。

| 列名 | 简单说明 |
|---|---|
| `symbol` | 股票代码。 |
| `open` | 开盘价。 |
| `high` | 最高价。 |
| `low` | 最低价。 |
| `close` | 收盘价。 |
| `volume` | 成交量。 |
| `amount` | 成交额。 |
| `adj_factor` | 复权因子。 |
| `paused` | 是否停牌。 |
| `limit_up` | 涨停价或涨停标记。 |
| `limit_down` | 跌停价或跌停标记。 |
| `st_flag` | 是否 ST。 |
| `event_time` | 事件发生时间或行情 bar 时间。 |
| `publish_time` | 数据源发布时间。 |
| `ingest_time` | 入库时间。 |
| `available_time` | 系统/模型可用该数据的时间，防未来函数关键字段。 |
| `data_version` | 数据版本。 |
| `schema_version` | 表结构版本。 |
| `trace_id` | 数据血缘追踪 ID。 |
| `adj_close` | 复权收盘价。 |

### dwd_stock_minute_bar

用途：清洗后的分钟行情事实表，用于分钟因子和实时链路验证。

| 列名 | 简单说明 |
|---|---|
| `trade_date` | 交易日期。 |
| `symbol` | 股票代码。 |
| `event_time` | 事件发生时间或行情 bar 时间。 |
| `open` | 开盘价。 |
| `high` | 最高价。 |
| `low` | 最低价。 |
| `close` | 收盘价。 |
| `volume` | 成交量。 |
| `amount` | 成交额。 |
| `vwap` | 成交均价。 |
| `source` | 数据来源。 |
| `source_version` | 源数据版本。 |
| `schema_version` | 表结构版本。 |
| `data_version` | 数据版本。 |
| `ingest_time` | 入库时间。 |
| `available_time` | 系统/模型可用该数据的时间，防未来函数关键字段。 |
| `trace_id` | 数据血缘追踪 ID。 |

### entity_symbol_mapping

用途：实体到股票代码的映射表，用于把新闻、公告中的实体映射到 symbol。

| 列名 | 简单说明 |
|---|---|
| `entity_name` | 项目当前数据资产字段。 |
| `symbol` | 股票代码。 |
| `industry_name` | 行业名称。 |
| `mapping_confidence` | 项目当前数据资产字段。 |
| `as_of_date` | 日期字段。 |
| `available_time` | 系统/模型可用该数据的时间，防未来函数关键字段。 |
| `source` | 数据来源。 |
| `license_id` | 数据许可证 ID。 |
| `data_version` | 数据版本。 |
| `schema_version` | 表结构版本。 |
| `research_boundary` | 研究边界，强调研究用途而非投资建议。 |

### event_extraction_result

用途：新闻/公告统一事件抽取结果表，是事件因子的明细基础。

| 列名 | 简单说明 |
|---|---|
| `event_id` | 事件 ID。 |
| `document_id` | 文档 ID。 |
| `document_type` | 文档类型。 |
| `publish_time` | 数据源发布时间。 |
| `available_time` | 系统/模型可用该数据的时间，防未来函数关键字段。 |
| `prediction_time` | 模型做预测的时间点。 |
| `source` | 数据来源。 |
| `source_authority_weight` | 项目当前数据资产字段。 |
| `entity_name` | 项目当前数据资产字段。 |
| `symbol` | 股票代码。 |
| `event_type` | 事件类型。 |
| `sentiment_model` | 情绪相关特征。 |
| `sentiment_score` | 情绪相关特征。 |
| `event_type_model` | 项目当前数据资产字段。 |
| `novelty_score` | 评分字段。 |
| `similarity_7d` | 项目当前数据资产字段。 |
| `similarity_30d` | 项目当前数据资产字段。 |
| `similarity_90d` | 项目当前数据资产字段。 |
| `impact_scope` | 项目当前数据资产字段。 |
| `event_decay_5m` | 事件衰减特征。 |
| `event_decay_30m` | 事件衰减特征。 |
| `event_decay_1h` | 事件衰减特征。 |
| `event_decay_1d` | 事件衰减特征。 |
| `event_decay_3d` | 事件衰减特征。 |
| `event_decay_5d` | 事件衰减特征。 |
| `event_decay_20d` | 事件衰减特征。 |
| `leakage_check_status` | 未来函数/数据泄漏检查状态。 |
| `data_version` | 数据版本。 |
| `schema_version` | 表结构版本。 |
| `trace_id` | 数据血缘追踪 ID。 |
| `research_boundary` | 研究边界，强调研究用途而非投资建议。 |

### news_document

用途：新闻文档表，保存新闻正文和文档元数据，供事件抽取和 RAG 使用。

| 列名 | 简单说明 |
|---|---|
| `document_id` | 文档 ID。 |
| `document_type` | 文档类型。 |
| `publish_time` | 数据源发布时间。 |
| `available_time` | 系统/模型可用该数据的时间，防未来函数关键字段。 |
| `source` | 数据来源。 |
| `title` | 标题。 |
| `content` | 正文内容。 |
| `primary_entity` | 项目当前数据资产字段。 |
| `primary_symbol` | 项目当前数据资产字段。 |
| `expected_polarity` | 项目当前数据资产字段。 |
| `expected_impact_scope` | 项目当前数据资产字段。 |
| `license_id` | 数据许可证 ID。 |
| `data_version` | 数据版本。 |
| `schema_version` | 表结构版本。 |
| `trace_id` | 数据血缘追踪 ID。 |
| `research_boundary` | 研究边界，强调研究用途而非投资建议。 |

### reference

用途：轻量参考维表/测试表。

| 列名 | 简单说明 |
|---|---|
| `symbol` | 股票代码。 |
| `source` | 数据来源。 |
| `data_version` | 数据版本。 |

## DWS / Gold

研究资产层：沉淀因子、标签、训练样本、模型信号、回测、风险、RAG、图谱和模拟盘资产。

### advanced_model_predictions

用途：高级模型预测表，服务 MASTER、StockMixer、HIST、TRSR 等 adapter。

| 列名 | 简单说明 |
|---|---|
| `trade_date` | 交易日期。 |
| `symbol` | 股票代码。 |
| `prediction_time` | 模型做预测的时间点。 |
| `available_time` | 系统/模型可用该数据的时间，防未来函数关键字段。 |
| `industry_name` | 行业名称。 |
| `forward_return` | 未来收益，研究评估标签，前端实盘页面不应直接展示。 |
| `cs_zscore_label` | 横截面标准化标签。 |
| `quantile_label` | 分位标签。 |
| `tradable_flag` | 是否可交易。 |
| `model_name` | 模型名称。 |
| `run_id` | 运行 ID。 |
| `experiment_id` | 实验 ID。 |
| `model_version` | 模型版本。 |
| `horizon` | 预测/标签周期。 |
| `score` | 模型综合分。 |
| `rank` | 横截面排名。 |
| `percentile` | 横截面分位。 |
| `confidence` | 置信度。 |
| `maturity` | 项目当前数据资产字段。 |
| `admission_status` | 项目当前数据资产字段。 |
| `approval_status` | 项目当前数据资产字段。 |
| `leakage_check_status` | 未来函数/数据泄漏检查状态。 |
| `research_boundary` | 研究边界，强调研究用途而非投资建议。 |
| `model_rank_ic` | 项目当前数据资产字段。 |

### factor_daily_panel

用途：早期/简版日频因子表，用于 lakehouse MVP 链路验证。

| 列名 | 简单说明 |
|---|---|
| `trade_date` | 交易日期。 |
| `symbol` | 股票代码。 |
| `factor_value` | 因子值。 |
| `available_time` | 系统/模型可用该数据的时间，防未来函数关键字段。 |
| `source` | 数据来源。 |
| `data_version` | 数据版本。 |
| `schema_version` | 表结构版本。 |
| `trace_id` | 数据血缘追踪 ID。 |
| `factor_name` | 因子名称。 |
| `factor_set` | 因子集合。 |
| `factor_version` | 因子版本。 |

### factor_daily_panel_event_regime_event_regime

用途：事件和市场状态类因子的长表。

| 列名 | 简单说明 |
|---|---|
| `trade_date` | 交易日期。 |
| `symbol` | 股票代码。 |
| `prediction_time` | 模型做预测的时间点。 |
| `available_time` | 系统/模型可用该数据的时间，防未来函数关键字段。 |
| `factor_name` | 因子名称。 |
| `factor_value` | 因子值。 |
| `factor_category` | 因子类别。 |
| `factor_version` | 因子版本。 |
| `leakage_check_status` | 未来函数/数据泄漏检查状态。 |
| `data_version` | 数据版本。 |
| `schema_version` | 表结构版本。 |
| `trace_id` | 数据血缘追踪 ID。 |
| `research_boundary` | 研究边界，强调研究用途而非投资建议。 |

### factor_daily_panel_long

用途：正式日频因子长表，一行一个股票-日期-因子，便于因子治理和单因子分析。

| 列名 | 简单说明 |
|---|---|
| `trade_date` | 交易日期。 |
| `symbol` | 股票代码。 |
| `prediction_time` | 模型做预测的时间点。 |
| `available_time` | 系统/模型可用该数据的时间，防未来函数关键字段。 |
| `industry_name` | 行业名称。 |
| `data_version` | 数据版本。 |
| `source_version` | 源数据版本。 |
| `schema_version` | 表结构版本。 |
| `trace_id` | 数据血缘追踪 ID。 |
| `factor_name` | 因子名称。 |
| `factor_value` | 因子值。 |
| `factor_version` | 因子版本。 |
| `feature_set_version` | 特征集合版本。 |
| `category` | 因子类别。 |
| `research_boundary` | 研究边界，强调研究用途而非投资建议。 |

### factor_daily_panel_relation_graph_relation

用途：关系图谱因子的长表版本。

| 列名 | 简单说明 |
|---|---|
| `trade_date` | 交易日期。 |
| `symbol` | 股票代码。 |
| `prediction_time` | 模型做预测的时间点。 |
| `available_time` | 系统/模型可用该数据的时间，防未来函数关键字段。 |
| `factor_name` | 因子名称。 |
| `factor_value` | 因子值。 |
| `factor_category` | 因子类别。 |
| `factor_version` | 因子版本。 |
| `data_version` | 数据版本。 |
| `schema_version` | 表结构版本。 |
| `leakage_check_status` | 未来函数/数据泄漏检查状态。 |
| `trace_id` | 数据血缘追踪 ID。 |
| `research_boundary` | 研究边界，强调研究用途而非投资建议。 |

### factor_daily_panel_spark_check

用途：Spark 检查用因子长表。

| 列名 | 简单说明 |
|---|---|
| `symbol` | 股票代码。 |
| `prediction_time` | 模型做预测的时间点。 |
| `available_time` | 系统/模型可用该数据的时间，防未来函数关键字段。 |
| `feature_set_version` | 特征集合版本。 |
| `research_boundary` | 研究边界，强调研究用途而非投资建议。 |
| `factor_name` | 因子名称。 |
| `factor_value` | 因子值。 |

### factor_intraday_panel

用途：分钟/实时因子面板。

| 列名 | 简单说明 |
|---|---|
| `event_time` | 事件发生时间或行情 bar 时间。 |
| `trade_date` | 交易日期。 |
| `symbol` | 股票代码。 |
| `factor_name` | 因子名称。 |
| `factor_value` | 因子值。 |
| `window` | 项目当前数据资产字段。 |
| `factor_version` | 因子版本。 |
| `source_topic` | 项目当前数据资产字段。 |
| `output_topic` | 项目当前数据资产字段。 |
| `idempotent_key` | 项目当前数据资产字段。 |
| `maturity` | 项目当前数据资产字段。 |
| `research_boundary` | 研究边界，强调研究用途而非投资建议。 |

### factor_market_regime_panel

用途：市场状态/regime 因子表，用于描述市场宽度、波动、风险偏好和风格环境。

| 列名 | 简单说明 |
|---|---|
| `trade_date` | 交易日期。 |
| `available_time` | 系统/模型可用该数据的时间，防未来函数关键字段。 |
| `prediction_time` | 模型做预测的时间点。 |
| `market_breadth` | 项目当前数据资产字段。 |
| `market_ret_1d` | 项目当前数据资产字段。 |
| `market_ret_5d` | 项目当前数据资产字段。 |
| `market_ret_20d` | 项目当前数据资产字段。 |
| `market_vol_20d` | 项目当前数据资产字段。 |
| `market_drawdown_20d` | 项目当前数据资产字段。 |
| `limit_up_count` | 项目当前数据资产字段。 |
| `limit_down_count` | 项目当前数据资产字段。 |
| `amount_percentile_252d` | 项目当前数据资产字段。 |
| `small_vs_large_return` | 收益相关字段。 |
| `growth_vs_value_return` | 收益相关字段。 |
| `industry_dispersion` | 项目当前数据资产字段。 |
| `northbound_flow_zscore` | 标准化 z-score 特征。 |
| `liquidity_regime` | 项目当前数据资产字段。 |
| `risk_appetite_proxy` | 代理变量。 |
| `ex_ante_regime_feature` | 项目当前数据资产字段。 |
| `ex_post_regime_label` | 项目当前数据资产字段。 |
| `regime_feature_role` | 项目当前数据资产字段。 |
| `ex_post_regime_label_role` | 项目当前数据资产字段。 |
| `leakage_check_status` | 未来函数/数据泄漏检查状态。 |
| `factor_version` | 因子版本。 |
| `data_version` | 数据版本。 |
| `schema_version` | 表结构版本。 |
| `trace_id` | 数据血缘追踪 ID。 |
| `research_boundary` | 研究边界，强调研究用途而非投资建议。 |

### factor_news_sentiment_panel

用途：新闻情绪因子面板。

| 列名 | 简单说明 |
|---|---|
| `trade_date` | 交易日期。 |
| `symbol` | 股票代码。 |
| `prediction_time` | 模型做预测的时间点。 |
| `available_time` | 系统/模型可用该数据的时间，防未来函数关键字段。 |
| `factor_name` | 因子名称。 |
| `factor_value` | 因子值。 |
| `factor_category` | 因子类别。 |
| `factor_version` | 因子版本。 |
| `leakage_check_status` | 未来函数/数据泄漏检查状态。 |
| `data_version` | 数据版本。 |
| `schema_version` | 表结构版本。 |
| `trace_id` | 数据血缘追踪 ID。 |
| `research_boundary` | 研究边界，强调研究用途而非投资建议。 |

### factor_relation_panel

用途：关系图谱传播因子宽表。

| 列名 | 简单说明 |
|---|---|
| `trade_date` | 交易日期。 |
| `symbol` | 股票代码。 |
| `prediction_time` | 模型做预测的时间点。 |
| `available_time` | 系统/模型可用该数据的时间，防未来函数关键字段。 |
| `neighbor_return_5m` | 收益相关字段。 |
| `neighbor_return_1d` | 收益相关字段。 |
| `neighbor_volume_shock` | 项目当前数据资产字段。 |
| `neighbor_sentiment_1h` | 情绪相关特征。 |
| `industry_spillover` | 项目当前数据资产字段。 |
| `concept_spillover` | 项目当前数据资产字段。 |
| `supply_chain_spillover` | 项目当前数据资产字段。 |
| `lead_lag_signal` | 项目当前数据资产字段。 |
| `relation_risk_score` | 风险相关字段。 |
| `centrality_score` | 评分字段。 |
| `community_momentum` | 项目当前数据资产字段。 |
| `correlation_cluster_momentum` | 项目当前数据资产字段。 |
| `community_id` | 图社区 ID。 |
| `factor_version` | 因子版本。 |
| `data_version` | 数据版本。 |
| `schema_version` | 表结构版本。 |
| `leakage_check_status` | 未来函数/数据泄漏检查状态。 |
| `research_boundary` | 研究边界，强调研究用途而非投资建议。 |

### graph_model_adapters

用途：图模型适配产物目录，包含 HIST/TRSR 所需矩阵、张量和映射。

#### hist_trsr/concept_matrix.parquet

用途：图模型适配文件 `concept_matrix.parquet`。

| 列名 | 简单说明 |
|---|---|
| `stock_id` | 模型内部股票 ID。 |
| `symbol` | 股票代码。 |
| `concept_id` | 概念 ID。 |
| `concept_weight` | 股票与概念的权重。 |

#### hist_trsr/label_tensor.parquet

用途：图模型适配文件 `label_tensor.parquet`。

| 列名 | 简单说明 |
|---|---|
| `stock_id` | 模型内部股票 ID。 |
| `symbol` | 股票代码。 |
| `trade_date` | 交易日期。 |
| `horizon` | 预测/标签周期。 |
| `label_value` | 标签值。 |

#### hist_trsr/relation_matrix.parquet

用途：图模型适配文件 `relation_matrix.parquet`。

| 列名 | 简单说明 |
|---|---|
| `src_id` | 源股票内部 ID。 |
| `dst_id` | 目标股票内部 ID。 |
| `relation_type_id` | 关系类型 ID。 |
| `weight` | 权重。 |
| `src_symbol` | 源股票代码。 |
| `dst_symbol` | 目标股票代码。 |
| `relation_type` | 关系类型。 |

#### hist_trsr/relation_type_mapping.json

用途：图模型映射文件 `relation_type_mapping.json`。

| 结构 | 简单说明 |
|---|---|
| JSON mapping | ID 与名称/代码之间的映射字典。 |

#### hist_trsr/stock_feature_tensor.parquet

用途：图模型适配文件 `stock_feature_tensor.parquet`。

| 列名 | 简单说明 |
|---|---|
| `stock_id` | 模型内部股票 ID。 |
| `symbol` | 股票代码。 |
| `trade_date` | 交易日期。 |
| `feature_name` | 特征名称。 |
| `feature_value` | 特征值。 |

#### hist_trsr/stock_id_mapping.json

用途：图模型映射文件 `stock_id_mapping.json`。

| 结构 | 简单说明 |
|---|---|
| JSON mapping | ID 与名称/代码之间的映射字典。 |

### label_cross_sectional_return

用途：横截面收益预测标签表，是监督学习 y 值来源。

| 列名 | 简单说明 |
|---|---|
| `trade_date` | 交易日期。 |
| `symbol` | 股票代码。 |
| `horizon` | 预测/标签周期。 |
| `label_horizon` | 项目当前数据资产字段。 |
| `prediction_time` | 模型做预测的时间点。 |
| `execution_price_type` | 项目当前数据资产字段。 |
| `execution_window` | 项目当前数据资产字段。 |
| `label_start_time` | 时间字段。 |
| `label_end_time` | 时间字段。 |
| `forward_return` | 未来收益，研究评估标签，前端实盘页面不应直接展示。 |
| `up_label` | 是否上涨标签。 |
| `excess_return` | 相对基准超额收益。 |
| `industry_neutral_return` | 行业中性收益。 |
| `cs_zscore_label` | 横截面标准化标签。 |
| `quantile_label` | 分位标签。 |
| `tradable_flag` | 是否可交易。 |
| `pause_flag` | 是否停牌。 |
| `st_flag` | 是否 ST。 |
| `limit_up_at_entry` | 项目当前数据资产字段。 |
| `limit_down_at_exit` | 项目当前数据资产字段。 |
| `delist_flag` | 布尔标记字段。 |
| `industry_name` | 行业名称。 |
| `benchmark` | 基准指数或基准组合。 |
| `label_version` | 标签版本。 |
| `data_version` | 数据版本。 |
| `research_boundary` | 研究边界，强调研究用途而非投资建议。 |
| `leakage_check_status` | 未来函数/数据泄漏检查状态。 |

### model_feature_matrix_spark_check

用途：Spark 检查用的小型模型特征宽表。

| 列名 | 简单说明 |
|---|---|
| `trade_date` | 交易日期。 |
| `symbol` | 股票代码。 |
| `prediction_time` | 模型做预测的时间点。 |
| `available_time` | 系统/模型可用该数据的时间，防未来函数关键字段。 |
| `feature_set_version` | 特征集合版本。 |
| `factor_version` | 因子版本。 |
| `research_boundary` | 研究边界，强调研究用途而非投资建议。 |
| `return_5d` | 过去 5d 收益。 |
| `momentum_20d` | 20d 动量因子。 |
| `volatility_20d` | 20d 波动率。 |
| `ma20_gap` | 20 日均线偏离。 |
| `volume_mean_20d` | 20d 平均成交量。 |
| `amount_mean_20d` | 20d 平均成交额。 |
| `volume_shock_20d` | 项目当前数据资产字段。 |
| `intraday_return` | 收益相关字段。 |
| `high_low_range` | 项目当前数据资产字段。 |
| `close_position_in_range` | 项目当前数据资产字段。 |
| `turnover_proxy_20d` | 20d 换手代理指标。 |
| `size_log_amount` | 项目当前数据资产字段。 |
| `vwap_deviation` | 项目当前数据资产字段。 |

### model_feature_matrix_wide

用途：基础模型训练宽表，一行一个股票-日期样本，列为离线因子。

| 列名 | 简单说明 |
|---|---|
| `run_id` | 运行 ID。 |
| `trade_date` | 交易日期。 |
| `symbol` | 股票代码。 |
| `prediction_time` | 模型做预测的时间点。 |
| `feature_set_version` | 特征集合版本。 |
| `available_time` | 系统/模型可用该数据的时间，防未来函数关键字段。 |
| `return_1d` | 过去 1d 收益。 |
| `return_5d` | 过去 5d 收益。 |
| `return_10d` | 过去 10d 收益。 |
| `return_20d` | 过去 20d 收益。 |
| `return_60d` | 过去 60d 收益。 |
| `return_120d` | 过去 120d 收益。 |
| `momentum_20d` | 20d 动量因子。 |
| `momentum_60d` | 60d 动量因子。 |
| `momentum_120d` | 120d 动量因子。 |
| `reversal_1d` | 1d 反转因子。 |
| `reversal_5d` | 5d 反转因子。 |
| `reversal_10d` | 10d 反转因子。 |
| `volatility_5d` | 5d 波动率。 |
| `volatility_10d` | 10d 波动率。 |
| `volatility_20d` | 20d 波动率。 |
| `volatility_60d` | 60d 波动率。 |
| `volatility_120d` | 120d 波动率。 |
| `downside_volatility_20d` | 项目当前数据资产字段。 |
| `high_low_volatility_20d` | 项目当前数据资产字段。 |
| `skew_20d` | 项目当前数据资产字段。 |
| `kurtosis_20d` | 项目当前数据资产字段。 |
| `downside_volatility_60d` | 项目当前数据资产字段。 |
| `high_low_volatility_60d` | 项目当前数据资产字段。 |
| `skew_60d` | 项目当前数据资产字段。 |
| `kurtosis_60d` | 项目当前数据资产字段。 |
| `turnover_proxy_5d` | 5d 换手代理指标。 |
| `amount_mean_5d` | 5d 平均成交额。 |
| `volume_mean_5d` | 5d 平均成交量。 |
| `turnover_proxy_20d` | 20d 换手代理指标。 |
| `amount_mean_20d` | 20d 平均成交额。 |
| `volume_mean_20d` | 20d 平均成交量。 |
| `turnover_proxy_60d` | 60d 换手代理指标。 |
| `amount_mean_60d` | 60d 平均成交额。 |
| `volume_mean_60d` | 60d 平均成交量。 |
| `amihud_20d` | 项目当前数据资产字段。 |
| `zero_trade_ratio_20d` | 项目当前数据资产字段。 |
| `amount_percentile_20d` | 项目当前数据资产字段。 |
| `amihud_60d` | 项目当前数据资产字段。 |
| `zero_trade_ratio_60d` | 项目当前数据资产字段。 |
| `amount_percentile_60d` | 项目当前数据资产字段。 |
| `liquidity_zscore_20d` | 标准化 z-score 特征。 |
| `vwap_deviation` | 项目当前数据资产字段。 |
| `close_to_high` | 项目当前数据资产字段。 |
| `close_to_low` | 项目当前数据资产字段。 |
| `intraday_return` | 收益相关字段。 |
| `overnight_gap` | 项目当前数据资产字段。 |
| `high_low_range` | 项目当前数据资产字段。 |
| `close_position_in_range` | 项目当前数据资产字段。 |
| `volume_shock_5d` | 项目当前数据资产字段。 |
| `volume_shock_20d` | 项目当前数据资产字段。 |
| `price_volume_corr_20d` | 项目当前数据资产字段。 |
| `price_volume_corr_60d` | 项目当前数据资产字段。 |
| `ma5_gap` | 5 日均线偏离。 |
| `ma10_gap` | 10 日均线偏离。 |
| `ma20_gap` | 20 日均线偏离。 |
| `ma60_gap` | 60 日均线偏离。 |
| `ma120_gap` | 120 日均线偏离。 |
| `size_log_amount` | 项目当前数据资产字段。 |
| `market_cap_proxy` | 代理变量。 |
| `float_market_cap_proxy` | 代理变量。 |
| `beta_20d` | 项目当前数据资产字段。 |
| `beta_60d` | 项目当前数据资产字段。 |
| `value_proxy` | 代理变量。 |
| `quality_proxy` | 代理变量。 |
| `growth_proxy_20d` | 代理变量。 |
| `low_volatility_proxy` | 代理变量。 |
| `liquidity_proxy` | 代理变量。 |
| `industry_return_1d` | 收益相关字段。 |
| `industry_neutral_return_20d` | 收益相关字段。 |
| `industry_rank_return_20d` | 收益相关字段。 |
| `cs_zscore_return_20d` | 标准化 z-score 特征。 |
| `cs_rank_return_20d` | 收益相关字段。 |
| `cs_zscore_liquidity` | 标准化 z-score 特征。 |
| `industry_zscore_liquidity` | 标准化 z-score 特征。 |
| `research_boundary` | 研究边界，强调研究用途而非投资建议。 |

### model_feature_matrix_wide_event_regime

用途：在基础宽表上增加新闻、公告、事件和市场 regime 特征。

| 列名 | 简单说明 |
|---|---|
| `run_id` | 运行 ID。 |
| `trade_date` | 交易日期。 |
| `symbol` | 股票代码。 |
| `prediction_time` | 模型做预测的时间点。 |
| `feature_set_version` | 特征集合版本。 |
| `available_time` | 系统/模型可用该数据的时间，防未来函数关键字段。 |
| `industry_name` | 行业名称。 |
| `data_version` | 数据版本。 |
| `source_version` | 源数据版本。 |
| `schema_version` | 表结构版本。 |
| `trace_id` | 数据血缘追踪 ID。 |
| `return_1d` | 过去 1d 收益。 |
| `return_5d` | 过去 5d 收益。 |
| `return_10d` | 过去 10d 收益。 |
| `return_20d` | 过去 20d 收益。 |
| `return_60d` | 过去 60d 收益。 |
| `return_120d` | 过去 120d 收益。 |
| `momentum_20d` | 20d 动量因子。 |
| `momentum_60d` | 60d 动量因子。 |
| `momentum_120d` | 120d 动量因子。 |
| `reversal_1d` | 1d 反转因子。 |
| `reversal_5d` | 5d 反转因子。 |
| `reversal_10d` | 10d 反转因子。 |
| `volatility_5d` | 5d 波动率。 |
| `volatility_10d` | 10d 波动率。 |
| `volatility_20d` | 20d 波动率。 |
| `volatility_60d` | 60d 波动率。 |
| `volatility_120d` | 120d 波动率。 |
| `downside_volatility_20d` | 项目当前数据资产字段。 |
| `high_low_volatility_20d` | 项目当前数据资产字段。 |
| `skew_20d` | 项目当前数据资产字段。 |
| `kurtosis_20d` | 项目当前数据资产字段。 |
| `downside_volatility_60d` | 项目当前数据资产字段。 |
| `high_low_volatility_60d` | 项目当前数据资产字段。 |
| `skew_60d` | 项目当前数据资产字段。 |
| `kurtosis_60d` | 项目当前数据资产字段。 |
| `turnover_proxy_5d` | 5d 换手代理指标。 |
| `amount_mean_5d` | 5d 平均成交额。 |
| `volume_mean_5d` | 5d 平均成交量。 |
| `turnover_proxy_20d` | 20d 换手代理指标。 |
| `amount_mean_20d` | 20d 平均成交额。 |
| `volume_mean_20d` | 20d 平均成交量。 |
| `turnover_proxy_60d` | 60d 换手代理指标。 |
| `amount_mean_60d` | 60d 平均成交额。 |
| `volume_mean_60d` | 60d 平均成交量。 |
| `amihud_20d` | 项目当前数据资产字段。 |
| `zero_trade_ratio_20d` | 项目当前数据资产字段。 |
| `amount_percentile_20d` | 项目当前数据资产字段。 |
| `amihud_60d` | 项目当前数据资产字段。 |
| `zero_trade_ratio_60d` | 项目当前数据资产字段。 |
| `amount_percentile_60d` | 项目当前数据资产字段。 |
| `liquidity_zscore_20d` | 标准化 z-score 特征。 |
| `vwap_deviation` | 项目当前数据资产字段。 |
| `close_to_high` | 项目当前数据资产字段。 |
| `close_to_low` | 项目当前数据资产字段。 |
| `intraday_return` | 收益相关字段。 |
| `overnight_gap` | 项目当前数据资产字段。 |
| `high_low_range` | 项目当前数据资产字段。 |
| `close_position_in_range` | 项目当前数据资产字段。 |
| `volume_shock_5d` | 项目当前数据资产字段。 |
| `volume_shock_20d` | 项目当前数据资产字段。 |
| `price_volume_corr_20d` | 项目当前数据资产字段。 |
| `price_volume_corr_60d` | 项目当前数据资产字段。 |
| `ma5_gap` | 5 日均线偏离。 |
| `ma10_gap` | 10 日均线偏离。 |
| `ma20_gap` | 20 日均线偏离。 |
| `ma60_gap` | 60 日均线偏离。 |
| `ma120_gap` | 120 日均线偏离。 |
| `size_log_amount` | 项目当前数据资产字段。 |
| `market_cap_proxy` | 代理变量。 |
| `float_market_cap_proxy` | 代理变量。 |
| `beta_20d` | 项目当前数据资产字段。 |
| `beta_60d` | 项目当前数据资产字段。 |
| `value_proxy` | 代理变量。 |
| `quality_proxy` | 代理变量。 |
| `growth_proxy_20d` | 代理变量。 |
| `low_volatility_proxy` | 代理变量。 |
| `liquidity_proxy` | 代理变量。 |
| `industry_return_1d` | 收益相关字段。 |
| `industry_neutral_return_20d` | 收益相关字段。 |
| `industry_rank_return_20d` | 收益相关字段。 |
| `cs_zscore_return_20d` | 标准化 z-score 特征。 |
| `cs_rank_return_20d` | 收益相关字段。 |
| `cs_zscore_liquidity` | 标准化 z-score 特征。 |
| `industry_zscore_liquidity` | 标准化 z-score 特征。 |
| `news_sentiment_1d` | 情绪相关特征。 |
| `news_sentiment_3d` | 情绪相关特征。 |
| `news_sentiment_5d` | 情绪相关特征。 |
| `announcement_sentiment` | 情绪相关特征。 |
| `event_count` | 项目当前数据资产字段。 |
| `negative_event_count` | 项目当前数据资产字段。 |
| `source_weighted_sentiment` | 情绪相关特征。 |
| `novelty_score` | 评分字段。 |
| `event_authority_score` | 评分字段。 |
| `event_decay_5m` | 事件衰减特征。 |
| `event_decay_1h` | 事件衰减特征。 |
| `event_decay_1d` | 事件衰减特征。 |
| `event_decay_5d` | 事件衰减特征。 |
| `policy_event_score` | 评分字段。 |
| `macro_event_score` | 评分字段。 |
| `market_breadth` | 项目当前数据资产字段。 |
| `market_ret_1d` | 项目当前数据资产字段。 |
| `market_ret_5d` | 项目当前数据资产字段。 |
| `market_ret_20d` | 项目当前数据资产字段。 |
| `market_vol_20d` | 项目当前数据资产字段。 |
| `market_drawdown_20d` | 项目当前数据资产字段。 |
| `limit_up_count` | 项目当前数据资产字段。 |
| `limit_down_count` | 项目当前数据资产字段。 |
| `amount_percentile_252d` | 项目当前数据资产字段。 |
| `small_vs_large_return` | 收益相关字段。 |
| `growth_vs_value_return` | 收益相关字段。 |
| `industry_dispersion` | 项目当前数据资产字段。 |
| `northbound_flow_zscore` | 标准化 z-score 特征。 |
| `risk_appetite_proxy` | 代理变量。 |
| `ex_ante_regime_feature` | 项目当前数据资产字段。 |
| `relation_spillover_placeholder` | 项目当前数据资产字段。 |
| `event_regime_feature_version` | 版本字段。 |
| `research_boundary` | 研究边界，强调研究用途而非投资建议。 |

### model_feature_matrix_wide_relation_graph

用途：在事件/regime 宽表上增加关系图谱传播特征。

| 列名 | 简单说明 |
|---|---|
| `run_id` | 运行 ID。 |
| `trade_date` | 交易日期。 |
| `symbol` | 股票代码。 |
| `prediction_time` | 模型做预测的时间点。 |
| `feature_set_version` | 特征集合版本。 |
| `available_time` | 系统/模型可用该数据的时间，防未来函数关键字段。 |
| `return_1d` | 过去 1d 收益。 |
| `return_5d` | 过去 5d 收益。 |
| `return_10d` | 过去 10d 收益。 |
| `return_20d` | 过去 20d 收益。 |
| `return_60d` | 过去 60d 收益。 |
| `return_120d` | 过去 120d 收益。 |
| `momentum_20d` | 20d 动量因子。 |
| `momentum_60d` | 60d 动量因子。 |
| `momentum_120d` | 120d 动量因子。 |
| `reversal_1d` | 1d 反转因子。 |
| `reversal_5d` | 5d 反转因子。 |
| `reversal_10d` | 10d 反转因子。 |
| `volatility_5d` | 5d 波动率。 |
| `volatility_10d` | 10d 波动率。 |
| `volatility_20d` | 20d 波动率。 |
| `volatility_60d` | 60d 波动率。 |
| `volatility_120d` | 120d 波动率。 |
| `downside_volatility_20d` | 项目当前数据资产字段。 |
| `high_low_volatility_20d` | 项目当前数据资产字段。 |
| `skew_20d` | 项目当前数据资产字段。 |
| `kurtosis_20d` | 项目当前数据资产字段。 |
| `downside_volatility_60d` | 项目当前数据资产字段。 |
| `high_low_volatility_60d` | 项目当前数据资产字段。 |
| `skew_60d` | 项目当前数据资产字段。 |
| `kurtosis_60d` | 项目当前数据资产字段。 |
| `turnover_proxy_5d` | 5d 换手代理指标。 |
| `amount_mean_5d` | 5d 平均成交额。 |
| `volume_mean_5d` | 5d 平均成交量。 |
| `turnover_proxy_20d` | 20d 换手代理指标。 |
| `amount_mean_20d` | 20d 平均成交额。 |
| `volume_mean_20d` | 20d 平均成交量。 |
| `turnover_proxy_60d` | 60d 换手代理指标。 |
| `amount_mean_60d` | 60d 平均成交额。 |
| `volume_mean_60d` | 60d 平均成交量。 |
| `amihud_20d` | 项目当前数据资产字段。 |
| `zero_trade_ratio_20d` | 项目当前数据资产字段。 |
| `amount_percentile_20d` | 项目当前数据资产字段。 |
| `amihud_60d` | 项目当前数据资产字段。 |
| `zero_trade_ratio_60d` | 项目当前数据资产字段。 |
| `amount_percentile_60d` | 项目当前数据资产字段。 |
| `liquidity_zscore_20d` | 标准化 z-score 特征。 |
| `vwap_deviation` | 项目当前数据资产字段。 |
| `close_to_high` | 项目当前数据资产字段。 |
| `close_to_low` | 项目当前数据资产字段。 |
| `intraday_return` | 收益相关字段。 |
| `overnight_gap` | 项目当前数据资产字段。 |
| `high_low_range` | 项目当前数据资产字段。 |
| `close_position_in_range` | 项目当前数据资产字段。 |
| `volume_shock_5d` | 项目当前数据资产字段。 |
| `volume_shock_20d` | 项目当前数据资产字段。 |
| `price_volume_corr_20d` | 项目当前数据资产字段。 |
| `price_volume_corr_60d` | 项目当前数据资产字段。 |
| `ma5_gap` | 5 日均线偏离。 |
| `ma10_gap` | 10 日均线偏离。 |
| `ma20_gap` | 20 日均线偏离。 |
| `ma60_gap` | 60 日均线偏离。 |
| `ma120_gap` | 120 日均线偏离。 |
| `size_log_amount` | 项目当前数据资产字段。 |
| `market_cap_proxy` | 代理变量。 |
| `float_market_cap_proxy` | 代理变量。 |
| `beta_20d` | 项目当前数据资产字段。 |
| `beta_60d` | 项目当前数据资产字段。 |
| `value_proxy` | 代理变量。 |
| `quality_proxy` | 代理变量。 |
| `growth_proxy_20d` | 代理变量。 |
| `low_volatility_proxy` | 代理变量。 |
| `liquidity_proxy` | 代理变量。 |
| `industry_return_1d` | 收益相关字段。 |
| `industry_neutral_return_20d` | 收益相关字段。 |
| `industry_rank_return_20d` | 收益相关字段。 |
| `cs_zscore_return_20d` | 标准化 z-score 特征。 |
| `cs_rank_return_20d` | 收益相关字段。 |
| `cs_zscore_liquidity` | 标准化 z-score 特征。 |
| `industry_zscore_liquidity` | 标准化 z-score 特征。 |
| `research_boundary` | 研究边界，强调研究用途而非投资建议。 |
| `news_sentiment_1d` | 情绪相关特征。 |
| `news_sentiment_3d` | 情绪相关特征。 |
| `news_sentiment_5d` | 情绪相关特征。 |
| `announcement_sentiment` | 情绪相关特征。 |
| `event_count` | 项目当前数据资产字段。 |
| `negative_event_count` | 项目当前数据资产字段。 |
| `source_weighted_sentiment` | 情绪相关特征。 |
| `novelty_score` | 评分字段。 |
| `event_authority_score` | 评分字段。 |
| `event_decay_5m` | 事件衰减特征。 |
| `event_decay_1h` | 事件衰减特征。 |
| `event_decay_1d` | 事件衰减特征。 |
| `event_decay_5d` | 事件衰减特征。 |
| `policy_event_score` | 评分字段。 |
| `macro_event_score` | 评分字段。 |
| `market_breadth` | 项目当前数据资产字段。 |
| `market_ret_1d` | 项目当前数据资产字段。 |
| `market_ret_5d` | 项目当前数据资产字段。 |
| `market_ret_20d` | 项目当前数据资产字段。 |
| `market_vol_20d` | 项目当前数据资产字段。 |
| `market_drawdown_20d` | 项目当前数据资产字段。 |
| `limit_up_count` | 项目当前数据资产字段。 |
| `limit_down_count` | 项目当前数据资产字段。 |
| `amount_percentile_252d` | 项目当前数据资产字段。 |
| `small_vs_large_return` | 收益相关字段。 |
| `growth_vs_value_return` | 收益相关字段。 |
| `industry_dispersion` | 项目当前数据资产字段。 |
| `northbound_flow_zscore` | 标准化 z-score 特征。 |
| `risk_appetite_proxy` | 代理变量。 |
| `ex_ante_regime_feature` | 项目当前数据资产字段。 |
| `relation_spillover_placeholder` | 项目当前数据资产字段。 |
| `event_regime_feature_version` | 版本字段。 |
| `industry_name` | 行业名称。 |
| `neighbor_return_5m` | 收益相关字段。 |
| `neighbor_return_1d` | 收益相关字段。 |
| `neighbor_volume_shock` | 项目当前数据资产字段。 |
| `neighbor_sentiment_1h` | 情绪相关特征。 |
| `industry_spillover` | 项目当前数据资产字段。 |
| `concept_spillover` | 项目当前数据资产字段。 |
| `supply_chain_spillover` | 项目当前数据资产字段。 |
| `lead_lag_signal` | 项目当前数据资产字段。 |
| `relation_risk_score` | 风险相关字段。 |
| `centrality_score` | 评分字段。 |
| `community_momentum` | 项目当前数据资产字段。 |
| `correlation_cluster_momentum` | 项目当前数据资产字段。 |
| `relation_feature_version` | 关系特征版本。 |

### model_signal_cross_sectional

用途：模型横截面信号表，保存 score、rank、概率、置信度等预测结果。

| 列名 | 简单说明 |
|---|---|
| `trade_date` | 交易日期。 |
| `symbol` | 股票代码。 |
| `prediction_time` | 模型做预测的时间点。 |
| `industry_name` | 行业名称。 |
| `forward_return` | 未来收益，研究评估标签，前端实盘页面不应直接展示。 |
| `up_label` | 是否上涨标签。 |
| `excess_return` | 相对基准超额收益。 |
| `industry_neutral_return` | 行业中性收益。 |
| `cs_zscore_label` | 横截面标准化标签。 |
| `quantile_label` | 分位标签。 |
| `tradable_flag` | 是否可交易。 |
| `split_id` | 训练/验证/测试切分 ID。 |
| `run_id` | 运行 ID。 |
| `experiment_id` | 实验 ID。 |
| `model_name` | 模型名称。 |
| `model_version` | 模型版本。 |
| `horizon` | 预测/标签周期。 |
| `target_label` | 目标标签名。 |
| `probability_up` | 上涨概率。 |
| `probability_down` | 下跌概率。 |
| `score` | 模型综合分。 |
| `rank` | 横截面排名。 |
| `percentile` | 横截面分位。 |
| `confidence` | 置信度。 |
| `data_version` | 数据版本。 |
| `factor_version` | 因子版本。 |
| `label_version` | 标签版本。 |
| `feature_set_version` | 特征集合版本。 |
| `leakage_check_status` | 未来函数/数据泄漏检查状态。 |
| `research_boundary` | 研究边界，强调研究用途而非投资建议。 |

### portfolio_backtest_result

用途：组合回测日度结果表。

| 列名 | 简单说明 |
|---|---|
| `run_id` | 运行 ID。 |
| `experiment_id` | 实验 ID。 |
| `trade_date` | 交易日期。 |
| `portfolio_id` | 组合 ID。 |
| `benchmark` | 基准指数或基准组合。 |
| `gross_return` | 未扣交易成本收益。 |
| `transaction_cost` | 交易成本。 |
| `daily_return` | 扣成本后日收益。 |
| `turnover` | 换手率。 |
| `nav` | 净值。 |
| `top_k` | 持仓股票数量。 |
| `horizon` | 预测/标签周期。 |
| `research_boundary` | 研究边界，强调研究用途而非投资建议。 |
| `max_drawdown` | 最大回撤。 |

### portfolio_risk_report

用途：组合风险和归因报告表。

| 列名 | 简单说明 |
|---|---|
| `run_id` | 运行 ID。 |
| `trade_date` | 交易日期。 |
| `portfolio_id` | 组合 ID。 |
| `benchmark` | 基准指数或基准组合。 |
| `active_return` | 收益相关字段。 |
| `annualized_active_return` | 收益相关字段。 |
| `tracking_error` | 项目当前数据资产字段。 |
| `information_ratio` | 项目当前数据资产字段。 |
| `beta_to_benchmark` | 项目当前数据资产字段。 |
| `alpha` | 项目当前数据资产字段。 |
| `active_max_drawdown` | 项目当前数据资产字段。 |
| `hit_rate_vs_benchmark` | 项目当前数据资产字段。 |
| `up_capture` | 项目当前数据资产字段。 |
| `down_capture` | 项目当前数据资产字段。 |
| `industry_attribution` | 归因字段。 |
| `style_attribution` | 归因字段。 |
| `stock_selection_attribution` | 归因字段。 |
| `transaction_cost_attribution` | 归因字段。 |
| `implementation_shortfall` | 项目当前数据资产字段。 |
| `capacity_curve` | 项目当前数据资产字段。 |
| `risk_model_version` | 风险相关字段。 |
| `research_boundary` | 研究边界，强调研究用途而非投资建议。 |

### rag_chunks

用途：RAG 文档切片表。

| 列名 | 简单说明 |
|---|---|
| `chunk_id` | RAG 切片 ID。 |
| `doc_id` | RAG 文档 ID。 |
| `chunk_text` | 项目当前数据资产字段。 |
| `citation_span` | 项目当前数据资产字段。 |
| `publish_time` | 数据源发布时间。 |
| `available_time` | 系统/模型可用该数据的时间，防未来函数关键字段。 |
| `content_hash` | 内容哈希，用于去重和血缘。 |
| `index_version` | 版本字段。 |

### rag_claims

用途：claim-level RAG 证据表。

| 列名 | 简单说明 |
|---|---|
| `claim_id` | RAG claim ID。 |
| `doc_id` | RAG 文档 ID。 |
| `chunk_id` | RAG 切片 ID。 |
| `doc_type` | 项目当前数据资产字段。 |
| `claim_type` | 项目当前数据资产字段。 |
| `claim_text` | 项目当前数据资产字段。 |
| `citation_span` | 项目当前数据资产字段。 |
| `source_title` | 项目当前数据资产字段。 |
| `source_url` | 项目当前数据资产字段。 |
| `source_quality` | 项目当前数据资产字段。 |
| `license_id` | 数据许可证 ID。 |
| `redisplay_allowed` | 项目当前数据资产字段。 |
| `export_allowed` | 项目当前数据资产字段。 |
| `event_time` | 事件发生时间或行情 bar 时间。 |
| `publish_time` | 数据源发布时间。 |
| `ingest_time` | 入库时间。 |
| `available_time` | 系统/模型可用该数据的时间，防未来函数关键字段。 |
| `valid_from` | 项目当前数据资产字段。 |
| `valid_to` | 项目当前数据资产字段。 |
| `symbols` | 项目当前数据资产字段。 |
| `industries` | 项目当前数据资产字段。 |
| `concepts` | 项目当前数据资产字段。 |
| `related_factor_ids` | 项目当前数据资产字段。 |
| `related_model_ids` | 项目当前数据资产字段。 |
| `related_experiment_ids` | 项目当前数据资产字段。 |
| `related_run_ids` | 项目当前数据资产字段。 |
| `evidence_direction` | 项目当前数据资产字段。 |
| `evidence_strength` | 项目当前数据资产字段。 |
| `confidence` | 置信度。 |
| `status` | 项目当前数据资产字段。 |
| `schema_version` | 表结构版本。 |
| `content_hash` | 内容哈希，用于去重和血缘。 |
| `embedding_model` | 项目当前数据资产字段。 |
| `index_version` | 版本字段。 |

### rag_documents

用途：RAG 文档元数据表。

| 列名 | 简单说明 |
|---|---|
| `doc_id` | RAG 文档 ID。 |
| `doc_type` | 项目当前数据资产字段。 |
| `title` | 标题。 |
| `source_url` | 项目当前数据资产字段。 |
| `source_quality` | 项目当前数据资产字段。 |
| `license_id` | 数据许可证 ID。 |
| `publish_time` | 数据源发布时间。 |
| `available_time` | 系统/模型可用该数据的时间，防未来函数关键字段。 |
| `status` | 项目当前数据资产字段。 |
| `content_hash` | 内容哈希，用于去重和血缘。 |

### risk_factor_covariance

用途：风险因子协方差矩阵。

| 列名 | 简单说明 |
|---|---|
| `trade_date` | 交易日期。 |
| `factor_i` | 项目当前数据资产字段。 |
| `factor_j` | 项目当前数据资产字段。 |
| `covariance` | 项目当前数据资产字段。 |
| `lookback_window` | 项目当前数据资产字段。 |
| `version` | 版本字段。 |
| `research_boundary` | 研究边界，强调研究用途而非投资建议。 |

### risk_factor_exposure

用途：股票风险因子暴露表。

| 列名 | 简单说明 |
|---|---|
| `trade_date` | 交易日期。 |
| `symbol` | 股票代码。 |
| `risk_factor_name` | 风险相关字段。 |
| `exposure_value` | 项目当前数据资产字段。 |
| `version` | 版本字段。 |
| `source_factor` | 项目当前数据资产字段。 |
| `research_boundary` | 研究边界，强调研究用途而非投资建议。 |

### simulation_account/simulation_account.json

用途：JSON 状态/服务数据。

| 字段 | 简单说明 |
|---|---|
| `account_id` | 账户 ID。 |
| `account_type` | 项目当前数据资产字段。 |
| `base_currency` | 项目当前数据资产字段。 |
| `initial_cash` | 项目当前数据资产字段。 |
| `cash` | 现金。 |
| `nav` | 净值。 |
| `run_id` | 运行 ID。 |
| `model_version` | 模型版本。 |
| `research_boundary` | 研究边界，强调研究用途而非投资建议。 |
| `broker_connection_status` | 项目当前数据资产字段。 |

### simulation_nav/simulation_nav.json

用途：JSON 状态/服务数据。

| 字段 | 简单说明 |
|---|---|
| `trade_date` | 交易日期。 |
| `nav` | 净值。 |
| `cash` | 现金。 |
| `gross_exposure` | 项目当前数据资产字段。 |
| `max_drawdown` | 最大回撤。 |

### simulation_order/simulation_order.json

用途：JSON 状态/服务数据。

| 字段 | 简单说明 |
|---|---|
| `order_id` | 订单 ID。 |
| `account_id` | 账户 ID。 |
| `symbol` | 股票代码。 |
| `side` | 买卖方向。 |
| `quantity` | 数量。 |
| `limit_price` | 项目当前数据资产字段。 |
| `simulated` | 项目当前数据资产字段。 |
| `source_signal` | 项目当前数据资产字段。 |
| `broker_route` | 项目当前数据资产字段。 |
| `created_at` | 项目当前数据资产字段。 |

### simulation_position/simulation_position.json

用途：JSON 状态/服务数据。

| 字段 | 简单说明 |
|---|---|
| `account_id` | 账户 ID。 |
| `symbol` | 股票代码。 |
| `industry` | 项目当前数据资产字段。 |
| `quantity` | 数量。 |
| `last_price` | 项目当前数据资产字段。 |
| `market_value` | 持仓市值。 |
| `weight` | 权重。 |
| `data_mode` | 项目当前数据资产字段。 |

### specific_risk

用途：个股特异风险表。

| 列名 | 简单说明 |
|---|---|
| `trade_date` | 交易日期。 |
| `symbol` | 股票代码。 |
| `specific_volatility` | 项目当前数据资产字段。 |
| `version` | 版本字段。 |
| `research_boundary` | 研究边界，强调研究用途而非投资建议。 |

### stock_relation_edge

用途：股票关系图谱边表，描述股票之间行业、概念、供应链、相关性等关系。

| 列名 | 简单说明 |
|---|---|
| `as_of_date` | 日期字段。 |
| `src_symbol` | 源股票代码。 |
| `dst_symbol` | 目标股票代码。 |
| `relation_type` | 关系类型。 |
| `relation_weight` | 关系权重。 |
| `direction` | 项目当前数据资产字段。 |
| `confidence` | 置信度。 |
| `strength_score` | 评分字段。 |
| `time_decay` | 项目当前数据资产字段。 |
| `direction_score` | 评分字段。 |
| `start_time` | 时间字段。 |
| `end_time` | 时间字段。 |
| `source` | 数据来源。 |
| `license_id` | 数据许可证 ID。 |
| `data_version` | 数据版本。 |
| `schema_version` | 表结构版本。 |
| `edge_version` | 版本字段。 |
| `available_time` | 系统/模型可用该数据的时间，防未来函数关键字段。 |
| `prediction_time` | 模型做预测的时间点。 |
| `trace_id` | 数据血缘追踪 ID。 |
| `research_boundary` | 研究边界，强调研究用途而非投资建议。 |

## ADS

应用服务层：面向前端、看板和接口的 latest / summary 表。

### ads_backtest_summary

用途：回测摘要表，前端展示策略关键绩效指标。

| 列名 | 简单说明 |
|---|---|
| `run_id` | 运行 ID。 |
| `start_date` | 开始日期。 |
| `end_date` | 结束日期。 |
| `topk` | 持仓股票数量。 |
| `long_short_return` | 多空收益。 |
| `turnover` | 换手率。 |
| `max_drawdown` | 最大回撤。 |
| `sharpe` | 夏普比率。 |
| `data_version` | 数据版本。 |
| `factor_version` | 因子版本。 |
| `model_version` | 模型版本。 |

### ads_dashboard_summary

用途：首页/控制台总览摘要表。

| 列名 | 简单说明 |
|---|---|
| `data_version` | 数据版本。 |
| `latest_trade_date` | 日期字段。 |
| `total_rows` | 总行数。 |
| `snapshot_count` | 项目当前数据资产字段。 |
| `authorized_source_count` | 项目当前数据资产字段。 |
| `restricted_or_blocked` | 项目当前数据资产字段。 |
| `research_boundary` | 研究边界，强调研究用途而非投资建议。 |

### ads_data_quality_summary

用途：数据质量摘要表，用于数据健康看板。

| 列名 | 简单说明 |
|---|---|
| `data_version` | 数据版本。 |
| `table_name` | 表名。 |
| `total_rows` | 总行数。 |
| `duplicate_keys` | 重复主键数量。 |
| `invalid_price_rows` | 异常价格行数。 |
| `missing_required_fields` | 必填字段缺失数量。 |
| `quality_status` | 质量状态。 |

### ads_score_latest

用途：最新选股分数表，前端股票列表和条件筛选页面优先读取。

| 列名 | 简单说明 |
|---|---|
| `trade_date` | 交易日期。 |
| `symbol` | 股票代码。 |
| `score` | 模型综合分。 |
| `rank` | 横截面排名。 |
| `percentile` | 横截面分位。 |
| `model_version` | 模型版本。 |
| `data_version` | 数据版本。 |
| `factor_version` | 因子版本。 |
| `label_version` | 标签版本。 |
| `trace_id` | 数据血缘追踪 ID。 |

## 总结

- ODS：原始数据和入湖治理。
- DWD：清洗、标准化、点时间治理。
- DWS：因子、标签、模型、回测、风险、RAG、图谱等研究资产。
- ADS：前端/看板查询用 latest 和 summary 表。
