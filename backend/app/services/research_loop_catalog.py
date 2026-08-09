from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd
import yaml


def project_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _read_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def _read_parquet(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    return pd.read_parquet(path)


def research_loop_report() -> dict[str, Any]:
    return _read_json(project_root() / "reports" / "research_loop" / "research_loop_research_loop_report.json")


def _real_csi300_daily() -> pd.DataFrame:
    return _read_parquet(project_root() / "data" / "real" / "csi300_daily" / "part-000.parquet")


def _model_feature_matrix_wide() -> pd.DataFrame:
    return _read_parquet(project_root() / "data" / "gold" / "model_feature_matrix_wide" / "part-000.parquet")


def _json_records(frame: pd.DataFrame) -> list[dict[str, Any]]:
    if frame.empty:
        return []
    return json.loads(frame.to_json(orient="records", force_ascii=False))


def _safe_float(value: Any) -> float | None:
    if value is None or pd.isna(value):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _safe_json_value(value: Any, fallback: Any) -> Any:
    if value is None:
        return fallback
    if isinstance(value, (dict, list)):
        return value
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return fallback
    try:
        if pd.isna(value):
            return fallback
    except (TypeError, ValueError):
        return fallback
    return fallback


_UNKNOWN_INDUSTRY_MARKERS = {"", "unknown", "unknown_real_csi300", "nan", "none", "null", "未知", "未知行业"}

_KEYWORD_INDUSTRY_RULES: list[tuple[tuple[str, ...], str]] = [
    (("银行", "农商", "城商"), "银行"),
    (("证券", "申万宏源", "中信建投", "东方财富", "华泰", "国泰海通"), "证券"),
    (("保险", "人寿", "平安", "太保", "新华保险"), "保险"),
    (("白酒", "茅台", "五粮液", "泸州老窖", "洋河", "古井贡", "山西汾酒", "今世缘", "迎驾贡酒"), "白酒"),
    (("啤酒", "青岛啤酒", "燕京啤酒"), "啤酒饮料"),
    (("食品", "伊利", "海天", "双汇", "安井", "东鹏饮料", "养元", "涪陵榨菜"), "食品饮料"),
    (("医药", "药", "医疗", "生物", "疫苗", "爱尔", "迈瑞", "恒瑞", "片仔癀", "云南白药", "长春高新"), "医药生物"),
    (("汽车", "比亚迪", "长安", "长城", "赛力斯", "江淮", "宇通", "上汽", "广汽", "福耀", "潍柴"), "汽车"),
    (("电池", "锂", "宁德", "亿纬", "天赐", "华友", "赣锋", "恩捷", "盐湖", "藏格"), "电力设备/新能源"),
    (("光伏", "阳光电源", "隆基", "通威", "TCL中环", "晶澳", "晶科", "天合", "正泰", "锦浪"), "光伏设备"),
    (("半导体", "芯片", "中芯", "韦尔", "兆易", "紫光", "寒武纪", "海光", "北方华创", "中微", "卓胜微", "澜起"), "半导体"),
    (("软件", "信息", "网络", "数据", "用友", "金山", "科大讯飞", "恒生电子", "三六零", "同花顺", "中科曙光", "浪潮信息"), "计算机"),
    (("通信", "中兴", "中国移动", "中国电信", "中国联通", "中际旭创", "新易盛", "光迅", "亨通"), "通信"),
    (("家电", "美的", "格力", "海尔", "海信", "公牛"), "家用电器"),
    (("地产", "万科", "保利发展", "招商蛇口", "华侨城"), "房地产"),
    (("建筑", "中国建筑", "中国中铁", "中国铁建", "中国交建", "中国电建", "中国能建", "中国化学"), "建筑装饰"),
    (("煤", "神华", "兖矿", "陕西煤业", "中煤能源"), "煤炭"),
    (("石油", "石化", "海油", "中国石油", "中国石化", "中国海油", "荣盛石化", "恒力石化", "东方盛虹"), "石油石化"),
    (("钢", "宝钢", "中信特钢", "华菱钢铁"), "钢铁"),
    (("有色", "铜", "铝", "紫金", "洛阳钼业", "山东黄金", "中国铝业", "铜陵有色", "江西铜业", "天山铝业"), "有色金属"),
    (("化工", "万华", "卫星化学", "龙佰", "宝丰能源", "新和成"), "基础化工"),
    (("电力", "能源", "核电", "长江电力", "三峡能源", "国投电力", "华能", "华电", "浙能", "川投能源"), "公用事业"),
    (("机场", "航空", "航发", "船舶", "中航", "洪都", "中国船舶", "中国重工", "春秋航空", "南方航空", "中国国航"), "国防军工/交通运输"),
    (("港", "高速", "快递", "顺丰", "京沪高铁", "大秦铁路", "上港", "宁波港"), "交通运输"),
    (("传媒", "出版", "芒果", "分众", "三七互娱", "世纪华通", "昆仑万维", "恺英网络"), "传媒"),
    (("免税", "百货", "商贸", "中国中免", "永辉", "小商品城"), "商贸零售"),
    (("牧原", "温氏", "海大", "新希望", "大北农", "圣农"), "农林牧渔"),
    (("机械", "重工", "机器人", "三一", "徐工", "中联重科", "汇川技术", "先导智能", "中国中车"), "机械设备"),
    (("建材", "水泥", "海螺", "东方雨虹", "北新建材"), "建筑材料"),
]

_SYMBOL_INDUSTRY_OVERRIDES = {
    "000001.SZ": "银行",
    "601398.SH": "银行",
    "601288.SH": "银行",
    "601939.SH": "银行",
    "600519.SH": "白酒",
    "000858.SZ": "白酒",
    "300750.SZ": "电力设备/新能源",
    "002594.SZ": "汽车",
}


def _display_industry_name(symbol: object, stock_name: object, raw_industry: object) -> str:
    raw = str(raw_industry or "").strip()
    if raw and raw.lower() not in _UNKNOWN_INDUSTRY_MARKERS and not raw.lower().startswith("unknown"):
        return raw
    normalized_symbol = str(symbol or "").upper()
    if normalized_symbol in _SYMBOL_INDUSTRY_OVERRIDES:
        return _SYMBOL_INDUSTRY_OVERRIDES[normalized_symbol]
    name = str(stock_name or "")
    for keywords, industry in _KEYWORD_INDUSTRY_RULES:
        if any(keyword in name for keyword in keywords):
            return industry
    return "沪深300综合"


def _with_display_industry(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        return frame
    output = frame.copy()
    if "industry_name" not in output.columns:
        output["industry_name"] = ""
    output["industry_name"] = [
        _display_industry_name(row.get("symbol"), row.get("stock_name"), row.get("industry_name"))
        for _, row in output.iterrows()
    ]
    return output


def _stock_name_map() -> pd.DataFrame:
    daily = _real_csi300_daily()
    if daily.empty or "stock_name" not in daily.columns:
        return pd.DataFrame(columns=["symbol", "stock_name"])
    return daily.sort_values("trade_date").drop_duplicates("symbol", keep="last")[["symbol", "stock_name"]]



SCREENING_WINDOWS = [5, 10, 20, 30, 60, 250]
SCREENING_BOOLEAN_COLUMNS = [
    "non_st", "ma_bullish", "return_10d_gt_15", "close_above_ma10", "market_cap_gt_100b",
    "all_conditions_met", "ma_bullish_order", "ma_all_up",
]
CONDITION_TEXT_COLUMNS = {"stock_name", "symbol"}
CONDITION_CATEGORY_COLUMNS = {"industry_name", "trade_date"}
CONDITION_NUMERIC_OPERATORS = ["gt", "gte", "lt", "lte", "eq", "between"]
CONDITION_TEXT_OPERATORS = ["contains"]
CONDITION_DISCRETE_OPERATORS = ["eq"]
MODEL_FEATURE_COLUMNS = [
    "momentum_20d", "volatility_20d", "reversal_5d", "amount_percentile_20d", "amihud_20d",
    "volume_shock_20d", "price_volume_corr_20d", "vwap_deviation", "ma20_gap", "ma60_gap",
    "market_cap_proxy", "float_market_cap_proxy", "beta_20d", "beta_60d", "value_proxy", "quality_proxy",
    "growth_proxy_20d", "low_volatility_proxy", "liquidity_proxy", "industry_neutral_return_20d", "cs_rank_return_20d",
]
CONDITION_SCREEN_CRITERIA = {
    "non_st": {"label": "非ST", "description": "没有退市风险：当前数据用 st_flag=false、delist_flag=false 且股票名称不含 ST/*ST 作为可执行代理；净利、营收、审计意见、分红、违法等正式触发项需接入财报/公告治理数据后严格判断。"},
    "ma_bullish": {"label": "均线多头排列", "description": "MA5 > MA10 > MA20 > MA30 > MA60 > MA250，且这些均线相对上一交易日向上；任何均线缺失都按“否”展示。"},
    "return_10d_gt_15": {"label": "10个交易日内涨幅大于15%", "description": "close / close.shift(10) - 1 > 15%；历史不足或涨幅未达标都按“否”展示。"},
    "close_above_ma10": {"label": "股价在10日均线上", "description": "当天收盘价 close > MA10；MA10 缺失时按“否”展示。"},
    "market_cap_gt_100b": {"label": "市值大于100亿", "description": "当前行情缺少总市值字段，先用 amount / turnover_rate 估算流通市值，单位亿元；缺失或低于阈值按“否”。后续可替换为正式 total_market_cap。"},
    "all_conditions_met": {"label": "综合条件通过", "description": "以上五个条件同时为“是”才为“是”；用于人工判断和排序，不直接构成交易建议。"},
}
CONDITION_BASE_COLUMNS = [
    "stock_name", "symbol", "trade_date", "industry_name", "non_st", "ma_bullish", "return_10d_gt_15",
    "close_above_ma10", "market_cap_gt_100b", "all_conditions_met",
]
CONDITION_FACTOR_COLUMN_CATALOG = {
    "close": "最近交易日收盘价", "pct_change": "最近交易日涨跌幅", "return_10d": "近10个交易日涨跌幅",
    "estimated_market_cap_billion": "估算流通市值（亿元，行情代理）", "ma5": "5日均线", "ma10": "10日均线",
    "ma20": "20日均线", "ma30": "30日均线", "ma60": "60日均线", "ma250": "250日均线",
    "ma_bullish_order": "MA5>MA10>MA20>MA30>MA60>MA250", "ma_all_up": "MA5/10/20/30/60/250 均向上",
    "turnover_rate": "换手率", "amount_billion": "成交额（亿元）", "volume": "成交量",
    "momentum_20d": "20日动量因子", "volatility_20d": "20日波动率因子", "reversal_5d": "5日反转因子",
    "amount_percentile_20d": "20日成交额分位", "amihud_20d": "20日 Amihud 非流动性", "volume_shock_20d": "20日量能冲击",
    "price_volume_corr_20d": "20日价量相关性", "vwap_deviation": "VWAP 偏离", "ma20_gap": "收盘价相对 MA20 偏离",
    "ma60_gap": "收盘价相对 MA60 偏离", "market_cap_proxy": "规模/市值代理因子", "float_market_cap_proxy": "流通市值代理因子",
    "beta_20d": "20日市场 Beta", "beta_60d": "60日市场 Beta", "value_proxy": "价值代理因子", "quality_proxy": "质量代理因子",
    "growth_proxy_20d": "20日成长代理因子", "low_volatility_proxy": "低波动代理因子", "liquidity_proxy": "流动性代理因子",
    "industry_neutral_return_20d": "20日行业中性收益", "cs_rank_return_20d": "20日截面收益排名",
}
CONDITION_FACTOR_COLUMNS = list(CONDITION_FACTOR_COLUMN_CATALOG)
ST_STAR_RULES = [
    "*ST：扣非净利为负且营收低于3亿元、年末净资产为负、年报无法表示意见/否定意见、2025新增分红不达标、重大违法等任一触发。",
    "ST：资金占用或占净资产比例超阈值且逾期未还、连续内控审计非标未整改、年报/半年报披露超期、违规担保未整改或控制权混乱等任一触发。",
    "当前本地行情表没有完整财报/审计/公告字段，因此页面把这些规则展示为治理口径，并用 st_flag/delist_flag/名称含ST 作为可执行过滤代理。",
]
MARKET_COLUMNS = [
    "symbol", "stock_name", "industry_name", "trade_date", "open", "high", "low", "close", "previous_close",
    "pct_change", "volume", "amount", "amount_billion", "turnover_rate", "tradable_flag", "research_boundary",
]
PRICE_SERIES_COLUMNS = ["trade_date", "open", "high", "low", "close", "volume", "amount", "pct_change", "ma5", "ma20", "turnover_rate"]
PREDICTION_COLUMNS = [
    "trade_date", "prediction_target_date", "symbol", "horizon", "probability_up", "probability_down", "score", "rank",
    "percentile", "confidence", "model_name", "model_family", "model_version", "market_regime",
    "sentiment_score", "sentiment_source", "sentiment_coverage", "relation_signal",
    "global_probability_up", "sentiment_probability_up", "regime_adjustment",
    "predicted_relative_change", "predicted_relative_change_pct", "signal_direction",
    "information_source", "sentiment_polarity_used",
]
MARKET_NOTES = [
    {"title": "当前沪深300重训", "body": "保留 IJCAI 2025 COGRASP 作者网络结构，使用当前 300 只股票和截至 2026-07-24 的本地日频数据重新训练。"},
    {"title": "原始回归输出", "body": "页面展示本地重训 checkpoint 的下一交易日相对涨跌回归值和横截面排名，不进行概率校准。"},
    {"title": "关系图口径", "body": "当前新闻缓存不足以覆盖 300 只股票，因此关系图使用历史日收益绝对相关性 Top8；不包含正负文本情绪。"},
    {"title": "样本外表现", "body": "当前测试集 RankIC 为负且样本量较小，只能作为研究候选排序，不能视为已验证的交易信号。"},
    {"title": "因子复核", "body": "下方因子摘要来自本地 factor_store 报告，正式使用前需要做样本外、成本、容量和风控复核。"},
]

def _score_model_catalog(root: Path) -> list[dict[str, Any]]:
    definitions = [
        {
            "id": "cograsp",
            "label": "COGRASP 当前沪深300重训",
            "description": "基于价格序列与收益相关性图的 COGRASP 1d 回归模型。",
            "report": root / "reports" / "research_loop" / "live_predictions_report.json",
            "predictions": root / "reports" / "research_loop" / "live_predictions.parquet",
        },
        {
            "id": "sentiment_event",
            "label": "情绪/事件融合 LightGBM",
            "description": "融合市场情绪代理和按可用时间对齐的可选真实新闻情绪。",
            "report": root / "reports" / "research_loop" / "sentiment_event_predictions_report.json",
            "predictions": root / "reports" / "research_loop" / "sentiment_event_predictions.parquet",
        },
        {
            "id": "finmamba",
            "label": "FinMamba 官方模型",
            "description": "市场引导动态图 GAT + 多层级 Mamba；直接使用作者原版模型结构。",
            "report": root / "reports" / "research_loop" / "finmamba_predictions_report.json",
            "predictions": root / "reports" / "research_loop" / "finmamba_predictions.parquet",
        },
    ]
    catalog: list[dict[str, Any]] = []
    for definition in definitions:
        report = _read_json(definition["report"])
        available = bool(
            definition["predictions"].exists() and report.get("status") == "ok"
        )
        status = "ready" if available else str(report.get("status") or "pending")
        catalog.append(
            {
                "id": definition["id"],
                "label": definition["label"],
                "description": definition["description"],
                "status": status,
                "latest_trade_date": report.get("latest_trade_date"),
                "model_version": report.get("model_version"),
                "integration_status": report.get("integration_status"),
                "runtime_requirements": report.get("runtime_requirements"),
                "runtime_blockers": report.get("runtime_blockers"),
            }
        )
    return catalog


def scores_payload(research_boundary: str, model: str = "cograsp") -> dict[str, Any]:
    root = project_root()
    aliases = {
        "cograsp": "cograsp",
        "default": "cograsp",
        "sentiment": "sentiment_event",
        "sentiment_event": "sentiment_event",
        "event": "sentiment_event",
        "finmamba": "finmamba",
        "mamba": "finmamba",
    }
    selected_model = aliases.get(str(model or "cograsp").strip().lower(), "cograsp")
    available_models = _score_model_catalog(root)
    legacy_report = research_loop_report()
    backtest_predictions = _read_parquet(root / "reports" / "research_loop" / "predictions.parquet")
    if selected_model == "finmamba":
        live_report = _read_json(
            root / "reports" / "research_loop" / "finmamba_predictions_report.json"
        )
        live_predictions = _read_parquet(
            root / "reports" / "research_loop" / "finmamba_predictions.parquet"
        )
        score_source = "official_finmamba_current_csi300_checkpoint"
        maturity = "L2-finmamba-official-current-csi300"
        model_description = "作者原版 FinMamba：市场引导动态图 GAT + 多层级 Mamba，使用日频量价和行业衰减关系。"
        candidate_reason = "作者原版 FinMamba 的下一日回归值排名靠前；需结合样本外指标和交易成本人工复核。"
        pool_definition = "取作者原版 FinMamba 下一日收益回归值排名靠前的 Top20；本站只做沪深300数据格式适配，不改模型结构与算法。"
    elif selected_model == "sentiment_event":
        live_report = _read_json(
            root / "reports" / "research_loop" / "sentiment_event_predictions_report.json"
        )
        live_predictions = _read_parquet(
            root / "reports" / "research_loop" / "sentiment_event_predictions.parquet"
        )
        score_source = "sentiment_event_fusion_lgbm_checkpoint"
        maturity = "L2-sentiment-event-fusion-lightgbm"
        model_description = "融合股票时序、市场情绪代理和按可用时间对齐的可选真实新闻情绪。"
        candidate_reason = "情绪/事件融合模型的下一日回归值排名靠前；需结合新闻覆盖率与样本外指标人工复核。"
        pool_definition = "取情绪/事件融合 LightGBM 下一日相对涨跌回归值排名靠前的 Top20；市场代理始终启用，真实新闻为可选增强。"
    else:
        live_report = _read_json(root / "reports" / "research_loop" / "live_predictions_report.json")
        live_predictions = _read_parquet(root / "reports" / "research_loop" / "live_predictions.parquet")
        score_source = "current_csi300_retrained_cograsp_checkpoint"
        maturity = "L2-cograsp-current-csi300-retrained"
        model_description = "保留 COGRASP 作者网络结构，以当前沪深300日频和收益相关性图重训。"
        candidate_reason = "当前沪深300重训版 COGRASP 的下一日相对涨跌回归值排名靠前；样本外表现较弱，需人工复核。"
        pool_definition = "取当前沪深300重训版 COGRASP 下一日相对涨跌回归值排名靠前的 Top20；没有二次概率校准，且样本外效果尚弱。"
    if not live_predictions.empty and live_report.get("status") == "ok":
        predictions = live_predictions
        report = live_report
    elif selected_model == "cograsp":
        predictions = backtest_predictions
        report = legacy_report
        score_source = "walk_forward_backtest_predictions"
    else:
        predictions = pd.DataFrame()
        report = live_report
    if report.get("status") != "ok" or predictions.empty:
        return {
            "module": "scores",
            "status": "research_loop_scores_pending",
            "maturity": "L1-route-stub",
            "selected_model": selected_model,
            "available_models": available_models,
            "model_description": live_report.get("model_description") or model_description,
            "model_family": live_report.get("model_family"),
            "model_version": live_report.get("model_version"),
            "latest_trade_date": live_report.get("latest_trade_date"),
            "latest_training_label_date": live_report.get("latest_training_label_date"),
            "training_sample_count": live_report.get("training_sample_count"),
            "integration_status": live_report.get("integration_status") or "training_pending",
            "runtime_requirements": live_report.get("runtime_requirements"),
            "runtime_blockers": live_report.get("runtime_blockers") or [],
            "training_command": live_report.get("training_command"),
            "upstream_source": live_report.get("upstream_source"),
            "model_methodology": live_report.get("model_methodology"),
            "paper_references": live_report.get("paper_references"),
            "architecture_modified": live_report.get("architecture_modified"),
            "algorithm_modified": live_report.get("algorithm_modified"),
            "data_pipeline_adapted": live_report.get("data_pipeline_adapted"),
            "research_boundary": research_boundary,
        }
    name_map = _stock_name_map()
    if not name_map.empty and "stock_name" not in predictions.columns:
        predictions = predictions.merge(name_map, on="symbol", how="left")
    predictions = _with_display_industry(predictions)
    latest_date = str(predictions["trade_date"].max())
    base_cols = [
        "trade_date", "prediction_target_date", "symbol", "stock_name", "industry_name", "score", "probability_up", "probability_down",
        "rank", "percentile", "horizon", "model_name", "model_family", "model_version", "confidence",
        "market_regime", "sentiment_score", "sentiment_source", "sentiment_coverage", "relation_signal",
        "global_probability_up", "sentiment_probability_up", "regime_adjustment", "leakage_check_status",
        "predicted_relative_change", "predicted_relative_change_pct", "signal_direction",
        "information_source", "sentiment_polarity_used",
    ]
    available_horizons = sorted(predictions["horizon"].astype(str).unique().tolist(), key=lambda h: int(h.rstrip("d")) if h.rstrip("d").isdigit() else 999)
    horizon_rankings: dict[str, list[dict[str, Any]]] = {}
    latest_trade_date_by_horizon: dict[str, str] = {}

    for horizon in available_horizons:
        horizon_frame = predictions[predictions["horizon"].astype(str) == horizon].copy()
        horizon_latest_date = str(horizon_frame["trade_date"].max())
        latest_trade_date_by_horizon[horizon] = horizon_latest_date
        latest = horizon_frame[horizon_frame["trade_date"].astype(str) == horizon_latest_date].sort_values("rank").head(20)
        horizon_rankings[horizon] = _json_records(latest[[col for col in base_cols if col in latest.columns]])
    rows = horizon_rankings.get("1d") or next(iter(horizon_rankings.values()), [])
    candidate_pool = []
    for row in rows[:20]:
        candidate_pool.append({
            **row,
            "candidate_reason": candidate_reason,
            "review_action": "查看个股详情 / 对照条件测试 / 进入回测风险复核",
        })

    return {
        "module": "scores",
        "status": "research_loop_scores_ready",
        "maturity": maturity,
        "research_boundary": research_boundary,
        "selected_model": selected_model,
        "available_models": available_models,
        "model_description": report.get("model_description") or model_description,
        "run_id": report.get("run_id"),
        "experiment_id": report.get("experiment_id"),
        "latest_trade_date": latest_date,
        "latest_trade_date_by_horizon": latest_trade_date_by_horizon,
        "prediction_rows": report.get("prediction_rows"),
        "display_score_rows": int(len(predictions)),
        "score_source": score_source,
        "available_horizons": available_horizons,
        "model_version": report.get("model_version"),
        "model_family": report.get("model_family") or (rows[0].get("model_family") if rows else None),
        "model_methodology": report.get("model_methodology"),
        "integration_status": report.get("integration_status"),
        "runtime_requirements": report.get("runtime_requirements"),
        "runtime_blockers": report.get("runtime_blockers"),
        "training_command": report.get("training_command"),
        "upstream_source": report.get("upstream_source"),
        "prediction_target_date": report.get("prediction_target_date"),
        "prediction_target_date_is_estimated": report.get("prediction_target_date_is_estimated"),
        "latest_training_label_date": report.get("latest_training_label_date"),
        "training_sample_count": report.get("training_sample_count"),
        "test_metrics": report.get("test_metrics"),
        "relationship_graph": report.get("relationship_graph"),
        "sentiment_status": report.get("sentiment_status"),
        "text_sentiment_coverage": report.get("text_sentiment_coverage"),
        "news_event_rows": report.get("news_event_rows"),
        "news_symbol_coverage": report.get("news_symbol_coverage"),
        "market_sentiment_proxy": report.get("market_sentiment_proxy"),
        "risk_appetite_proxy": report.get("risk_appetite_proxy"),
        "price_only_ablation_metrics": report.get("price_only_ablation_metrics"),
        "implementation_scope": report.get("implementation_scope"),
        "paper_references": report.get("paper_references"),
        "algorithm_modified": report.get("algorithm_modified"),
        "architecture_modified": report.get("architecture_modified"),
        "data_pipeline_adapted": report.get("data_pipeline_adapted"),
        "model_output_rows": report.get("model_output_rows"),
        "display_overlap_rows": report.get("display_overlap_rows"),
        "probability_calibration": report.get("probability_calibration"),
        "label_version": report.get("label_version"),
        "factor_version": report.get("factor_version"),
        "horizon": "1d",
        "top_scores": rows,
        "candidate_pool": candidate_pool,
        "candidate_summary": {
            "source_horizon": "1d",
            "candidate_count": len(candidate_pool),
            "pool_definition": pool_definition,
            "next_checks": ["个股详情", "条件测试", "回测风险"],
        },
        "horizon_rankings": horizon_rankings,
        "api_note": "research ranking only; not investment advice or trading instruction",
    }


def _daily_with_screening_factors() -> pd.DataFrame:
    daily = _real_csi300_daily()
    if daily.empty:
        return daily
    frame = daily.sort_values(["symbol", "trade_date"]).copy()
    grouped = frame.groupby("symbol", group_keys=False)
    for window in SCREENING_WINDOWS:
        frame[f"ma{window}"] = grouped["close"].rolling(window).mean().reset_index(level=0, drop=True)
        frame[f"ma{window}_slope_up"] = frame[f"ma{window}"] > grouped[f"ma{window}"].shift(1)
    frame["return_10d"] = grouped["close"].pct_change(10)
    turnover = pd.to_numeric(frame.get("turnover_rate"), errors="coerce")
    frame["estimated_market_cap_billion"] = (frame["amount"] / (turnover / 100) / 100_000_000).replace([float("inf"), -float("inf")], pd.NA)
    stock_name_upper = frame["stock_name"].astype(str).str.upper()
    frame["non_st"] = (~frame["st_flag"].astype(bool)) & (~frame["delist_flag"].astype(bool)) & (~stock_name_upper.str.contains("ST", regex=False))
    frame["ma_bullish_order"] = (
        (frame["ma5"] > frame["ma10"])
        & (frame["ma10"] > frame["ma20"])
        & (frame["ma20"] > frame["ma30"])
        & (frame["ma30"] > frame["ma60"])
        & (frame["ma60"] > frame["ma250"])
    )
    frame["ma_all_up"] = True
    for window in SCREENING_WINDOWS:
        frame["ma_all_up"] = frame["ma_all_up"] & frame[f"ma{window}_slope_up"].fillna(False)
    frame["ma_bullish"] = frame["ma_bullish_order"] & frame["ma_all_up"]
    frame["return_10d_gt_15"] = frame["return_10d"] > 0.15
    frame["close_above_ma10"] = frame["close"] > frame["ma10"]
    frame["market_cap_gt_100b"] = frame["estimated_market_cap_billion"] > 100
    frame["all_conditions_met"] = (
        frame["non_st"]
        & frame["ma_bullish"]
        & frame["return_10d_gt_15"]
        & frame["close_above_ma10"]
        & frame["market_cap_gt_100b"]
    )
    wide = _model_feature_matrix_wide()
    available_feature_columns = [col for col in ["symbol", "trade_date", *MODEL_FEATURE_COLUMNS] if col in wide.columns]
    if len(available_feature_columns) > 2:
        feature_frame = wide[available_feature_columns].drop_duplicates(["symbol", "trade_date"], keep="last")
        frame = frame.merge(feature_frame, on=["symbol", "trade_date"], how="left")
    return frame


def _existing_columns(frame: pd.DataFrame, columns: list[str]) -> list[str]:
    return [column for column in columns if column in frame.columns]


def _condition_column_schema(frame: pd.DataFrame, columns: list[str]) -> dict[str, dict[str, Any]]:
    schema: dict[str, dict[str, Any]] = {}
    for column in columns:
        if column in SCREENING_BOOLEAN_COLUMNS:
            schema[column] = {
                "type": "boolean",
                "operators": CONDITION_DISCRETE_OPERATORS,
                "options": [{"label": "是", "value": True}, {"label": "否", "value": False}],
            }
        elif column in CONDITION_CATEGORY_COLUMNS:
            values = []
            if column in frame.columns:
                values = sorted(frame[column].dropna().astype(str).unique().tolist())
            schema[column] = {"type": "category", "operators": CONDITION_DISCRETE_OPERATORS, "options": values}
        elif column in CONDITION_TEXT_COLUMNS:
            schema[column] = {"type": "text", "operators": CONDITION_TEXT_OPERATORS}
        elif column in frame.columns and pd.api.types.is_numeric_dtype(frame[column]):
            values = pd.to_numeric(frame[column], errors="coerce").dropna()
            schema[column] = {
                "type": "number",
                "operators": CONDITION_NUMERIC_OPERATORS,
                "min": None if values.empty else float(values.min()),
                "max": None if values.empty else float(values.max()),
            }
        else:
            schema[column] = {"type": "text", "operators": CONDITION_TEXT_OPERATORS}
    return schema


def _data_refresh_policy() -> dict[str, Any]:
    return {
        "frequency": "daily_after_market_close",
        "description": "A股收盘且数据源完成日线落库后每日更新；先拉取沪深300日线，再重算因子、标签和最新研究信号。",
        "recommended_time_cn": "交易日 16:30 后",
        "command": "./.venv/Scripts/python.exe scripts/update_daily_market_data.py",
        "report_path": "reports/daily_update/daily_market_data_update_report.json",
        "steps": [
            "fetch_real_csi300_daily",
            "materialize_factor_store",
            "build_labels",
            "build_latest_live_scores",
        ],
    }


def _latest_symbol_universe(frame: pd.DataFrame) -> pd.DataFrame:
    latest = frame.sort_values(["symbol", "trade_date"]).drop_duplicates("symbol", keep="last").copy()
    latest = _with_display_industry(latest).sort_values("symbol")
    for column in SCREENING_BOOLEAN_COLUMNS:
        if column in latest.columns:
            latest[column] = latest[column].fillna(False).astype(bool)
    return latest


def _latest_complete_signal_universe(frame: pd.DataFrame) -> tuple[pd.DataFrame, str, str, int, int]:
    raw_latest_trade_date = str(frame["trade_date"].max())
    latest_by_symbol = _latest_symbol_universe(frame)
    expected_symbol_count = int(len(latest_by_symbol))
    date_counts = frame.groupby("trade_date")["symbol"].nunique().sort_index()
    complete_dates = date_counts[date_counts >= expected_symbol_count]
    latest_complete_trade_date = str(complete_dates.index[-1]) if not complete_dates.empty else raw_latest_trade_date
    raw_latest_count = int(date_counts.loc[raw_latest_trade_date]) if raw_latest_trade_date in date_counts.index else 0
    signal_universe = frame[frame["trade_date"].astype(str).eq(latest_complete_trade_date)].sort_values(["symbol", "trade_date"]).drop_duplicates("symbol", keep="last").copy()
    signal_universe = _with_display_industry(signal_universe).sort_values("symbol")
    for column in SCREENING_BOOLEAN_COLUMNS:
        if column in signal_universe.columns:
            signal_universe[column] = signal_universe[column].fillna(False).astype(bool)
    return signal_universe, latest_complete_trade_date, raw_latest_trade_date, raw_latest_count, expected_symbol_count


def _factor_daily_panel_wide(trade_date: str) -> tuple[pd.DataFrame, list[str], dict[str, str]]:
    factor_path = project_root() / "data" / "gold" / "factor_daily_panel_long"
    if not factor_path.exists():
        return pd.DataFrame(), [], {}
    try:
        frame = pd.read_parquet(
            factor_path,
            columns=["trade_date", "symbol", "factor_name", "factor_value", "category"],
            filters=[("trade_date", "=", trade_date)],
        )
    except Exception:
        frame = _read_parquet(factor_path)
        if not frame.empty:
            frame = frame[frame["trade_date"].astype(str).eq(trade_date)].copy()
    if frame.empty:
        return pd.DataFrame(), [], {}
    frame = frame.dropna(subset=["symbol", "factor_name"]).copy()
    frame["symbol"] = frame["symbol"].astype(str).str.upper()
    frame["trade_date"] = frame["trade_date"].astype(str)
    frame["factor_name"] = frame["factor_name"].astype(str)
    factor_columns = sorted(frame["factor_name"].unique().tolist())
    catalog = {
        str(row["factor_name"]): f"{row['category']} · {row['factor_name']}" if row.get("category") else str(row["factor_name"])
        for _, row in frame.sort_values(["factor_name", "category"]).drop_duplicates("factor_name").iterrows()
    }
    wide = (
        frame.sort_values(["symbol", "trade_date", "factor_name"])
        .drop_duplicates(["symbol", "trade_date", "factor_name"], keep="last")
        .pivot(index=["symbol", "trade_date"], columns="factor_name", values="factor_value")
        .reset_index()
    )
    wide.columns = [str(column) for column in wide.columns]
    return wide, factor_columns, catalog


def condition_screen_payload(research_boundary: str) -> dict[str, Any]:
    frame = _daily_with_screening_factors()
    if frame.empty:
        return {
            "module": "condition-screen",
            "status": "condition_screen_pending",
            "mode": "latest_stock_universe_condition_table",
            "research_boundary": research_boundary,
            "criteria": CONDITION_SCREEN_CRITERIA,
            "base_columns": CONDITION_BASE_COLUMNS,
            "available_factor_columns": CONDITION_FACTOR_COLUMNS,
            "factor_column_catalog": CONDITION_FACTOR_COLUMN_CATALOG,
            "column_schema": _condition_column_schema(pd.DataFrame(), [*CONDITION_BASE_COLUMNS, *CONDITION_FACTOR_COLUMNS]),
            "rows": [],
            "row_count": 0,
            "summary": {"sample_count": 0, "matched_count": 0, "displayed_trade_dates": [], "data_dates": []},
        }

    frame["amount_billion"] = frame["amount"] / 100_000_000
    latest_universe, latest_trade_date, raw_latest_trade_date, raw_latest_count, expected_symbol_count = _latest_complete_signal_universe(frame)
    factor_wide, factor_columns, factor_catalog = _factor_daily_panel_wide(latest_trade_date)
    if not factor_wide.empty and factor_columns:
        latest_universe = latest_universe.drop(columns=[column for column in factor_columns if column in latest_universe.columns], errors="ignore")
        latest_universe = latest_universe.merge(factor_wide, on=["symbol", "trade_date"], how="left")
    displayed_trade_dates = sorted(latest_universe["trade_date"].astype(str).unique().tolist())
    available_factor_columns = _existing_columns(latest_universe, factor_columns or CONDITION_FACTOR_COLUMNS)
    factor_column_catalog = {column: CONDITION_FACTOR_COLUMN_CATALOG.get(column, factor_catalog.get(column, column)) for column in available_factor_columns}
    output_columns = _existing_columns(latest_universe, [*CONDITION_BASE_COLUMNS, *available_factor_columns])
    column_schema = _condition_column_schema(latest_universe, output_columns)
    matched_count = int(latest_universe["all_conditions_met"].sum()) if "all_conditions_met" in latest_universe.columns else 0

    return {
        "module": "condition-screen",
        "status": "condition_screen_ready",
        "maturity": "L2-latest-complete-universe-condition-factor-table",
        "mode": "latest_stock_universe_condition_table",
        "research_boundary": research_boundary,
        "latest_trade_date": latest_trade_date,
        "raw_latest_trade_date": raw_latest_trade_date,
        "raw_latest_stock_count": raw_latest_count,
        "expected_symbol_count": expected_symbol_count,
        "criteria": CONDITION_SCREEN_CRITERIA,
        "base_columns": CONDITION_BASE_COLUMNS,
        "available_factor_columns": available_factor_columns,
        "factor_column_catalog": factor_column_catalog,
        "column_schema": column_schema,
        "st_star_rules": ST_STAR_RULES,
        "rows": _json_records(latest_universe[output_columns]),
        "row_count": int(len(latest_universe)),
        "summary": {
            "sample_count": int(len(latest_universe)),
            "matched_count": matched_count,
            "latest_signal_date": latest_trade_date,
            "raw_latest_trade_date": raw_latest_trade_date,
            "raw_latest_stock_count": raw_latest_count,
            "expected_symbol_count": expected_symbol_count,
            "displayed_trade_dates": displayed_trade_dates,
            "data_dates": displayed_trade_dates,
            "date_range": [displayed_trade_dates[0], displayed_trade_dates[-1]] if displayed_trade_dates else [latest_trade_date, latest_trade_date],
            "universe_rows": int(len(frame)),
            "latest_universe_rows": int(len(latest_universe)),
        },
        "api_note": "展示最新完整沪深300股票截面的最近可用行情/因子；如果当日公共数据源只返回部分股票，则自动回退到最近一个完整截面。条件不满足或必要特征缺失均显示为否。页面仅保留研究因子列供人工判断，不构成投资建议。",
    }


def market_overview_payload(research_boundary: str) -> dict[str, Any]:
    daily = _real_csi300_daily()
    if daily.empty:
        return {
            "module": "market",
            "status": "market_universe_pending",
            "research_boundary": research_boundary,
            "breadth_summary": {"up_count": 0, "down_count": 0, "flat_count": 0, "unknown_count": 0},
            "data_refresh_policy": _data_refresh_policy(),
            "stocks": [],
        }

    frame = daily.sort_values(["symbol", "trade_date"]).copy()
    frame["previous_close"] = frame.groupby("symbol")["close"].shift(1)
    latest = frame.loc[frame.groupby("symbol")["trade_date"].idxmax()].copy()
    latest = _with_display_industry(latest)
    valid_previous_close = pd.to_numeric(latest["previous_close"], errors="coerce").gt(0)
    latest["pct_change"] = (latest["close"] - latest["previous_close"]) / latest["previous_close"]
    latest.loc[~valid_previous_close, "pct_change"] = pd.NA
    latest["turnover_rate"] = pd.to_numeric(latest.get("turnover_rate"), errors="coerce")
    latest["amount_billion"] = latest["amount"] / 100_000_000
    latest = latest.sort_values("symbol")

    pct = pd.to_numeric(latest["pct_change"], errors="coerce")
    up_count = int(pct.gt(0).sum())
    down_count = int(pct.lt(0).sum())
    unknown_count = int(pct.isna().sum())
    flat_count = int(len(latest) - up_count - down_count - unknown_count)

    stocks = _json_records(latest[_existing_columns(latest, MARKET_COLUMNS)])
    return {
        "module": "market",
        "status": "market_universe_ready",
        "maturity": "L2-real-csi300-market-board",
        "research_boundary": research_boundary,
        "stock_count": int(latest["symbol"].nunique()),
        "latest_trade_date": str(latest["trade_date"].max()),
        "data_source": "data/real/csi300_daily/part-000.parquet",
        "breadth_summary": {
            "up_count": up_count,
            "down_count": down_count,
            "flat_count": flat_count,
            "unknown_count": unknown_count,
            "priced_count": up_count + down_count + flat_count,
        },
        "data_refresh_policy": _data_refresh_policy(),
        "stocks": stocks,
        "api_note": "CSI300 research universe display only; not investment advice or trading instruction",
    }


def _stock_factor_values(symbol: str, trade_date: str, factor_names: list[str] | None = None) -> dict[str, dict[str, Any]]:
    factor_path = project_root() / "data" / "gold" / "factor_daily_panel_long"
    if not factor_path.exists():
        return {}
    filters: list[tuple[str, str, Any]] = [("symbol", "=", symbol), ("trade_date", "=", trade_date)]
    if factor_names:
        filters.append(("factor_name", "in", factor_names))
    try:
        frame = pd.read_parquet(
            factor_path,
            columns=["trade_date", "symbol", "factor_name", "factor_value", "category"],
            filters=filters,
        )
    except Exception:
        frame = _read_parquet(factor_path)
        if frame.empty:
            return {}
        mask = (frame["symbol"].astype(str).str.upper() == symbol) & (frame["trade_date"].astype(str) == trade_date)
        if factor_names:
            mask = mask & frame["factor_name"].astype(str).isin(factor_names)
        frame = frame[mask].copy()
    if frame.empty:
        return {}
    frame = frame.sort_values(["category", "factor_name", "trade_date"]).drop_duplicates("factor_name", keep="last")
    return {str(row["factor_name"]): row.to_dict() for _, row in frame.iterrows()}


def _factor_value_interpretation(factor_name: str | None, factor_value: Any) -> str:
    value = _safe_float(factor_value)
    name = (factor_name or "").lower()
    if value is None:
        return "该股暂无取值。"
    if any(token in name for token in ["return", "momentum", "reversal", "gap", "range", "deviation", "volatility"]):
        if value > 0:
            return f"该股该因子为正，约 {value:.2%}。"
        if value < 0:
            return f"该股该因子为负，约 {value:.2%}。"
        return "该股该因子接近零。"
    if "beta" in name:
        return f"该股 Beta 约 {value:.2f}。"
    if "rank" in name or "percentile" in name:
        return f"该股截面位置约 {value:.2f}。"
    if "zscore" in name or "z_score" in name:
        return f"该股标准分约 {value:.2f}。"
    return f"该股取值 {value:.4f}。"


def stock_detail_payload(symbol: str, research_boundary: str) -> dict[str, Any]:
    normalized_symbol = symbol.upper().replace("-", ".")
    daily = _real_csi300_daily()
    stock_frame = daily[daily["symbol"].astype(str).str.upper() == normalized_symbol].sort_values("trade_date").copy()
    if stock_frame.empty:
        return {
            "module": "stock_detail",
            "status": "stock_detail_not_found",
            "symbol": normalized_symbol,
            "research_boundary": research_boundary,
        }
    stock_frame = _with_display_industry(stock_frame)

    stock_frame["previous_close"] = stock_frame["close"].shift(1)
    stock_frame["pct_change"] = ((stock_frame["close"] - stock_frame["previous_close"]) / stock_frame["previous_close"]).fillna(0.0)
    stock_frame["ma5"] = stock_frame["close"].rolling(5).mean()
    stock_frame["ma20"] = stock_frame["close"].rolling(20).mean()
    stock_frame["turnover_rate"] = pd.to_numeric(stock_frame.get("turnover_rate"), errors="coerce")
    latest_row = stock_frame.iloc[-1]

    price_series = _json_records(stock_frame.tail(160)[_existing_columns(stock_frame, PRICE_SERIES_COLUMNS)])

    live_predictions = _read_parquet(project_root() / "reports" / "research_loop" / "live_predictions.parquet")
    predictions = live_predictions if not live_predictions.empty else _read_parquet(project_root() / "reports" / "research_loop" / "predictions.parquet")
    prediction_rows: list[dict[str, Any]] = []
    if not predictions.empty:
        pred_symbol = predictions[predictions["symbol"].astype(str).str.upper() == normalized_symbol].copy()
        for horizon in ["1d", "5d", "14d"]:
            pred_horizon = pred_symbol[pred_symbol["horizon"].astype(str) == horizon]
            if not pred_horizon.empty:
                latest_pred_date = str(pred_horizon["trade_date"].max())
                row = pred_horizon[pred_horizon["trade_date"].astype(str) == latest_pred_date].sort_values("rank").head(1)
                prediction_rows.extend(_json_records(row[_existing_columns(row, PREDICTION_COLUMNS)]))

    factor_report = _read_json(project_root() / "reports" / "factor_store" / "factor_store_factor_report.json")
    report_by_name = {str(item.get("factor_name")): item for item in factor_report.get("single_factor_reports", []) if item.get("factor_name")}
    latest_trade_date = str(latest_row.get("trade_date"))
    stock_factor_values = _stock_factor_values(normalized_symbol, latest_trade_date)
    recent_factors = []
    for factor_name, stock_factor in stock_factor_values.items():
        item = report_by_name.get(str(factor_name), {})
        factor_value = _safe_float(stock_factor.get("factor_value"))
        recent_factors.append({
            "factor_name": factor_name,
            "category": stock_factor.get("category") or item.get("category"),
            "coverage": item.get("coverage_by_year", {}).get("all"),
            "IC_mean": item.get("IC_mean"),
            "RankIC_mean": item.get("RankIC_mean"),
            "top_bottom_spread": item.get("top_bottom_spread"),
            "cost_adjusted_spread": item.get("cost_adjusted_spread"),
            "factor_value": factor_value,
            "value_trade_date": stock_factor.get("trade_date") or latest_trade_date,
            "value_interpretation": _factor_value_interpretation(str(factor_name), factor_value),
        })

    return {
        "module": "stock_detail",
        "status": "stock_detail_ready",
        "maturity": "L2-real-csi300-stock-detail",
        "research_boundary": research_boundary,
        "symbol": normalized_symbol,
        "stock_name": latest_row.get("stock_name"),
        "industry_name": latest_row.get("industry_name"),
        "latest_trade_date": str(latest_row.get("trade_date")),
        "latest_quote": _json_records(pd.DataFrame([latest_row]))[0],
        "price_series": price_series,
        "predictions": prediction_rows,
        "recent_factors": recent_factors,
        "factor_count": len(recent_factors),
        "market_notes": MARKET_NOTES,
    }


def _risk_level(value: float | None, warning: float, danger: float, more_negative_is_worse: bool = False) -> str:
    if value is None:
        return "unknown"
    if more_negative_is_worse:
        if value <= danger:
            return "danger"
        if value <= warning:
            return "warning"
        return "ok"
    if value >= danger:
        return "danger"
    if value >= warning:
        return "warning"
    return "ok"


def backtests_payload(research_boundary: str) -> dict[str, Any]:
    root = project_root()
    report = research_loop_report()
    curve = _read_parquet(root / "data" / "gold" / "portfolio_backtest_result" / "part-000.parquet")
    risk = _read_parquet(root / "reports" / "research_loop" / "risk_report.parquet")
    if report.get("status") != "ok" or curve.empty:
        return {
            "module": "backtests",
            "status": "research_loop_backtest_pending",
            "maturity": "L1-route-stub",
            "research_boundary": research_boundary,
        }
    metrics = report.get("metrics", {})
    metric_payload = {k: v for k, v in metrics.items() if k != "baseline_metrics"}
    latest_curve = curve.sort_values("trade_date").iloc[-1]
    latest_risk = risk.sort_values("trade_date").iloc[-1] if not risk.empty else None
    max_drawdown = _safe_float(metric_payload.get("MaxDrawdown"))
    turnover = _safe_float(metric_payload.get("Turnover"))
    sharpe = _safe_float(metric_payload.get("Sharpe"))
    calmar = _safe_float(metric_payload.get("Calmar"))
    hit_rate = _safe_float(metric_payload.get("HitRate"))
    cost_adjusted_return = _safe_float(metric_payload.get("Cost_adjusted_return"))
    risk_summary = {
        "latest_trade_date": str(latest_curve.get("trade_date")),
        "nav_latest": _safe_float(latest_curve.get("nav")),
        "cumulative_return": None if _safe_float(latest_curve.get("nav")) is None else _safe_float(latest_curve.get("nav")) - 1,
        "latest_daily_return": _safe_float(latest_curve.get("daily_return")),
        "latest_turnover": _safe_float(latest_curve.get("turnover")),
        "latest_transaction_cost": _safe_float(latest_curve.get("transaction_cost")),
        "max_drawdown": max_drawdown,
        "sharpe": sharpe,
        "calmar": calmar,
        "hit_rate": hit_rate,
        "turnover": turnover,
        "cost_adjusted_return": cost_adjusted_return,
        "capacity": _safe_float(metric_payload.get("Capacity")),
        "risk_flags": [
            {"name": "最大回撤", "level": _risk_level(max_drawdown, -0.20, -0.35, more_negative_is_worse=True), "explain": "越接近 -100% 越危险，用来衡量历史最深亏损。"},
            {"name": "换手率", "level": _risk_level(turnover, 0.50, 0.80), "explain": "越高越依赖频繁调仓，交易成本和滑点越敏感。"},
            {"name": "夏普比率", "level": "warning" if sharpe is not None and sharpe < 1 else "ok", "explain": "单位波动带来的收益，低于 1 说明收益/波动不够稳。"},
            {"name": "胜率", "level": "warning" if hit_rate is not None and hit_rate < 0.5 else "ok", "explain": "并不单独决定好坏，但能提示策略是否经常处于亏损日。"},
        ],
    }
    risk_latest = {}
    capacity_curve = []
    industry_attribution = {}
    style_attribution = {}
    if latest_risk is not None:
        risk_latest = {
            "active_return": _safe_float(latest_risk.get("active_return")),
            "tracking_error": _safe_float(latest_risk.get("tracking_error")),
            "information_ratio": _safe_float(latest_risk.get("information_ratio")),
            "beta_to_benchmark": _safe_float(latest_risk.get("beta_to_benchmark")),
            "active_max_drawdown": _safe_float(latest_risk.get("active_max_drawdown")),
            "implementation_shortfall": _safe_float(latest_risk.get("implementation_shortfall")),
            "risk_model_version": latest_risk.get("risk_model_version"),
        }
        capacity_curve = _safe_json_value(latest_risk.get("capacity_curve"), [])
        industry_attribution = _safe_json_value(latest_risk.get("industry_attribution"), {})
        style_attribution = _safe_json_value(latest_risk.get("style_attribution"), {})
    return {
        "module": "backtests",
        "status": "research_loop_backtest_ready",
        "maturity": "L2-tradable-topk-cost-risk-capacity-backtest",
        "research_boundary": research_boundary,
        "run_id": report.get("run_id"),
        "experiment_id": report.get("experiment_id"),
        "portfolio_id": "top5_equal_weight",
        "benchmark": "CSI300_DEMO",
        "equity_curve_rows": int(len(curve)),
        "risk_report_rows": int(len(risk)),
        "metrics": metric_payload,
        "baseline_metrics": metrics.get("baseline_metrics", {}),
        "risk_summary": risk_summary,
        "risk_latest": risk_latest,
        "capacity_curve": capacity_curve,
        "industry_attribution": industry_attribution,
        "style_attribution": style_attribution,
        "curve_tail": curve.tail(30).to_dict(orient="records"),
        "risk_tail": risk.tail(10).to_dict(orient="records") if not risk.empty else [],
        "risk_explainers": [
            {"title": "先看回撤，不只看收益", "body": "最大回撤代表历史上从高点跌到低点的最深亏损，是判断能不能扛住策略波动的核心指标。"},
            {"title": "换手和成本决定能不能落地", "body": "候选池换得越频繁，手续费、冲击成本和滑点越容易吞掉模型优势。"},
            {"title": "容量曲线看资金规模上限", "body": "capacity_curve 按参与率估算策略可承载资金，超过容量后成交冲击会快速上升。"},
            {"title": "风险归因看亏损来源", "body": "行业、风格、选股和交易成本归因用于判断亏损来自模型、市场暴露还是执行成本。"},
        ],
        "artifacts": report.get("artifacts", {}),
    }


def experiments_payload(research_boundary: str) -> dict[str, Any]:
    root = project_root()
    report = research_loop_report()
    manifest = _read_json(root / "reports" / "research_loop" / "experiment_recorder" / str(report.get("run_id", "")) / "artifact_manifest.json")
    config = _read_yaml(root / "reports" / "research_loop" / "experiment_recorder" / str(report.get("run_id", "")) / "resolved_config.yaml")
    advanced = _read_json(root / "reports" / "advanced_models" / "advanced_model_integration_report.json")
    if report.get("status") != "ok":
        return {
            "module": "experiments",
            "status": "research_loop_experiment_pending",
            "maturity": "L1-route-stub",
            "research_boundary": research_boundary,
            "advanced_models": {
                "status": "advanced_models_advanced_models_ready" if advanced.get("status") == "ok" else "advanced_models_advanced_models_pending",
                "maturity": advanced.get("maturity"),
                "run_id": advanced.get("run_id"),
                "experiment_id": advanced.get("experiment_id"),
                "model_count": len(advanced.get("models", {})),
                "approval_status": advanced.get("approval_status"),
                "leakage_check_status": advanced.get("leakage_check_status"),
                "artifacts": advanced.get("artifacts", {}),
            },
        }
    return {
        "module": "experiments",
        "status": "research_loop_experiment_recorder_ready",
        "maturity": "L2-file-based-mlflow-qlib-compatible-recorder",
        "research_boundary": research_boundary,
        "run_id": report.get("run_id"),
        "experiment_id": report.get("experiment_id"),
        "config_hash": report.get("config_hash"),
        "data_version": report.get("data_version"),
        "factor_version": report.get("factor_version"),
        "label_version": report.get("label_version"),
        "model_version": report.get("model_version"),
        "feature_count": report.get("feature_count"),
        "split_count": report.get("split_count"),
        "lightgbm_status": report.get("lightgbm_status"),
        "qlib_status": report.get("qlib_status"),
        "resolved_config": config,
        "artifact_manifest": manifest,
        "advanced_models": {
            "status": "advanced_models_advanced_models_ready" if advanced.get("status") == "ok" else "advanced_models_advanced_models_pending",
            "maturity": advanced.get("maturity"),
            "run_id": advanced.get("run_id"),
            "experiment_id": advanced.get("experiment_id"),
            "model_count": len(advanced.get("models", {})),
            "approval_status": advanced.get("approval_status"),
            "leakage_check_status": advanced.get("leakage_check_status"),
            "artifacts": advanced.get("artifacts", {}),
        },
    }


def dashboard_research_loop_payload(research_boundary: str) -> dict[str, Any]:
    report = research_loop_report()
    if report.get("status") != "ok":
        return {
            "module": "overview",
            "status": "factor_store_ready_research_loop_pending",
            "research_boundary": research_boundary,
        }
    metrics = report.get("metrics", {})
    return {
        "module": "overview",
        "status": "research_loop_research_loop_ready",
        "maturity": "L2-offline-research-loop-dashboard-summary",
        "research_boundary": research_boundary,
        "run_id": report.get("run_id"),
        "model_version": report.get("model_version"),
        "label_version": report.get("label_version"),
        "leakage_check_status": report.get("leakage_check_status"),
        "prediction_rows": report.get("prediction_rows"),
        "equity_curve_rows": report.get("equity_curve_rows"),
        "risk_report_rows": report.get("risk_report_rows"),
        "core_metrics": {
            "IC": metrics.get("IC"),
            "RankIC": metrics.get("RankIC"),
            "TopK_return": metrics.get("TopK_return"),
            "Turnover": metrics.get("Turnover"),
            "Cost_adjusted_return": metrics.get("Cost_adjusted_return"),
            "Capacity": metrics.get("Capacity"),
        },
    }
