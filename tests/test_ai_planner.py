import asyncio
import json
from threading import BoundedSemaphore

import httpx
import pandas as pd
import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from pydantic import ValidationError
from starlette.requests import Request

from backend.app.routers import assistant as route
from backend.app.services import ai_assistant as ai, ai_planner as planner
from backend.app.services.strategy_lab import ExperimentRequest, run_experiment


CATALOG = {
    "stocks": [{"symbol": "000001.SZ", "stock_name": "平安银行"}, {"symbol": "600036.SH", "stock_name": "招商银行"}],
    "metrics": [{"id": "close", "label": "后复权收盘价"}, {"id": "volume", "label": "成交量"}],
    "market_start": "2026-01-01", "market_end": "2026-10-19", "default_start": "2026-07-01",
    "_calendar": pd.bdate_range("2026-01-01", "2026-10-19").strftime("%Y-%m-%d").tolist(),
}
BOARD = {"version": 1, "title": "银行对比", "symbols": ["000001.SZ", "600036.SH"],
         "start_date": "2026-07-01", "end_date": "2026-10-19", "cards": [
             {"id": "price", "title": "价格", "type": "line", "metric": "close", "xMetric": "close", "wide": True, "normalize": False},
             {"id": "volume", "title": "成交量", "type": "bar", "metric": "volume", "xMetric": "close", "wide": False, "normalize": False},
         ]}
STRATEGY = {"start_date": "2026-07-01", "end_date": "2026-10-19", "strategies": ["momentum", "low_volatility"],
            "lookback": 20, "top_k": 5, "rebalance_days": 5, "initial_capital": 100000,
            "fee_bps": 3, "slippage_bps": 5, "exclude_st": True, "exclude_extreme": False, "exclude_abnormal": False}


def request(task="visualization", **kwargs):
    return planner.PlanRequest(provider="deepseek", model="deepseek-flash", task=task, prompt="近三个月的研究方案", **kwargs)


def envelope(config=None, **kwargs):
    return {"summary": "按需求生成的配置草案", "notes": ["区间截至本地最新行情。"], "unsupported": [],
            "config": BOARD if config is None else config, **kwargs}


def validate(config, task="visualization", catalog=CATALOG):
    return planner.validate_plan(json.dumps(envelope(config)), request(task), catalog)


def test_valid_board_and_strategy_are_only_configuration():
    for task, config in [("visualization", BOARD), ("strategy", STRATEGY)]:
        result = validate(config, task)
        assert result["status"] == "ready"
        assert result["config"] == config
        assert "results" not in result


def test_resized_board_survives_ai_plan_validation():
    board = {**BOARD, "cards": [{**BOARD["cards"][0], "columns": 8, "height": 720}]}
    assert validate(board)["config"] == board


@pytest.mark.parametrize("size", [{"columns": 3}, {"columns": 13}, {"columns": 6.5},
                                  {"columns": "6"}, {"height": 399}, {"height": 1201}, {"height": True}])
def test_invalid_chart_sizes_are_rejected(size):
    with pytest.raises(planner.PlanError):
        validate({**BOARD, "cards": [{**BOARD["cards"][0], **size}]})


@pytest.mark.parametrize("change", [
    {"symbols": ["999999.SZ"]}, {"symbols": ["000001.SZ"] * 2}, {"symbols": ["000001.SZ"] * 5},
    {"start_date": "2026-11-01"}, {"end_date": "2026-10-24"}, {"start_date": "2026-02-30"},
    {"cards": [dict(BOARD["cards"][0], metric="exec_shell")]},
    {"cards": [dict(BOARD["cards"][0], type="pie")]},
    {"cards": [dict(BOARD["cards"][0], normalize="false")]},
    {"cards": [BOARD["cards"][0]] * 2}, {"script": "run arbitrary code"},
])
def test_invalid_board_never_becomes_an_applyable_plan(change):
    with pytest.raises(planner.PlanError):
        validate({**BOARD, **change})


@pytest.mark.parametrize("change", [
    {"strategies": ["custom_python"]}, {"strategies": ["momentum", "momentum"]},
    {"lookback": True}, {"top_k": 51}, {"rebalance_days": 0}, {"fee_bps": -1}, {"slippage_bps": 101},
    {"initial_capital": "100000"}, {"start_date": "2026-01-05"}, {"start_date": "2026-10-19"},
    {"symbols": ["000001.SZ"]}, {"stop_loss": 0.1},
])
def test_invalid_or_unsupported_strategy_rules_are_rejected(change):
    with pytest.raises(planner.PlanError):
        validate({**STRATEGY, **change}, "strategy")


def test_unsupported_requests_do_not_offer_partial_execution():
    raw = json.dumps(envelope(STRATEGY, unsupported=["暂不支持把多个因子合成一个策略。" ]))
    result = planner.validate_plan(raw, request("strategy"), CATALOG)
    assert result["status"] == "needs_changes" and result["config"] is None


@pytest.mark.parametrize("raw", ["not json", "[]", '{"summary":"x"}', "Here is code: {}"])
def test_malformed_model_output_is_sanitized(raw):
    with pytest.raises(planner.PlanError):
        planner.validate_plan(raw, request(), CATALOG)


def test_single_json_fence_is_supported_and_payload_contains_only_public_catalog():
    raw = '```json\n' + json.dumps(envelope()) + '\n```'
    assert planner.validate_plan(raw, request(), CATALOG)["config"] == BOARD
    payload = planner.planning_payload(request(current=BOARD), CATALOG)
    assert payload["stream"] is False
    material = json.loads(payload["messages"][1]["content"])
    assert "_calendar" not in material["catalog"]
    assert material["catalog"]["market_end"] == "2026-10-19"
    assert material["current"] == BOARD
    assert material["config_schema"]["additionalProperties"] is False


