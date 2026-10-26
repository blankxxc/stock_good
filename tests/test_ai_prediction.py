import copy
import json
from datetime import date, timedelta

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import ValidationError

from backend.app.routers import assistant as route
from backend.app.services import ai_assistant as ai, ai_prediction as prediction
from backend.app.services.ai_structured import StructuredError


def request(**changes):
    return prediction.PredictionRequest(**{**dict(provider='deepseek', model='test-model', symbol='000001.SZ',
        factors=['return_5d', 'volatility_20d', 'volume_shock_20d']), **changes})


def model_result(**changes):
    return {**dict(status='estimated', probability_up=.5, probability_flat=.2, probability_down=.3,
        rationale='动量提供支持，波动和成交信号存在分歧。', evidence=[dict(factor='return_5d', impact='supports_up', explanation='动量为正。')],
        risks=['未来市场环境可能发生变化。']), **changes}


@pytest.fixture
def data(monkeypatch):
    dates = [(date(2026, 8, 1) + timedelta(days=i)).isoformat() for i in range(60)]
    factors = request().factors + ['missing_factor']
    meta = dict(stocks=[dict(symbol='000001.SZ', stock_name='测试股票')], metrics=[dict(id=f, label=f, group='因子', description='公式') for f in factors],
        market_start=dates[0], market_end=dates[-1], data_version='test-v1')
    values = {'close': [100. + i for i in range(60)], 'volume': [1000.] * 60,
              **{f: [.1] * 60 for f in factors}, 'missing_factor': [.4] * 59 + [None]}
    series = dict(dates=dates, series=[dict(metric=k, values=v) for k, v in values.items()], price_basis='后复权', data_version='test-v1')
    monkeypatch.setattr(prediction, 'visualization_metadata', lambda: meta)
    queries = []
    def load(body):
        queries.append(body)
        return series
    monkeypatch.setattr(prediction, 'query_series', load)
    return meta, series, values, queries


@pytest.mark.parametrize('changes', [dict(horizon_days=2), dict(horizon_days=True), dict(horizon_days=5.),
    dict(neutral_band_pct=0), dict(neutral_band_pct=float('nan')), dict(neutral_band_pct=True),
    dict(symbol='../secret'), dict(factors=['x', 'x', 'y']), dict(factors=['a']),
    dict(factors=[f'f{i}' for i in range(11)]), dict(factors=['a', 'b', '../c']), dict(api_key='private')])
def test_request_rejects_unsupported_inputs(changes):
    with pytest.raises(ValidationError):
        request(**changes)


@pytest.mark.parametrize('changes', [dict(probability_up=.9), dict(probability_up=-.1), dict(probability_up=float('nan')),
    dict(probability_up='0.5'), dict(probability_up=True), dict(probability_flat=None), dict(evidence=[]),
    dict(evidence=[dict(factor='unknown', impact='supports_up', explanation='伪造')]),
    dict(evidence=[dict(factor='missing_factor', impact='mixed', explanation='旧值不算当前值')]),
    dict(status='insufficient_data'), dict(risks=[]), dict(extra='unexpected')])
def test_bad_model_results_never_get_normalized(data, changes):
    context = prediction.build_prediction_context(request(factors=request().factors + ['missing_factor']))
    with pytest.raises(StructuredError) as exc:
        prediction.validate_prediction(json.dumps(model_result(**changes)), context)
    assert exc.value.status == 502


def test_valid_result_and_abstention(data):
    context = prediction.build_prediction_context(request())
    assert prediction.validate_prediction('```json\n' + json.dumps(model_result()) + '\n```', context)['probability_up'] == .5
    abstain = model_result(status='insufficient_data', probability_up=None, probability_flat=None, probability_down=None, evidence=[])
    assert prediction.validate_prediction(json.dumps(abstain), context)['probability_up'] is None
    with pytest.raises(StructuredError):
        prediction.validate_prediction(json.dumps(model_result(evidence=model_result()['evidence'] * 2)), context)


def test_history_reference_keeps_closed_band_boundaries_and_missing_windows():
    dates = ['a', 'b']
    for close in (101., 99.):
        result = prediction.history_reference(dates, [100., close], 1, .01)
        assert result['probability_flat'] == 1
    assert prediction.history_reference(['a', 'b', 'c'], [100., None, 200.], 2, .01)['sample_count'] == 0
    assert prediction.history_reference(dates, [None, None], 1, .01)['probability_up'] is None
    result = prediction.history_reference([str(i) for i in range(300)], [100.] * 300, 20, .01)
    assert result['sample_count'] == 252 and result['last_window_end'] == '299' and result['first_window_start'] == '28'


