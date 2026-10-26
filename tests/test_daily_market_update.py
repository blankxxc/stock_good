from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def isolate_benchmark_refresh(monkeypatch):
    import scripts.update_daily_market_data as update

    monkeypatch.setattr(update, "_refresh_benchmark_inputs", lambda *_: {
        "status": "no_change", "data_changed": False, "fingerprint": "index-1",
    })


def test_daily_orchestrator_skips_derived_rebuild_when_market_data_is_unchanged(monkeypatch, tmp_path):
    import data.adapters.real_csi300_akshare as adapter
    import scripts.update_daily_market_data as update

    monkeypatch.setattr(update, "REPORT", tmp_path / "daily-update.json")
    monkeypatch.setattr(update, "STATE", tmp_path / "pipeline-state.json")
    monkeypatch.setattr(update, "PIPELINE_LOCK", tmp_path / "pipeline.lock")
    monkeypatch.setattr(
        update,
        "_latest_real_data_status",
        lambda: {"exists": True, "latest_trade_date": "2024-01-03", "fingerprint": "raw-1"},
    )
    update._write_json_atomic(
        update.STATE,
        {
            "steps": {
                step: {"status": "ok", "input_fingerprint": update._factor_input_fingerprint("raw-1", "index-1") if step in {"materialize_factor_store", "build_model_feature_matrix"} else "raw-1"}
                for step in update.DERIVED_STEPS
            }
        },
    )
    monkeypatch.setattr(
        adapter,
        "write_real_csi300_daily",
        lambda **_kwargs: {
            "status": "no_change",
            "data_changed": False,
            "write_performed": False,
            "new_row_count": 0,
            "revised_row_count": 0,
        },
    )

    report = update.run_daily_update()

    assert report["status"] == "no_change"
    assert report["data_changed"] is False
    assert [step["status"] for step in report["steps"]] == ["no_change", "no_change", *["skipped"] * len(update.DERIVED_STEPS)]
    assert all("checkpoint" in step.get("reason", "") for step in report["steps"][2:])


def test_daily_orchestrator_resumes_failed_checkpoint_on_no_change(monkeypatch, tmp_path):
    import data.adapters.real_csi300_akshare as adapter
    import data.adapters.sentiment_event_data as sentiment_data
    import factors.offline.polars_factor_engine as factors
    import feature_store.point_in_time_join.build_model_feature_matrix as pit
    import models.cograsp_current as cograsp
    import models.research_loop_research_loop as research
    import models.sentiment_event_fusion as sentiment_model
    import scripts.build_latest_live_scores as live
    import scripts.update_daily_market_data as update

    monkeypatch.setattr(update, "REPORT", tmp_path / "daily-update.json")
    monkeypatch.setattr(update, "STATE", tmp_path / "pipeline-state.json")
    monkeypatch.setattr(update, "PIPELINE_LOCK", tmp_path / "pipeline.lock")
    monkeypatch.setattr(
        update,
        "_latest_real_data_status",
        lambda: {"exists": True, "latest_trade_date": "2024-01-03", "fingerprint": "raw-2"},
    )
    update._write_json_atomic(
        update.STATE,
        {
            "steps": {
                "materialize_factor_store": {"status": "ok", "input_fingerprint": update._factor_input_fingerprint("raw-2", "index-1")},
                "build_labels": {"status": "failed", "input_fingerprint": "raw-2"},
                "train_cograsp_current": {"status": "failed", "input_fingerprint": "raw-1"},
                "build_latest_live_scores": {"status": "ok", "input_fingerprint": "raw-1"},
                "refresh_sentiment_event_data": {"status": "failed", "input_fingerprint": "raw-1"},
                "train_sentiment_event_fusion": {"status": "failed", "input_fingerprint": "raw-1"},
                "build_sentiment_event_scores": {"status": "failed", "input_fingerprint": "raw-1"},
            }
        },
    )
    monkeypatch.setattr(
        adapter,
        "write_real_csi300_daily",
        lambda **_kwargs: {"status": "no_change", "data_changed": False, "write_performed": False},
    )
    monkeypatch.setattr(factors, "materialize_factor_store", lambda **_kwargs: (_ for _ in ()).throw(AssertionError("factor step is current")))
    calls: list[str] = []
    monkeypatch.setattr(pit, "build_model_feature_matrix", lambda **kwargs: calls.append("pit") or {"status": "ok", "output_rows": 10})
    monkeypatch.setattr(research, "build_labels", lambda **_kwargs: (None, {"status": "ok", "row_count": 10}))
    monkeypatch.setattr(cograsp, "train_current_cograsp", lambda _market: calls.append("train") or {"status": "ok"})
    monkeypatch.setattr(live, "build_latest_live_scores", lambda: calls.append("live") or {"status": "ok", "rows": 3})
    monkeypatch.setattr(sentiment_data, "update_sentiment_event_data", lambda **_kwargs: calls.append("refresh_sentiment") or {"status": "ok", "market_sentiment_rows": 3})
    monkeypatch.setattr(sentiment_model, "train_sentiment_event_fusion", lambda _market: calls.append("train_sentiment") or {"status": "ok", "training_sample_count": 8})
    monkeypatch.setattr(sentiment_model, "build_sentiment_event_scores", lambda: calls.append("sentiment_scores") or {"status": "ok", "prediction_rows": 3})

    report = update.run_daily_update()

    assert report["status"] == "ok"
    assert report["resumed_from_checkpoint"] is True
    assert [step["status"] for step in report["steps"]] == [
        "no_change", "no_change", "skipped", "ok", "ok", "ok", "ok", "ok", "ok", "ok",
    ]
    assert calls == ["pit", "train", "live", "refresh_sentiment", "train_sentiment", "sentiment_scores"]
    state = update._read_json(update.STATE)
    assert state["published_raw_fingerprint"] == "raw-2"
    assert state["steps"]["build_labels"]["status"] == "ok"
    assert state["steps"]["build_model_feature_matrix"]["input_fingerprint"] == update._factor_input_fingerprint("raw-2", "index-1")


