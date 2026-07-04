from pathlib import Path
import json
import pyarrow.parquet as pq

root = Path(r"C:/Users/blankxxc/Desktop/work_space/stock_good")
out = root / "docs" / "warehouse_table_columns.md"

layers = [
    ("ODS / Bronze", "data/bronze/synthetic_lakehouse", "原始数据入湖层：保留源数据原貌，并补充来源、版本、入库时间、可用时间、血缘字段。"),
    ("DWD / Silver", "data/silver", "清洗明细事实层：对 ODS 做标准化、清洗和点时间治理，形成可直接计算因子的事实表。"),
    ("DWS / Gold", "data/gold", "研究资产层：沉淀因子、标签、训练样本、模型信号、回测、风险、RAG、图谱和模拟盘资产。"),
    ("ADS", "data/ads", "应用服务层：面向前端、看板和接口的 latest / summary 表。"),
]

purpose = {
    "ods_market_daily_raw": "日频行情原始表，作为日频因子、标签、回测的基础输入。",
    "ods_market_minute_raw": "分钟行情原始表，用于分钟因子、实时特征和回放验证。",
    "ods_market_tick_raw": "tick 行情原始表，用于盘口、微观结构和实时因子研究。",
    "ods_trade_raw": "逐笔成交原始表，用于成交方向、成交冲击和短周期流动性研究。",
    "ods_orderbook_raw": "盘口原始表，用于买卖盘压力、价差、订单簿不平衡等因子。",
    "ods_financial_statement_raw": "财报原始明细表，采用 item_name/item_value 长表结构，是基本面因子来源。",
    "ods_announcement_raw": "公告原始事件表，用于公告事件、公告情绪和 RAG 证据。",
    "ods_news_raw": "新闻原始事件表，用于新闻情绪、事件因子和 RAG 文档入口。",
    "ods_macro_raw": "宏观事件/指标原始表，用于市场 regime、宏观事件和风险偏好因子。",
    "ods_fund_flow_raw": "资金流原始表，用于主力净流入和资金行为类因子。",
    "ods_northbound_raw": "北向资金原始表，用于外资流入、北向持仓类因子，并受许可证治理约束。",
    "dwd_stock_daily_bar": "清洗后的日频行情事实表，补充复权、停牌、ST、涨跌停，是离线日频因子的主输入。",
    "dwd_stock_daily_bar_spark": "Spark 检查/验证版本的日频行情事实表。",
    "dwd_stock_minute_bar": "清洗后的分钟行情事实表，用于分钟因子和实时链路验证。",
    "dwd_financial_statement": "清洗后的财报明细表，用于构建真实基本面因子。",
    "news_document": "新闻文档表，保存新闻正文和文档元数据，供事件抽取和 RAG 使用。",
    "announcement_document": "公告文档表，保存公告正文和文档元数据，供事件抽取和 RAG 使用。",
    "event_extraction_result": "新闻/公告统一事件抽取结果表，是事件因子的明细基础。",
    "dwd_news_event": "新闻事件标准化结果表，面向新闻情绪和事件因子。",
    "dwd_announcement_event": "公告事件标准化结果表，面向公告情绪和事件因子。",
    "entity_symbol_mapping": "实体到股票代码的映射表，用于把新闻、公告中的实体映射到 symbol。",
    "reference": "轻量参考维表/测试表。",
    "factor_daily_panel_long": "正式日频因子长表，一行一个股票-日期-因子，便于因子治理和单因子分析。",
    "factor_daily_panel": "早期/简版日频因子表，用于 lakehouse MVP 链路验证。",
    "factor_daily_panel_spark_check": "Spark 检查用因子长表。",
    "factor_intraday_panel": "分钟/实时因子面板。",
    "factor_news_sentiment_panel": "新闻情绪因子面板。",
    "factor_daily_panel_event_regime_event_regime": "事件和市场状态类因子的长表。",
    "factor_market_regime_panel": "市场状态/regime 因子表，用于描述市场宽度、波动、风险偏好和风格环境。",
    "factor_relation_panel": "关系图谱传播因子宽表。",
    "factor_daily_panel_relation_graph_relation": "关系图谱因子的长表版本。",
    "stock_relation_edge": "股票关系图谱边表，描述股票之间行业、概念、供应链、相关性等关系。",
    "model_feature_matrix_wide": "基础模型训练宽表，一行一个股票-日期样本，列为离线因子。",
    "model_feature_matrix_spark_check": "Spark 检查用的小型模型特征宽表。",
    "model_feature_matrix_wide_event_regime": "在基础宽表上增加新闻、公告、事件和市场 regime 特征。",
    "model_feature_matrix_wide_relation_graph": "在事件/regime 宽表上增加关系图谱传播特征。",
    "label_cross_sectional_return": "横截面收益预测标签表，是监督学习 y 值来源。",
    "model_signal_cross_sectional": "模型横截面信号表，保存 score、rank、概率、置信度等预测结果。",
    "advanced_model_predictions": "高级模型预测表，服务 MASTER、StockMixer、HIST、TRSR 等 adapter。",
    "portfolio_backtest_result": "组合回测日度结果表。",
    "portfolio_risk_report": "组合风险和归因报告表。",
    "risk_factor_exposure": "股票风险因子暴露表。",
    "risk_factor_covariance": "风险因子协方差矩阵。",
    "specific_risk": "个股特异风险表。",
    "rag_documents": "RAG 文档元数据表。",
    "rag_chunks": "RAG 文档切片表。",
    "rag_claims": "claim-level RAG 证据表。",
    "graph_model_adapters": "图模型适配产物目录，包含 HIST/TRSR 所需矩阵、张量和映射。",
    "ads_dashboard_summary": "首页/控制台总览摘要表。",
    "ads_score_latest": "最新选股分数表，前端股票列表和条件筛选页面优先读取。",
    "ads_backtest_summary": "回测摘要表，前端展示策略关键绩效指标。",
    "ads_data_quality_summary": "数据质量摘要表，用于数据健康看板。",
}

