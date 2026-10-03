from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from quantrade.institutional.ceo_observer import (
    QuanTradeCEOObserver,
    build_ceo_proposals_read_model,
)


HISTORY_SCHEMA = "quantrade_ceo_operating_history_v1"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _hash(value: dict[str, Any]) -> str:
    raw = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def empty_history() -> dict[str, Any]:
    return {
        "schema": HISTORY_SCHEMA,
        "decision_episode_versions": [],
        "operational_events": [],
        "capability_gaps": [],
        "last_reviewed_at": None,
        "note": (
            "Append-only operating evidence for the QuanTrade CEO observer. "
            "Repeated publication of the same episode does not count as new evidence."
        ),
    }


def load_history(path: Path) -> dict[str, Any]:
    if not path.exists():
        return empty_history()
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or payload.get("schema") != HISTORY_SCHEMA:
        raise ValueError("unsupported CEO operating-history schema")
    for key in (
        "decision_episode_versions",
        "operational_events",
        "capability_gaps",
    ):
        if not isinstance(payload.get(key), list):
            raise ValueError(f"{key} must be a list")
    return payload


def extract_decision_episode(snapshot: dict[str, Any], *, recorded_at: str) -> dict[str, Any] | None:
    if snapshot.get("schema") != "quantrade_institutional_decision_snapshot_v1":
        raise ValueError("unsupported institutional decision snapshot schema")

    episode = snapshot.get("decision_episode") or {}
    episode_id = str(episode.get("episode_id") or "").strip()
    if not episode_id:
        return None

    economics = snapshot.get("economics") or {}
    source_payload = {
        "decision_episode": episode,
        "economics": economics,
        "market_context": snapshot.get("market_context") or {},
        "shock": snapshot.get("shock") or {},
        "baseline_comparison": snapshot.get("baseline_comparison") or {},
        "publication_status": snapshot.get("publication_status"),
    }
    return {
        "episode_id": episode_id,
        "evidence_hash": _hash(source_payload),
        "recorded_at": recorded_at,
        "publication_status": snapshot.get("publication_status"),
        "workflow_latency_proxy_ms": economics.get("workflow_latency_ms"),
        "model_cost_usd": economics.get("model_cost_usd"),
        "model_call_count": economics.get("model_call_count"),
        "model_telemetry_available": economics.get("model_telemetry_available"),
        "market_move_during_deliberation_bps": economics.get(
            "market_move_during_deliberation_bps"
        ),
        "source_provenance": snapshot.get("projection_provenance") or {},
    }


def append_episode_version(
    history: dict[str, Any],
    record: dict[str, Any] | None,
    *,
    max_versions: int = 500,
) -> bool:
    if record is None:
        return False

    versions = history["decision_episode_versions"]
    if any(
        item.get("episode_id") == record["episode_id"]
        and item.get("evidence_hash") == record["evidence_hash"]
        for item in versions
    ):
        return False

    revision = (
        sum(1 for item in versions if item.get("episode_id") == record["episode_id"])
        + 1
    )
    versions.append({**record, "revision": revision})
    if len(versions) > max_versions:
        history["decision_episode_versions"] = versions[-max_versions:]
    return True


def latest_decision_episodes(history: dict[str, Any]) -> list[dict[str, Any]]:
    latest: dict[str, dict[str, Any]] = {}
    for item in history["decision_episode_versions"]:
        episode_id = str(item.get("episode_id") or "")
        if episode_id:
            latest[episode_id] = item
    return list(latest.values())


def run_review(
    *,
    snapshot: dict[str, Any],
    history: dict[str, Any],
    reviewed_at: str,
    hq_outcomes: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    record = extract_decision_episode(snapshot, recorded_at=reviewed_at)
    append_episode_version(history, record)
    history["last_reviewed_at"] = reviewed_at

    observer = QuanTradeCEOObserver()
    proposals = observer.review(
        decision_episodes=latest_decision_episodes(history),
        operational_events=history["operational_events"],
        capability_gaps=history["capability_gaps"],
        hq_outcomes=hq_outcomes,
    )
    feed = build_ceo_proposals_read_model(
        proposals,
        generated_at=reviewed_at,
    )
    return history, feed


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Compile durable QuanTrade operating evidence into the public CEO "
            "improvement-proposal read model. No AI or transaction API is used."
        )
    )
    parser.add_argument(
        "--decision-snapshot",
        default="institutional_decision_snapshot.json",
    )
    parser.add_argument(
        "--history",
        default="ceo_operating_history.json",
    )
    parser.add_argument(
        "--output",
        default="ceo_improvement_proposals.json",
    )
    parser.add_argument("--reviewed-at")
    parser.add_argument(
        "--hq-outcomes",
        help=(
            "Optional authenticated Holdings HQ outcome projection downloaded "
            "before this process runs. If omitted, proposal generation remains "
            "valid but cannot suppress proposals already known to HQ."
        ),
    )
    args = parser.parse_args()

    reviewed_at = args.reviewed_at or _now()
    snapshot = json.loads(
        Path(args.decision_snapshot).read_text(encoding="utf-8")
    )
    history_path = Path(args.history)
    history = load_history(history_path)
    hq_outcomes = None
    if args.hq_outcomes:
        outcome_path = Path(args.hq_outcomes)
        if outcome_path.exists():
            hq_outcomes = json.loads(outcome_path.read_text(encoding="utf-8"))

    history, feed = run_review(
        snapshot=snapshot,
        history=history,
        reviewed_at=reviewed_at,
        hq_outcomes=hq_outcomes,
    )

    history_path.write_text(
        json.dumps(history, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    Path(args.output).write_text(
        json.dumps(feed, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    print(json.dumps({
        "history_schema": history["schema"],
        "unique_decision_episodes": len(latest_decision_episodes(history)),
        "proposal_count": len(feed["proposals"]),
        "reviewed_at": reviewed_at,
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
