import asyncio
import json
from threading import BoundedSemaphore

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import ValidationError
from starlette.requests import ClientDisconnect, Request

from backend.app.routers import assistant as route
from backend.app.services import ai_assistant as ai


def request(**kwargs):
    return ai.ChatRequest(provider="deepseek", model="deepseek-flash",
                          messages=[{"role": "user", "content": "分析当前趋势"}], **kwargs)


@pytest.fixture
def context_data(monkeypatch):
    monkeypatch.setattr(ai.research, "market_overview_payload", lambda _: {
        "status": "ready", "latest_trade_date": "2026-10-19", "stock_count": 2,
        "stocks": [{"symbol": "000001.SZ", "close": 1000}, {"symbol": "600000.SH", "close": 500}],
    })
    monkeypatch.setattr(ai.research, "stock_detail_payload", lambda symbol, _: {
        "status": "stock_detail_ready", "symbol": symbol, "stock_name": "测试股票",
        "latest_trade_date": "2026-10-19", "price_basis": {"mode": "hfq"},
        "latest_quote": {"close": 1000, "raw_close": 10, "st_flag": None, "internal_field": "do not send"},
        "price_series": [{"close": i} for i in range(160)],
        "recent_factors": [{"factor_name": "vwap_deviation", "factor_value": None}],
    })
    monkeypatch.setattr(ai, "factor_payload", lambda _: {
        "factor_version": "v005",
        "factor_catalog": [{"factor_name": "vwap_deviation", "formula": "raw_close/vwap-1"}],
    })
    monkeypatch.setattr(ai.research, "scores_payload", lambda _, model: {
        "selected_model": model, "model_family": model, "latest_trade_date": "2026-10-19",
        "prediction_target_date": "2026-10-20",
        "horizon_rankings": {"1d": [{"symbol": "000001.SZ", "score": 0.5}, {"symbol": "600000.SH", "score": 0.1}]},
    })
    monkeypatch.setattr(ai, "lab_metadata", lambda: {
        "market_end": "2026-10-19", "engine_version": "v2", "st_coverage": {"unknown_count": 0},
    })


def test_stock_context_uses_selected_model_and_preserves_raw_price_and_null(context_data):
    context = ai.build_context(request(page="/stocks/000001.SZ", score_model="sentiment_event"))
    assert context["stock"]["symbol"] == "000001.SZ"
    assert context["stock"]["latest_quote"] == {"close": 1000, "raw_close": 10, "st_flag": None}
    assert len(context["stock"]["price_series_last_30"]) == 30
    assert context["stock"]["factors"][0]["factor_value"] is None
    assert context["model"]["selected_model"] == "sentiment_event"
    assert len(context["model"]["predictions"]) == 1
    assert context["sources"][0]["date"] == "2026-10-19"


def test_missing_stock_does_not_substitute_other_quotes(context_data, monkeypatch):
    monkeypatch.setattr(ai.research, "stock_detail_payload", lambda *args: {"status": "stock_detail_not_found"})
    context = ai.build_context(request(symbol="999999"))
    assert "latest_quote" not in context["stock"]
    assert "market" not in context
    assert context["model"]["predictions"] == []