exact = {
    "trade_date":"交易日期。", "symbol":"股票代码。", "event_time":"事件发生时间或行情 bar 时间。", "publish_time":"数据源发布时间。",
    "available_time":"系统/模型可用该数据的时间，防未来函数关键字段。", "prediction_time":"模型做预测的时间点。", "ingest_time":"入库时间。",
    "trace_id":"数据血缘追踪 ID。", "source":"数据来源。", "source_version":"源数据版本。", "schema_version":"表结构版本。", "data_version":"数据版本。",
    "research_boundary":"研究边界，强调研究用途而非投资建议。", "open":"开盘价。", "high":"最高价。", "low":"最低价。", "close":"收盘价。",
    "volume":"成交量。", "amount":"成交额。", "vwap":"成交均价。", "price":"最新成交价。", "bid_price":"买盘价格。", "ask_price":"卖盘价格。",
    "bid_volume":"买盘数量。", "ask_volume":"卖盘数量。", "trade_id":"逐笔成交 ID。", "trade_price":"成交价格。", "trade_volume":"成交数量。",
    "ods_table":"来源 ODS 表名。", "ingest_date":"入湖日期分区。", "report_period":"财报报告期。", "announce_time":"公告/财报披露时间。",
    "statement_type":"报表类型。", "item_name":"财务科目名称。", "item_value":"财务科目值。", "event_id":"事件 ID。", "document_id":"文档 ID。",
    "document_type":"文档类型。", "doc_id":"RAG 文档 ID。", "chunk_id":"RAG 切片 ID。", "claim_id":"RAG claim ID。", "title":"标题。", "content":"正文内容。",
    "content_hash":"内容哈希，用于去重和血缘。", "related_symbols":"关联股票列表。", "related_industries":"关联行业列表。", "event_type":"事件类型。",
    "sentiment":"情绪标签。", "confidence":"置信度。", "license_id":"数据许可证 ID。", "license_status":"授权状态。", "adj_factor":"复权因子。",
    "adj_close":"复权收盘价。", "paused":"是否停牌。", "pause_flag":"是否停牌。", "st_flag":"是否 ST。", "limit_up":"涨停价或涨停标记。",
    "limit_down":"跌停价或跌停标记。", "factor_name":"因子名称。", "factor_value":"因子值。", "factor_version":"因子版本。", "factor_set":"因子集合。",
    "factor_category":"因子类别。", "category":"因子类别。", "feature_set_version":"特征集合版本。", "industry_name":"行业名称。", "run_id":"运行 ID。",
    "experiment_id":"实验 ID。", "model_name":"模型名称。", "model_version":"模型版本。", "label_version":"标签版本。", "horizon":"预测/标签周期。",
    "score":"模型综合分。", "rank":"横截面排名。", "percentile":"横截面分位。", "forward_return":"未来收益，研究评估标签，前端实盘页面不应直接展示。",
    "up_label":"是否上涨标签。", "excess_return":"相对基准超额收益。", "industry_neutral_return":"行业中性收益。", "cs_zscore_label":"横截面标准化标签。",
    "quantile_label":"分位标签。", "tradable_flag":"是否可交易。", "split_id":"训练/验证/测试切分 ID。", "target_label":"目标标签名。", "probability_up":"上涨概率。",
    "probability_down":"下跌概率。", "leakage_check_status":"未来函数/数据泄漏检查状态。", "portfolio_id":"组合 ID。", "benchmark":"基准指数或基准组合。",
    "gross_return":"未扣交易成本收益。", "transaction_cost":"交易成本。", "daily_return":"扣成本后日收益。", "turnover":"换手率。", "nav":"净值。",
    "top_k":"持仓股票数量。", "max_drawdown":"最大回撤。", "start_date":"开始日期。", "end_date":"结束日期。", "topk":"持仓股票数量。", "long_short_return":"多空收益。",
    "sharpe":"夏普比率。", "table_name":"表名。", "total_rows":"总行数。", "duplicate_keys":"重复主键数量。", "invalid_price_rows":"异常价格行数。",
    "missing_required_fields":"必填字段缺失数量。", "quality_status":"质量状态。", "account_id":"账户 ID。", "order_id":"订单 ID。", "side":"买卖方向。",
    "quantity":"数量。", "cash":"现金。", "weight":"权重。", "market_value":"持仓市值。", "stock_id":"模型内部股票 ID。", "src_symbol":"源股票代码。",
    "dst_symbol":"目标股票代码。", "src_id":"源股票内部 ID。", "dst_id":"目标股票内部 ID。", "relation_type":"关系类型。", "relation_type_id":"关系类型 ID。",
    "relation_weight":"关系权重。", "relation_feature_version":"关系特征版本。", "community_id":"图社区 ID。", "feature_name":"特征名称。", "feature_value":"特征值。",
    "label_value":"标签值。", "concept_id":"概念 ID。", "concept_weight":"股票与概念的权重。"
}

