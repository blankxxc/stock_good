import json
import os

import polars as pl
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import ValidationError

from backend.app.services import visualization as visual
from backend.app.routers import visualization as route


@pytest.fixture
def daily_files(tmp_path, monkeypatch):
    market = tmp_path / "market.parquet"
    factors = tmp_path / "factors.parquet"
    spec = tmp_path / "factors.yaml"
    pl.DataFrame({
        "symbol": ["000001.SZ"] * 3 + ["600000.SH"] * 2,
        "stock_name": ["股票甲"] * 3 + ["股票乙"] * 2,
        "trade_date": ["2026-10-12", "2026-10-13", "2026-10-14", "2026-10-12", "2026-10-14"],
        "close": [100., 110., 120., 200., 210.], "raw_close": [10., 11., 12., 20., 21.],
        "volume": [20., 30., 40., 50., 60.], "adjustment_mode": ["hfq"] * 5,
    }).write_parquet(market)
    pl.DataFrame({"symbol": ["000001.SZ"] * 3 + ["600000.SH"],
                  "trade_date": ["2026-10-12", "2026-10-13", "2026-10-14", "2026-10-14"],
                  "return_20d": [None, .1, float("nan"), float("inf")]}).write_parquet(factors)
    spec.write_text("factors:\n  return_20d:\n    formula: close / shift(close, 20) - 1\n  unavailable:\n    formula: missing\n", encoding="utf-8")
    monkeypatch.setattr(visual, "MARKET", market)
    monkeypatch.setattr(visual, "FACTORS", factors)
    monkeypatch.setattr(visual, "SPEC", spec)
    return market, factors, spec


def request(**overrides):
    values = dict(symbols=["000001.SZ", "600000.SH"], metrics=["raw_close", "return_20d"],
                  start_date="2026-10-12", end_date="2026-10-14")
    return visual.SeriesRequest(**(values | overrides))


def test_series_aligns_dates_and_preserves_missing_and_raw_prices(daily_files):
    result = visual.query_series(request(metrics=["raw_close", "close", "return_20d"]))
    series = {(s["symbol"], s["metric"]): s["values"] for s in result["series"]}
    assert result["dates"] == ["2026-10-12", "2026-10-13", "2026-10-14"]
    assert series["000001.SZ", "raw_close"] == [10., 11., 12.]
    assert series["000001.SZ", "close"] == [100., 110., 120.]
    assert series["600000.SH", "raw_close"] == [20., None, 21.]
    assert series["000001.SZ", "return_20d"] == [None, .1, None]
    assert series["600000.SH", "return_20d"] == [None, None, None]
    json.dumps(result, allow_nan=False)
    subset = visual.query_series(request(symbols=["600000.SH"], metrics=["close"], start_date="2026-10-14"))
    assert subset["dates"] == ["2026-10-14"]
    assert len(subset["series"]) == 1
    assert subset["series"][0]["values"] == [210.]


def test_metadata_exposes_only_available_columns_and_price_basis(daily_files):
    meta = visual.visualization_metadata()
    assert len(meta["stocks"]) == 2
    assert {m["id"] for m in meta["metrics"]} == {"close", "raw_close", "volume", "return_20d"}
    assert meta["price_basis"] == "后复权研究价格"
    assert meta["market_end"] == meta["factor_end"] == "2026-10-14"


def test_metadata_rejects_source_update_during_read(daily_files, monkeypatch):
    real_read_text = type(daily_files[2]).read_text
    updated = False

    def update_after_market_read(path, *args, **kwargs):
        nonlocal updated
        content = real_read_text(path, *args, **kwargs)
        if path == daily_files[2] and not updated:
            updated = True
            market = daily_files[0]
            stat = market.stat()
            frame = pl.read_parquet(market).with_columns(pl.lit("新名称").alias("stock_name"))
            frame.write_parquet(market)
            os.utime(market, ns=(stat.st_atime_ns, stat.st_mtime_ns + 1_000_000_000))
        return content

    monkeypatch.setattr(type(daily_files[2]), "read_text", update_after_market_read)
    with pytest.raises(ValueError, match="更新"):
        visual.visualization_metadata()
    assert {row["stock_name"] for row in visual.visualization_metadata()["stocks"]} == {"新名称"}