def test_daily_orchestrator_stops_dependent_steps_after_failure(monkeypatch, tmp_path):
    import data.adapters.real_csi300_akshare as adapter
    import factors.offline.polars_factor_engine as factors
    import models.research_loop_research_loop as research
    import scripts.build_latest_live_scores as live
    import scripts.update_daily_market_data as update

    monkeypatch.setattr(update, "REPORT", tmp_path / "daily-update.json")
    monkeypatch.setattr(update, "STATE", tmp_path / "pipeline-state.json")
    monkeypatch.setattr(update, "PIPELINE_LOCK", tmp_path / "pipeline.lock")
    monkeypatch.setattr(
        update,
        "_latest_real_data_status",
        lambda: {"exists": True, "latest_trade_date": "2024-01-04", "fingerprint": "raw-3"},
    )
    monkeypatch.setattr(
        adapter,
        "write_real_csi300_daily",
        lambda **_kwargs: {"status": "ok", "data_changed": True, "write_performed": True},
    )
    monkeypatch.setattr(factors, "materialize_factor_store", lambda **_kwargs: {"status": "failed"})
    monkeypatch.setattr(research, "build_labels", lambda **_kwargs: (_ for _ in ()).throw(AssertionError("must be skipped")))
    monkeypatch.setattr(live, "build_latest_live_scores", lambda: (_ for _ in ()).throw(AssertionError("must be skipped")))

    report = update.run_daily_update()

    assert report["status"] == "failed"
    assert [step["status"] for step in report["steps"]] == [
        "ok", "no_change", "failed", *["skipped"] * (len(update.DERIVED_STEPS) - 1),
    ]
    state = update._read_json(update.STATE)
    assert state["steps"]["materialize_factor_store"]["status"] == "failed"
    assert state.get("published_raw_fingerprint") is None


def test_fetch_news_forces_sentiment_refresh_and_downstream_retrain(monkeypatch, tmp_path):
    import data.adapters.real_csi300_akshare as adapter
    import data.adapters.sentiment_event_data as sentiment_data
    import models.sentiment_event_fusion as sentiment_model
    import scripts.update_daily_market_data as update

    monkeypatch.setattr(update, "REPORT", tmp_path / "daily-update.json")
    monkeypatch.setattr(update, "STATE", tmp_path / "pipeline-state.json")
    monkeypatch.setattr(update, "PIPELINE_LOCK", tmp_path / "pipeline.lock")
    monkeypatch.setattr(
        update,
        "_latest_real_data_status",
        lambda: {"exists": True, "latest_trade_date": "2024-01-03", "fingerprint": "raw-news"},
    )
    update._write_json_atomic(
        update.STATE,
        {
            "steps": {
                step: {"status": "ok", "input_fingerprint": update._factor_input_fingerprint("raw-news", "index-1") if step in {"materialize_factor_store", "build_model_feature_matrix"} else "raw-news"}
                for step in update.DERIVED_STEPS
            }
        },
    )
    monkeypatch.setattr(
        adapter,
        "write_real_csi300_daily",
        lambda **_kwargs: {"status": "no_change", "data_changed": False, "write_performed": False},
    )
    calls: list[str] = []
    monkeypatch.setattr(
        sentiment_data,
        "update_sentiment_event_data",
        lambda **kwargs: calls.append(f"refresh:{kwargs['fetch_news']}") or {"status": "ok"},
    )
    monkeypatch.setattr(
        sentiment_model,
        "train_sentiment_event_fusion",
        lambda _market: calls.append("train") or {"status": "ok"},
    )
    monkeypatch.setattr(
        sentiment_model,
        "build_sentiment_event_scores",
        lambda: calls.append("scores") or {"status": "ok"},
    )

    report = update.run_daily_update(fetch_news=True)

    assert [step["status"] for step in report["steps"]] == [
        "no_change", "no_change", "skipped", "skipped", "skipped", "skipped", "skipped", "ok", "ok", "ok",
    ]
    assert calls == ["refresh:True", "train", "scores"]