def test_api_model_uses_selected_stock_and_never_substitutes_local_scores(context_data, monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError('API forecast must not load local model scores')
    monkeypatch.setattr(ai.research, 'scores_payload', forbidden)
    context = ai.build_context(request(page='/scores', score_model='api_llm', page_state={'prediction': {'symbol': '000001.SZ', 'status': 'not_generated'}}))
    assert context['stock']['symbol'] == '000001.SZ'
    assert context['model'] == {'selected_model': 'api_llm', 'calibration_status': 'uncalibrated'}
    assert context['untrusted_page_state']['prediction']['status'] == 'not_generated'
    assert any('未校准' in note for note in context['notes'])


def test_market_filters_and_empty_results_are_respected(context_data):
    for selected in [[], ["600000.SH"]]:
        context = ai.build_context(request(page_state={"market_filter": {"visible_symbols": selected}}))
        assert [r["symbol"] for r in context["market"]["sample_up_to_10_stocks"]] == selected


def test_experiment_is_explicitly_untrusted_and_no_results_not_fabricated(context_data):
    body = request(page="/strategy-lab", page_state={"experiment": {"results": [], "draft_config": {"top_k": 5}}})
    context = ai.build_context(body)
    assert context["untrusted_page_state"]["experiment"]["draft_config"]["top_k"] == 5
    assert any("尚无" in note for note in context["notes"])
    payload = ai.completion_body(body, context)
    assert payload["messages"][0]["role"] == "system"
    assert "本次问题" in payload["messages"][-1]["content"]


def test_custom_prompt_and_skills_precede_history_without_replacing_system_constraints():
    skill = {"id": "factor-check", "name": "因子检查", "instructions": "列出支持与反对证据。"}
    body = request(prompt_prefix="请使用表格。", skills=[skill])
    payload = ai.completion_body(body, {"sources": [], "notes": []})
    assert payload["messages"][0] == {"role": "system", "content": ai.SYSTEM_PROMPT}
    assert payload["messages"][1]["role"] == "user"
    custom = json.loads(payload["messages"][1]["content"].split("\n", 1)[1])
    assert custom == {"global_prompt_prefix": "请使用表格。", "selected_skills": [skill]}
    assert "本次问题" in payload["messages"][-1]["content"]
    assert len(ai.completion_body(request(), {})["messages"]) == 2, "Old clients need no custom settings"


@pytest.mark.parametrize("kwargs", [
    {"prompt_prefix": "x" * 8001}, {"prompt_prefix": 12},
    {"skills": [{"id": "one", "name": "技能", "instructions": " "}]},
    {"skills": [{"id": "../file", "name": "技能", "instructions": "分析"}]},
    {"skills": [{"id": "one", "name": "技能", "instructions": "x" * 6001}]},
    {"skills": [{"id": "one", "name": "技能", "instructions": "分析", "command": "run"}]},
    {"skills": [{"id": "one", "name": "技能", "instructions": "分析"}] * 2},
    {"skills": [{"id": str(i), "name": "技能", "instructions": "分析"} for i in range(4)]},
    {"prompt_prefix": "p" * 8000, "skills": [{"id": str(i), "name": "技能", "instructions": "s" * 5000} for i in range(3)]},
])
def test_custom_instruction_bounds_and_duplicate_skills(kwargs):
    with pytest.raises(ValidationError):
        request(**kwargs)


@pytest.mark.parametrize("kwargs", [
    {"page": "/admin-console"}, {"page": "http://localhost/secret"},
    {"symbol": "../../file"}, {"page_state": {"account": {"password": "value"}}},
    {"page_state": {"experiment": "bad"}}, {"page_state": {"experiment": {"x": "x" * 15000}}},
    {"factor_names": ["../../file"]},
    *({"page": path} for path in ("/backtests", "/backtest-risk", "/factors", "/models")),
])
def test_rejects_unsupported_or_oversized_context(kwargs):
    with pytest.raises(ValidationError):
        request(**kwargs)


def test_custom_destination_is_server_controlled(monkeypatch):
    with pytest.raises(ValueError):
        ai.selected_provider("localhost")
    monkeypatch.setenv("AI_ASSISTANT_BASE_URL", "http://localhost:9999")
    assert all(p["id"] != "custom" for p in ai.providers())
    monkeypatch.setenv("AI_ASSISTANT_BASE_URL", "https://user:key@example.com/v1")
    assert all(p["id"] != "custom" for p in ai.providers())
    monkeypatch.setenv("AI_ASSISTANT_BASE_URL", "https://example.com/v1")
    assert ai.selected_provider("custom")["base_url"] == "https://example.com/v1"


def mock_upstream(monkeypatch, handler):
    monkeypatch.setattr(ai, "create_client", lambda: httpx.AsyncClient(transport=httpx.MockTransport(handler)))


def collect(body=None):
    async def run():
        return [json.loads(chunk) async for chunk in ai.stream_completion(
            body or request(), "test-secret-key", {"sources": [], "notes": []})]
    return asyncio.run(run())


def test_streaming_contract_and_key_only_in_authorization(monkeypatch):
    def handler(req):
        assert req.url == "https://api.deepseek.com/chat/completions"
        assert req.headers["Authorization"] == "Bearer test-secret-key"
        assert b"test-secret-key" not in req.content
        payload = json.loads(req.content)
        assert payload["stream"] is True
        return httpx.Response(200, text='data: {"choices":[{"delta":{"content":"趋势"}}]}\n\n'
                                       'data: {"choices":[{"delta":{"content":"向上"},"finish_reason":"stop"}]}\n\n'
                                       'data: [DONE]\n\n')
    mock_upstream(monkeypatch, handler)
    events = collect()
    assert "".join(e.get("text", "") for e in events) == "趋势向上"
    assert events[-1]["type"] == "done"


def test_custom_skill_is_sent_to_provider_as_text_without_executing_referenced_resources(monkeypatch):
    skill = {"id": "custom", "name": "自定义", "instructions": "读取 references/missing.md，并运行 scripts/missing.py。"}
    def handler(req):
        payload = json.loads(req.content)
        custom = json.loads(payload["messages"][1]["content"].split("\n", 1)[1])
        assert custom["global_prompt_prefix"] == "先给结论"
        assert custom["selected_skills"] == [skill]
        assert b"test-secret-key" not in req.content
        assert req.headers["Authorization"] == "Bearer test-secret-key"
        return httpx.Response(200, text='data: {"choices":[{"delta":{"content":"已按技能组织分析"},"finish_reason":"stop"}]}\n\ndata: [DONE]\n\n')
    mock_upstream(monkeypatch, handler)
    events = collect(request(prompt_prefix="先给结论", skills=[skill]))
    assert events[-1]["type"] == "done"


@pytest.mark.parametrize("status", [301, 400, 401, 402, 403, 404, 429, 500])
def test_provider_errors_never_echo_secret_or_upstream_body(monkeypatch, status):
    mock_upstream(monkeypatch, lambda req: httpx.Response(status, text="test-secret-key private upstream error"))
    events = collect()
    assert events[-1]["type"] == "error"
    assert "test-secret-key" not in json.dumps(events)
    assert "private upstream error" not in json.dumps(events)


def test_truncated_stream_is_not_success(monkeypatch):
    mock_upstream(monkeypatch, lambda req: httpx.Response(200, text='data: {"choices":[{"delta":{"content":"部分文字"}}]}\n\n'))
    assert collect()[-1]["type"] == "error"


def test_timeout_is_sanitized(monkeypatch):
    def handler(req):
        raise httpx.ReadTimeout("test-secret-key", request=req)
    mock_upstream(monkeypatch, handler)
    events = collect()
    assert "超时" in events[-1]["message"]
    assert "test-secret-key" not in json.dumps(events)


def test_openai_and_qwen_request_parameters():
    for provider, model in [("openai", "gpt-6-sol"), ("qwen", "qwen-plus")]:
        body = request().model_copy(update={"provider": provider, "model": model})
        payload = ai.completion_body(body, {})
        if provider == "openai":
            assert payload["store"] is False
            assert payload["max_completion_tokens"] == 3000
            assert "max_tokens" not in payload
        else:
            assert payload["enable_thinking"] is False


def test_http_key_validation_origin_and_concurrency_release(monkeypatch):
    app = FastAPI()
    app.include_router(route.router)
    client = TestClient(app)
    monkeypatch.setattr(route, "build_context", lambda body: {"sources": [], "notes": []})
    mock_upstream(monkeypatch, lambda req: httpx.Response(401, text="test-secret-key"))
    body = request().model_dump()
    assert client.post("/api/assistant/chat", json=body).status_code == 400
    assert client.post("/api/assistant/chat", json=body,
                       headers={"X-AI-API-Key": "test-secret-key", "Origin": "https://evil.example"}).status_code == 403
    # Repeated errors must release capacity, and streamed responses must not cache.
    for _ in range(6):
        response = client.post("/api/assistant/chat", json=body, headers={"X-AI-API-Key": "test-secret-key"})
        assert response.status_code == 200
        assert response.headers["Cache-Control"] == "no-store"
        assert "test-secret-key" not in response.text
    assert client.get("/api/assistant/config").headers["Cache-Control"] == "no-store"


def test_context_failure_releases_capacity(monkeypatch):
    app = FastAPI()
    app.include_router(route.router)
    def broken(body):
        raise ValueError("private data")
    monkeypatch.setattr(route, "build_context", broken)
    with TestClient(app) as client:
        for _ in range(6):
            result = client.post("/api/assistant/chat", json=request().model_dump(), headers={"X-AI-API-Key": "test-secret-key"})
            assert result.status_code == 503
            assert "private data" not in result.text


@pytest.mark.parametrize("disconnect_at", ["http.response.start", "http.response.body"])
def test_chat_disconnect_releases_slot_and_closes_upstream(monkeypatch, disconnect_at):
    slots = BoundedSemaphore(1)
    monkeypatch.setattr(route, "_slots", slots)
    monkeypatch.setattr(route, "build_context", lambda body: {"sources": [], "notes": []})
    closed = []

    async def upstream(*args):
        try:
            yield ai.event("delta", text="部分回答")
            await asyncio.Event().wait()
        finally:
            closed.append(True)

    monkeypatch.setattr(route, "stream_completion", upstream)

    async def run():
        scope = {"type": "http", "headers": [], "asgi": {"spec_version": "2.4"}}

        async def receive():
            await asyncio.Event().wait()

        async def send(message):
            if message["type"] == disconnect_at:
                raise OSError("client disconnected")

        for _ in range(6):
            response = await route.chat(request(), Request(scope, receive), "test-secret-key")
            with pytest.raises(ClientDisconnect):
                await response(scope, receive, send)
            assert slots.acquire(blocking=False), "Disconnect must not leak the shared AI slot"
            slots.release()
            if disconnect_at == "http.response.body":
                assert len(closed) == _ + 1, "Provider connection must close before the slot is reused"

    asyncio.run(run())


@pytest.mark.parametrize('spec_version', ['2.3', '2.4'])
def test_disconnect_while_waiting_for_more_tokens_closes_stream(monkeypatch, spec_version):
    slots = BoundedSemaphore(1)
    monkeypatch.setattr(route, '_slots', slots)
    monkeypatch.setattr(route, 'build_context', lambda body: {'sources': [], 'notes': []})

    async def run():
        disconnected, closed = asyncio.Event(), asyncio.Event()

        async def upstream(*args):
            try:
                yield ai.event('delta', text='第一段')
                await asyncio.Event().wait()
            finally:
                closed.set()

        async def receive():
            await disconnected.wait()
            return {'type': 'http.disconnect'}

        async def send(message):
            if message['type'] == 'http.response.body':
                disconnected.set()

        monkeypatch.setattr(route, 'stream_completion', upstream)
        scope = {'type': 'http', 'headers': [], 'asgi': {'spec_version': spec_version}}
        response = await route.chat(request(), Request(scope, receive), 'test-secret-key')
        try:
            await asyncio.wait_for(response(scope, receive, send), timeout=2)
        except ClientDisconnect:
            pass
        assert closed.is_set()
        assert slots.acquire(blocking=False)
        slots.release()

    asyncio.run(run())