def describe(col: str) -> str:
    if col in exact:
        return exact[col]
    if col.startswith("return_"):
        return col.replace("return_", "过去 ") + " 收益。"
    if col.startswith("momentum_"):
        return col.replace("momentum_", "") + " 动量因子。"
    if col.startswith("reversal_"):
        return col.replace("reversal_", "") + " 反转因子。"
    if col.startswith("volatility_"):
        return col.replace("volatility_", "") + " 波动率。"
    if col.startswith("amount_mean_"):
        return col.replace("amount_mean_", "") + " 平均成交额。"
    if col.startswith("volume_mean_"):
        return col.replace("volume_mean_", "") + " 平均成交量。"
    if col.startswith("turnover_proxy_"):
        return col.replace("turnover_proxy_", "") + " 换手代理指标。"
    if col.startswith("ma") and col.endswith("_gap"):
        return col[2:-4] + " 日均线偏离。"
    if "sentiment" in col:
        return "情绪相关特征。"
    if "event_decay" in col:
        return "事件衰减特征。"
    if "zscore" in col:
        return "标准化 z-score 特征。"
    if "proxy" in col:
        return "代理变量。"
    if "risk" in col:
        return "风险相关字段。"
    if "attribution" in col:
        return "归因字段。"
    if "version" in col:
        return "版本字段。"
    if col.endswith("_id"):
        return "标识 ID。"
    if col.endswith("_time"):
        return "时间字段。"
    if col.endswith("_date"):
        return "日期字段。"
    if "return" in col:
        return "收益相关字段。"
    if "score" in col:
        return "评分字段。"
    if "flag" in col:
        return "布尔标记字段。"
    return "项目当前数据资产字段。"

