from __future__ import annotations

from scripts.run_ceo_operating_review import (
    append_episode_version,
    empty_history,
    extract_decision_episode,
    latest_decision_episodes,
    run_review,
)


def _snapshot(
    episode_id: str,
    *,
    latency_ms=None,
    model_cost_usd=None,
):
    return {
        "schema": "quantrade_institutional_decision_snapshot_v1",
        "publication_status": "TEST",
        "decision_episode": {
            "episode_id": episode_id,
            "committee_action": "WAIT",
        },
        "economics": {
            "workflow_latency_ms": latency_ms,
            "model_cost_usd": model_cost_usd,
            "model_call_count": 1 if model_cost_usd is not None else None,
            "model_telemetry_available": model_cost_usd is not None,
        },
        "market_context": {},
        "shock": {},
        "baseline_comparison": {},
        "projection_provenance": {"test": True},
    }


def test_same_published_episode_does_not_count_twice():
    history = empty_history()
    snapshot = _snapshot("EP-1", latency_ms=15000, model_cost_usd=0.01)

    history, first = run_review(
        snapshot=snapshot,
        history=history,
        reviewed_at="2026-10-03T00:00:00+00:00",
    )
    history, second = run_review(
        snapshot=snapshot,
        history=history,
        reviewed_at="2026-10-04T00:00:00+00:00",
    )

    assert len(history["decision_episode_versions"]) == 1
    assert len(latest_decision_episodes(history)) == 1
    assert first["proposals"] == []
    assert second["proposals"] == []


def test_updated_same_episode_preserves_revision_but_counts_once():
    history = empty_history()
    partial = _snapshot("EP-1")
    measured = _snapshot("EP-1", latency_ms=15000, model_cost_usd=0.01)

    first = extract_decision_episode(
        partial,
        recorded_at="2026-10-03T00:00:00+00:00",
    )
    second = extract_decision_episode(
        measured,
        recorded_at="2026-10-04T00:00:00+00:00",
    )
    assert append_episode_version(history, first)
    assert append_episode_version(history, second)

    assert len(history["decision_episode_versions"]) == 2
    assert [x["revision"] for x in history["decision_episode_versions"]] == [1, 2]
    latest = latest_decision_episodes(history)
    assert len(latest) == 1
    assert latest[0]["workflow_latency_proxy_ms"] == 15000


def test_three_measured_unique_episodes_create_latency_proposal():
    history = empty_history()
    feed = None
    for index in range(1, 4):
        history, feed = run_review(
            snapshot=_snapshot(
                f"EP-{index}",
                latency_ms=15000 + index,
                model_cost_usd=0.01,
            ),
            history=history,
            reviewed_at=f"2026-10-0{index}T00:00:00+00:00",
        )

    assert feed is not None
    assert feed["schema"] == "quantrade_ceo_proposals_v1"
    assert feed["source"] == "QUANTRADE_LLM_CEO"
    assert len(feed["proposals"]) == 1
    proposal = feed["proposals"][0]
    assert proposal["issue_type"] == "DECISION_LATENCY_BOTTLENECK"
    assert proposal["proposal_id"].startswith("QTPROP-")
    assert proposal["auto_apply"] is False
    assert proposal["requires_hq_review"] is True


def test_unmeasured_episodes_do_not_trigger_false_zero_cost_statistics():
    history = empty_history()
    feed = None
    for index in range(1, 5):
        history, feed = run_review(
            snapshot=_snapshot(f"PARTIAL-{index}"),
            history=history,
            reviewed_at=f"2026-10-0{index}T00:00:00+00:00",
        )

    assert feed is not None
    assert feed["proposals"] == []