def test_context_uses_actual_current_values_and_bounded_history(data):
    meta, series, values, queries = data
    context = prediction.build_prediction_context(request(factors=request().factors + ['missing_factor']))
    assert context['as_of'] == meta['market_end']
    assert context['prices'][-1]['close'] == values['close'][-1] and len(context['prices']) == 30
    assert context['factors'][-1]['value'] is None and context['factors'][-1]['value_date'] is None
    assert context['factors'][-1]['recent'][-2]['value'] == .4
    assert '后复权' in context['event_definition']
    assert set(queries[0].metrics) == {'close', 'volume', *request().factors, 'missing_factor'}
    assert queries[0].end_date.isoformat() == meta['market_end']
    changed = copy.deepcopy(context)
    values['close'][-1] += 1
    assert prediction.build_prediction_context(request(factors=request().factors + ['missing_factor']))['snapshot_id'] != changed['snapshot_id']


@pytest.mark.parametrize('failure', ['unknown_stock', 'unknown_factor', 'zero_volume', 'missing_close', 'missing_factor', 'short_history', 'version'])
def test_unusable_inputs_stop_before_model(data, failure):
    meta, series, values, _ = data
    body = request()
    if failure == 'unknown_stock': body = request(symbol='999999.SH')
    if failure == 'unknown_factor': body = request(factors=['a', 'b', 'c'])
    if failure == 'zero_volume': values['volume'][-1] = 0
    if failure == 'missing_close': values['close'][-1] = None
    if failure == 'missing_factor': values['return_5d'][-1] = None
    if failure == 'short_history': values['close'][:40] = [None] * 40
    if failure == 'version': series['data_version'] = 'changed'
    with pytest.raises(StructuredError): prediction.build_prediction_context(body)


def client():
    app = FastAPI(); app.include_router(route.router)
    return TestClient(app)


def upstream(monkeypatch, status=200, result=None):
    seen = []
    def handler(req):
        seen.append(json.loads(req.content))
        assert req.headers['Authorization'] == 'Bearer test-only-secret'
        assert 'test-only-secret' not in req.content.decode()
        assert req.url.host == 'api.deepseek.com'
        if status != 200: return httpx.Response(status, text='test-only-secret private provider error')
        return httpx.Response(200, json={'choices': [{'message': {'content': json.dumps(result or model_result())}, 'finish_reason': 'stop'}]})
    monkeypatch.setattr(ai, 'create_client', lambda: httpx.AsyncClient(transport=httpx.MockTransport(handler)))
    return seen


def test_endpoint_validates_key_origin_and_uses_server_snapshot(data, monkeypatch):
    seen = upstream(monkeypatch)
    with client() as http:
        body = request().model_dump()
        assert http.post('/api/assistant/predict', json=body).status_code == 400
        headers = {'X-AI-API-Key': 'test-only-secret'}
        assert http.post('/api/assistant/predict', json=body, headers={**headers, 'Origin': 'https://evil.test'}).status_code == 403
        assert not seen
        response = http.post('/api/assistant/predict', json=body, headers=headers)
        assert response.status_code == 200 and response.headers['Cache-Control'] == 'no-store'
        result = response.json()
        assert result['calibration_status'] == 'uncalibrated' and 'test-only-secret' not in response.text
        supplied = json.loads(seen[0]['messages'][1]['content'])['data']
        assert supplied == result['input']
        assert seen[0]['stream'] is False and result['model'] == body['model']
        data[2]['volume'][-1] = 0
        assert http.post('/api/assistant/predict', json=body, headers=headers).status_code == 422
        assert len(seen) == 1


@pytest.mark.parametrize('status', [401, 429, 500])
def test_provider_errors_sanitized_and_capacity_released(data, monkeypatch, status):
    upstream(monkeypatch, status=status)
    with client() as http:
        for _ in range(6):
            response = http.post('/api/assistant/predict', json=request().model_dump(), headers={'X-AI-API-Key': 'test-only-secret'})
            assert response.status_code == 502 and 'test-only-secret' not in response.text and 'private provider' not in response.text


def test_context_failure_sanitized_and_capacity_released(monkeypatch):
    def fail(body): raise OSError('private local path')
    monkeypatch.setattr(route, 'build_prediction_context', fail)
    with client() as http:
        for _ in range(6):
            response = http.post('/api/assistant/predict', json=request().model_dump(), headers={'X-AI-API-Key': 'test-only-secret'})
            assert response.status_code == 503 and 'private local path' not in response.text