@pytest.mark.parametrize("typed_timestamps", [False, True])
def test_series_excludes_factors_unavailable_at_prediction_time(daily_files, typed_timestamps):
    path = daily_files[1]
    frame = pl.read_parquet(path).with_columns(
        pl.Series("return_20d", [.1, .2, .3, .4]),
        pl.Series("available_time", ["2026-10-12T15:30:00+08:00", "2026-10-13T16:30:00+08:00", None, "2026-10-14T07:30:00+00:00"]),
        pl.Series("prediction_time", ["2026-10-12T16:00:00+08:00", "2026-10-13T16:00:00+08:00", "2026-10-14T16:00:00+08:00", "2026-10-14T16:00:00+08:00"]),
    )
    if typed_timestamps:
        frame = frame.with_columns(pl.col("available_time").str.to_datetime(time_zone="UTC"), pl.col("prediction_time").str.to_datetime(time_zone="UTC"))
    frame.write_parquet(path)
    values = {(s["symbol"], s["metric"]): s["values"] for s in visual.query_series(request())["series"]}
    assert values["000001.SZ", "return_20d"] == [.1, None, None]
    assert values["600000.SH", "return_20d"] == [None, None, .4]
    assert values["000001.SZ", "raw_close"] == [10., 11., 12.]


def test_cache_is_isolated_and_invalidates_on_source_update(daily_files):
    req = request()
    result = visual.query_series(req)
    before = result["data_version"]
    result["series"][0]["values"][0] = -999
    assert visual.query_series(req)["series"][0]["values"][0] != -999
    path = daily_files[0]
    stat = path.stat()
    frame = pl.read_parquet(path).with_columns((pl.col("raw_close") + 1).alias("raw_close"))
    frame.write_parquet(path)
    os.utime(path, ns=(stat.st_atime_ns, stat.st_mtime_ns + 1_000_000_000))
    updated = visual.query_series(req)
    assert updated["data_version"] != before
    assert next(s for s in updated["series"] if s["symbol"] == "000001.SZ" and s["metric"] == "raw_close")["values"][0] == 11.


@pytest.mark.parametrize("overrides", [
    {"start_date": "2026-10-15"}, {"start_date": "2000-01-01"},
    {"symbols": []}, {"symbols": [str(i) for i in range(5)]},
    {"metrics": [str(i) for i in range(13)]}, {"start_date": "2026-02-30"},
])
def test_rejects_invalid_or_unbounded_request(overrides):
    with pytest.raises(ValidationError):
        request(**overrides)


def test_api_rejects_unknown_symbols_and_metrics_and_handles_empty_interval(daily_files):
    app = FastAPI()
    app.include_router(route.router)
    with TestClient(app) as client:
        assert client.get("/api/visualization").status_code == 200
        for changed in [{"symbols": ["../secret"]}, {"metrics": ["unavailable"]}]:
            response = client.post("/api/visualization/series", json=request(**changed).model_dump(mode="json"))
            assert response.status_code == 422
        response = client.post("/api/visualization/series", json=request(start_date="2026-10-17", end_date="2026-10-18").model_dump(mode="json"))
        assert response.status_code == 200
        assert response.json()["dates"] == []
        assert response.headers["Cache-Control"] == "no-store"


def test_duplicate_observations_are_rejected(daily_files):
    path = daily_files[1]
    frame = pl.read_parquet(path)
    pl.concat([frame, frame.head(1)]).write_parquet(path)
    with pytest.raises(ValueError, match="重复"):
        visual.query_series(request())


def test_missing_factors_still_allows_price_charts(daily_files):
    daily_files[1].unlink()
    meta = visual.visualization_metadata()
    assert meta["factor_end"] is None
    assert all(m["group"] == "行情" for m in meta["metrics"])
    assert visual.query_series(request(metrics=["raw_close"]))["series"][0]["values"] == [10., 11., 12.]


def test_assistant_rereads_bounded_series_not_browser_numbers(daily_files, monkeypatch):
    from backend.app.services import ai_assistant as ai
    monkeypatch.setattr(ai, "factor_payload", lambda _: {"factor_catalog": []})
    def forbidden(*args):
        raise AssertionError("Visualization must not load the unrelated market overview")
    monkeypatch.setattr(ai.research, "market_overview_payload", forbidden)
    state = {**request().model_dump(mode="json"), "loaded": True, "invented_value": 999999}
    body = ai.ChatRequest(provider="deepseek", model="test", page="/visualization", page_state={"visualization": state},
                          messages=[{"role": "user", "content": "分析看板"}])
    context = ai.build_context(body)
    item = context["visualization"]["series_summary_up_to_12"][0]
    assert item["first"] == {"date": "2026-10-12", "value": 10.}
    assert item["maximum"] == 12.
    assert "invented_value" not in context["visualization"]
    body.page_state["visualization"]["loaded"] = False
    assert "visualization" not in ai.build_context(body)