def test_index_change_rebuilds_factors_even_when_stock_data_is_unchanged(monkeypatch, tmp_path):
    import data.adapters.real_csi300_akshare as adapter
    import factors.offline.polars_factor_engine as factors
    import feature_store.point_in_time_join.build_model_feature_matrix as pit
    import scripts.update_daily_market_data as update

    monkeypatch.setattr(update, "REPORT", tmp_path / "update.json")
    monkeypatch.setattr(update, "STATE", tmp_path / "state.json")
    monkeypatch.setattr(update, "PIPELINE_LOCK", tmp_path / "pipeline.lock")
    monkeypatch.setattr(update, "_latest_real_data_status", lambda: {"exists": True, "fingerprint": "raw-1"})
    monkeypatch.setattr(adapter, "write_real_csi300_daily", lambda **_: {"status": "no_change", "data_changed": False})
    update._write_json_atomic(update.STATE, {"steps": {
        name: {"status": "ok", "input_fingerprint": update._factor_input_fingerprint("raw-1", "index-1") if name in {"materialize_factor_store", "build_model_feature_matrix"} else "raw-1"}
        for name in update.DERIVED_STEPS
    }})
    monkeypatch.setattr(update, "_refresh_benchmark_inputs", lambda *_: {
        "status": "ok", "data_changed": True, "fingerprint": "index-2",
    })
    calls = []
    monkeypatch.setattr(factors, "materialize_factor_store", lambda **_: calls.append("factors") or {"status": "ok"})
    monkeypatch.setattr(pit, "build_model_feature_matrix", lambda **kwargs: calls.append(f"pit:{kwargs['validate_existing']}") or {"status": "ok"})
    report = update.run_daily_update()
    assert report["status"] == "ok" and report["data_changed"] is True
    assert calls == ["factors", "pit:True"]
    saved = update._read_json(update.STATE)["steps"]
    for name in ["materialize_factor_store", "build_model_feature_matrix"]:
        assert saved[name]["input_fingerprint"] == update._factor_input_fingerprint("raw-1", "index-2")


def test_point_in_time_failure_stops_publishing_new_scores(monkeypatch, tmp_path):
    import data.adapters.real_csi300_akshare as adapter
    import factors.offline.polars_factor_engine as factors
    import feature_store.point_in_time_join.build_model_feature_matrix as pit
    import models.research_loop_research_loop as research
    import scripts.update_daily_market_data as update

    monkeypatch.setattr(update, "REPORT", tmp_path / "update.json")
    monkeypatch.setattr(update, "STATE", tmp_path / "state.json")
    monkeypatch.setattr(update, "PIPELINE_LOCK", tmp_path / "pipeline.lock")
    monkeypatch.setattr(update, "_latest_real_data_status", lambda: {"exists": True, "fingerprint": "raw-1"})
    monkeypatch.setattr(adapter, "write_real_csi300_daily", lambda **_: {"status": "ok", "data_changed": True})
    monkeypatch.setattr(factors, "materialize_factor_store", lambda **_: {"status": "ok"})
    monkeypatch.setattr(pit, "build_model_feature_matrix", lambda **_: (_ for _ in ()).throw(AssertionError("future-available rows")))
    monkeypatch.setattr(research, "build_labels", lambda **_: pytest.fail("labels must wait for the PIT gate"))

    report = update.run_daily_update()

    assert report["status"] == "failed"
    by_step = {step["step"]: step for step in report["steps"]}
    assert by_step["build_model_feature_matrix"]["status"] == "failed"
    assert all(by_step[name]["status"] == "skipped" for name in update.DERIVED_STEPS[2:])
    assert update._read_json(update.STATE).get("published_raw_fingerprint") is None