def mock_upstream(monkeypatch, status=200, content=None, finish="stop"):
    seen = []
    def handler(req):
        seen.append(req)
        assert req.headers["Authorization"] == "Bearer test-only-secret"
        assert b"test-only-secret" not in req.content
        if status != 200:
            return httpx.Response(status, text="test-only-secret provider private error")
        return httpx.Response(200, json={"choices": [{"message": {"content": content or json.dumps(envelope())}, "finish_reason": finish}]})
    monkeypatch.setattr(ai, "create_client", lambda: httpx.AsyncClient(transport=httpx.MockTransport(handler)))
    return seen


def client(monkeypatch):
    app = FastAPI(); app.include_router(route.router)
    monkeypatch.setattr(route, "prepare_catalog", lambda task: CATALOG)
    return TestClient(app)


def test_plan_route_validates_connection_and_uses_existing_header_only_key(monkeypatch):
    seen = mock_upstream(monkeypatch)
    with client(monkeypatch) as http:
        body = request().model_dump()
        assert http.post("/api/assistant/plan", json=body).status_code == 400
        assert http.post("/api/assistant/plan", json=body, headers={"X-AI-API-Key": "test-only-secret", "Origin": "https://evil.test"}).status_code == 403
        assert not seen
        response = http.post("/api/assistant/plan", json=body, headers={"X-AI-API-Key": "test-only-secret"})
        assert response.status_code == 200
        assert response.json()["config"] == BOARD
        assert response.headers["Cache-Control"] == "no-store"
        assert "test-only-secret" not in response.text
        assert len(seen) == 1


@pytest.mark.parametrize("status", [400, 401, 429, 500])
def test_provider_failure_does_not_leak_keys_and_releases_slots(monkeypatch, status):
    mock_upstream(monkeypatch, status)
    with client(monkeypatch) as http:
        for _ in range(6):
            response = http.post("/api/assistant/plan", json=request().model_dump(), headers={"X-AI-API-Key": "test-only-secret"})
            assert response.status_code == 502
            assert "test-only-secret" not in response.text and "provider private error" not in response.text


def test_truncation_and_oversized_output_never_apply(monkeypatch):
    for options in ({"finish": "length"}, {"content": "x" * 97000}):
        mock_upstream(monkeypatch, **options)
        with pytest.raises(planner.PlanError):
            asyncio.run(planner.generate_plan(request(), "test-only-secret", CATALOG))


def test_private_or_oversized_current_configuration_is_rejected():
    for current in ({"apiKey": "test-only-secret"}, {"title": "x" * 16001}):
        with pytest.raises(ValidationError):
            request(current=current)


def test_catalog_failure_releases_capacity(monkeypatch):
    def broken(task):
        raise OSError("private filesystem path")
    with client(monkeypatch) as http:
        monkeypatch.setattr(route, "prepare_catalog", broken)
        for _ in range(6):
            response = http.post("/api/assistant/plan", json=request().model_dump(), headers={"X-AI-API-Key": "test-only-secret"})
            assert response.status_code == 503 and "private filesystem path" not in response.text
    assert route._slots.acquire(blocking=False)
    route._slots.release()


def test_generated_strategy_can_run_in_real_engine_without_invented_results():
    from tests.test_strategy_lab import market_frame, params
    frame = market_frame()
    config = params(frame).model_dump(mode="json")
    calendar = sorted(frame.trade_date.dt.strftime("%Y-%m-%d").unique().tolist())
    catalog = {**CATALOG, "market_start": calendar[0], "market_end": calendar[-1], "_calendar": calendar}
    result = validate(config, "strategy", catalog)
    experiment = run_experiment(ExperimentRequest.model_validate(result["config"]), frame)
    assert len(experiment["results"]) == len(config["strategies"])
    assert experiment["results"][0]["curve"][0]["signal_date"] < experiment["actual_start"]
    assert experiment["config"] == result["config"]


@pytest.mark.parametrize("endpoint", ["plan", "predict"])
@pytest.mark.parametrize("already_disconnected", [False, True])
def test_client_disconnect_cancels_structured_request_and_releases_slot(monkeypatch, endpoint, already_disconnected):
    slots = BoundedSemaphore(1)
    monkeypatch.setattr(route, "_slots", slots)
    monkeypatch.setattr(route, "prepare_catalog", lambda task: CATALOG)
    monkeypatch.setattr(route, "build_prediction_context", lambda body: {})

    async def run():
        started, closed = asyncio.Event(), asyncio.Event()
        disconnected = already_disconnected

        async def upstream(*args):
            nonlocal disconnected
            started.set()
            disconnected = True
            try:
                await asyncio.Event().wait()
            finally:
                closed.set()

        monkeypatch.setattr(route, "generate_plan", upstream)
        monkeypatch.setattr(route, "generate_prediction", upstream)

        async def receive():
            if disconnected:
                return {"type": "http.disconnect"}
            await asyncio.Event().wait()

        body = request() if endpoint == "plan" else route.PredictionRequest(
            provider="deepseek", model="deepseek-flash", symbol="000001.SZ",
            factors=["return_5d", "return_20d", "volatility_20d"])
        connection = Request({"type": "http", "headers": []}, receive)
        with pytest.raises(HTTPException) as exc:
            await asyncio.wait_for(getattr(route, endpoint)(body, connection, "test-only-secret"), timeout=2)
        assert exc.value.status_code == 499
        assert slots.acquire(blocking=False)
        slots.release()
        if already_disconnected:
            assert not started.is_set(), "An abandoned request must not start a paid model call"
        else:
            assert started.is_set() and closed.is_set(), "Cancellation must close the active provider request"

    asyncio.run(run())
