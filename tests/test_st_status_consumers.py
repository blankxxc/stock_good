from __future__ import annotations

import pandas as pd

from tests.test_strategy_lab import market_frame


def test_screening_preserves_unknown_st_in_json(monkeypatch):
    from backend.app.services import research_loop_catalog as catalog

    frame = market_frame()
    frame["trade_date"] = frame.trade_date.dt.strftime("%Y-%m-%d")
    frame["st_flag"] = frame.st_flag.astype("boolean")
    frame.loc[frame.symbol == "000001.SZ", "st_flag"] = pd.NA
    frame.loc[frame.symbol == "600001.SH", "st_flag"] = True
    frame = frame.assign(amount=10000, turnover_rate=1, delist_flag=False)
    monkeypatch.setattr(catalog, "_real_csi300_daily", lambda: frame)
    monkeypatch.setattr(catalog, "compute_abnormal_movement_factors", lambda df: pd.DataFrame(0, index=df.index, columns=catalog.FLAG_NAMES))
    monkeypatch.setattr(catalog, "_factor_daily_panel_wide", lambda date: (pd.DataFrame(), [], {}))
    payload = catalog.condition_screen_payload("unknown-st-fixture")
    rows = {row["symbol"]: row for row in payload["rows"]}
    assert rows["000001.SZ"]["non_st"] is None
    assert rows["000001.SZ"]["all_conditions_met"] is False
    assert rows["600001.SH"]["non_st"] is False
    assert rows["600002.SH"]["non_st"] is True


def test_label_builder_preserves_unknown_st_without_writing(monkeypatch):
    from models import research_loop_research_loop as labels_service

    frame = market_frame().assign(industry_name="fixture", paused=False, delist_flag=False,
                                 limit_up_flag=False, limit_down_flag=False, execution_window="t_plus_1_open")
    frame["prediction_time"] = frame.trade_date.dt.strftime("%Y-%m-%dT16:00:00+08:00")
    frame["st_flag"] = frame.st_flag.astype("boolean")
    frame.loc[frame.symbol == "000001.SZ", "st_flag"] = pd.NA
    frame.loc[frame.symbol == "600001.SH", "st_flag"] = True
    monkeypatch.setattr(labels_service, "_read_clean_market", lambda: frame.copy())
    labels, report = labels_service.build_labels(write_outputs=False)
    assert not labels.empty
    assert labels.loc[labels.symbol == "000001.SZ", "st_flag"].isna().all()
    assert labels.loc[labels.symbol == "600001.SH", "st_flag"].eq(True).all()
    assert labels.loc[labels.symbol == "600002.SH", "st_flag"].eq(False).all()
    assert report["st_unknown_rows"] == int(labels.symbol.eq("000001.SZ").sum())
    assert report["st_unknown_rows"] + report["st_known_rows"] == len(labels)