def column_table(cols, head="列名"):
    rows = [f"| {head} | 简单说明 |", "|---|---|"]
    for col in cols:
        rows.append(f"| `{col}` | {describe(col)} |")
    return rows

md = [
    "# stock_good 数仓分层表字段说明",
    "",
    "本文档按 ODS / DWD / DWS / ADS 分层整理当前项目实际存在的数据表，并对每个字段做简要说明。",
    "",
    "## 阅读提示",
    "",
    "- `available_time <= prediction_time` 是防未来函数的核心约束。",
    "- DWS 中的 `forward_return`、`up_label`、`label_*` 等字段属于研究评估标签，不应作为真实选股页面的筛选条件直接展示。",
    "- `trace_id`、各类 `*_version` 字段用于数据血缘、复现实验和版本治理。",
    "",
]

for layer, rel, intro in layers:
    md += [f"## {layer}", "", intro, ""]
    base = root / rel
    for d in sorted([p for p in base.iterdir() if p.is_dir()]):
        name = d.name
        if name == "graph_model_adapters":
            md += [f"### {name}", "", f"用途：{purpose[name]}", ""]
            h = d / "hist_trsr"
            for p in sorted(h.glob("*")):
                md += [f"#### hist_trsr/{p.name}", ""]
                if p.suffix == ".parquet":
                    cols = pq.ParquetFile(p).schema.names
                    md += [f"用途：图模型适配文件 `{p.name}`。", ""] + column_table(list(cols)) + [""]
                elif p.suffix == ".json":
                    md += [f"用途：图模型映射文件 `{p.name}`。", "", "| 结构 | 简单说明 |", "|---|---|", "| JSON mapping | ID 与名称/代码之间的映射字典。 |", ""]
            continue

        files = list(d.glob("**/*.parquet"))
        jsons = list(d.glob("*.json"))
        if files:
            cols = pq.ParquetFile(files[0]).schema.names
            md += [f"### {name}", "", f"用途：{purpose.get(name, '项目数据资产表。')}", ""] + column_table(list(cols)) + [""]
        elif jsons:
            for j in sorted(jsons):
                obj = json.loads(j.read_text(encoding="utf-8"))
                if isinstance(obj, list) and obj:
                    cols = list(obj[0].keys())
                elif isinstance(obj, dict):
                    cols = list(obj.keys())
                else:
                    cols = []
                table_name = f"{name}/{j.name}"
                md += [f"### {table_name}", "", f"用途：JSON 状态/服务数据。", ""] + column_table(cols, "字段") + [""]

md += [
    "## 总结",
    "",
    "- ODS：原始数据和入湖治理。",
    "- DWD：清洗、标准化、点时间治理。",
    "- DWS：因子、标签、模型、回测、风险、RAG、图谱等研究资产。",
    "- ADS：前端/看板查询用 latest 和 summary 表。",
    "",
]

out.parent.mkdir(parents=True, exist_ok=True)
out.write_text("\n".join(md), encoding="utf-8")
print(out)
print(f"lines={len(md)} size_bytes={out.stat().st_size}")
