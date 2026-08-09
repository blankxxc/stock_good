from __future__ import annotations


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
                step: {"status": "ok", "input_fingerprint": "raw-1"}
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
    assert [step["status"] for step in report["steps"]] == [
        "no_change", "skipped", "skipped", "skipped", "skipped", "skipped", "skipped", "skipped", "skipped",
    ]
    assert all("checkpoint" in step.get("reason", "") for step in report["steps"][1:])


def test_daily_orchestrator_resumes_failed_checkpoint_on_no_change(monkeypatch, tmp_path):
    import data.adapters.real_csi300_akshare as adapter
    import data.adapters.sentiment_event_data as sentiment_data
    import factors.offline.polars_factor_engine as factors
    import models.cograsp_current as cograsp
    import models.research_loop_research_loop as research
    import models.sentiment_event_fusion as sentiment_model
    import scripts.build_latest_live_scores as live
    import scripts.train_finmamba_official as finmamba
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
                "materialize_factor_store": {"status": "ok", "input_fingerprint": "raw-2"},
                "build_labels": {"status": "failed", "input_fingerprint": "raw-2"},
                "train_cograsp_current": {"status": "failed", "input_fingerprint": "raw-1"},
                "build_latest_live_scores": {"status": "ok", "input_fingerprint": "raw-1"},
                "refresh_sentiment_event_data": {"status": "failed", "input_fingerprint": "raw-1"},
                "train_sentiment_event_fusion": {"status": "failed", "input_fingerprint": "raw-1"},
                "build_sentiment_event_scores": {"status": "failed", "input_fingerprint": "raw-1"},
                "train_finmamba_official": {"status": "failed", "input_fingerprint": "raw-1"},
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
    monkeypatch.setattr(research, "build_labels", lambda **_kwargs: (None, {"status": "ok", "row_count": 10}))
    monkeypatch.setattr(cograsp, "train_current_cograsp", lambda _market: calls.append("train") or {"status": "ok"})
    monkeypatch.setattr(live, "build_latest_live_scores", lambda: calls.append("live") or {"status": "ok", "rows": 3})
    monkeypatch.setattr(sentiment_data, "update_sentiment_event_data", lambda **_kwargs: calls.append("refresh_sentiment") or {"status": "ok", "market_sentiment_rows": 3})
    monkeypatch.setattr(sentiment_model, "train_sentiment_event_fusion", lambda _market: calls.append("train_sentiment") or {"status": "ok", "training_sample_count": 8})
    monkeypatch.setattr(sentiment_model, "build_sentiment_event_scores", lambda: calls.append("sentiment_scores") or {"status": "ok", "prediction_rows": 3})
    monkeypatch.setattr(finmamba, "train_official_finmamba", lambda **_kwargs: calls.append("finmamba") or {"status": "blocked_runtime"})

    report = update.run_daily_update()

    assert report["status"] == "ok"
    assert report["resumed_from_checkpoint"] is True
    assert [step["status"] for step in report["steps"]] == [
        "no_change", "skipped", "ok", "ok", "ok", "ok", "ok", "ok", "blocked_runtime",
    ]
    assert calls == ["train", "live", "refresh_sentiment", "train_sentiment", "sentiment_scores", "finmamba"]
    state = update._read_json(update.STATE)
    assert state["published_raw_fingerprint"] == "raw-2"
    assert state["steps"]["build_labels"]["status"] == "ok"


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
        "ok", "failed", "skipped", "skipped", "skipped", "skipped", "skipped", "skipped", "skipped",
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
                step: {"status": "ok", "input_fingerprint": "raw-news"}
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
        "no_change", "skipped", "skipped", "skipped", "skipped", "ok", "ok", "ok", "skipped",
    ]
    assert calls == ["refresh:True", "train", "scores"]
