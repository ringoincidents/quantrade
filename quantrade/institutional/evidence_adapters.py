from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any, Iterable


class NonAuthoritativeSourceError(ValueError):
    pass


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def evidence_fingerprint(
    *,
    source: str,
    observed_at: str | None,
    subject: str,
    metric: str,
    observed_value: Any,
) -> str:
    """Stable factual identity. Routing/priority metadata is deliberately excluded."""
    body = _canonical({
        "source": source,
        "observed_at": observed_at,
        "subject": subject,
        "metric": metric,
        "observed_value": observed_value,
    })
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class EvidenceCandidate:
    source: str
    observed_at: str | None
    subject: str
    metric: str
    observed_value: Any
    fact: str
    provenance: dict
    routing_metadata: dict

    @property
    def fingerprint(self) -> str:
        return evidence_fingerprint(
            source=self.source,
            observed_at=self.observed_at,
            subject=self.subject,
            metric=self.metric,
            observed_value=self.observed_value,
        )


class ChangeEventEvidenceAdapter:
    """Convert structured research change_events into sourced Evidence candidates."""

    def convert(self, event: dict) -> EvidenceCandidate:
        asset = event.get("asset") or {}
        subject = str(asset.get("symbol") or asset.get("name") or "UNKNOWN")
        source = str(event.get("source") or "news_event_cards.change_events")
        metric = str(event.get("event_type") or "UNSPECIFIED_CHANGE")
        observed = event.get("observed_value")
        observed_at = event.get("timestamp")
        reliability = event.get("reliability")
        priority = event.get("priority") or {}

        factual = {
            "event_type": metric,
            "observed_value": observed,
            "baseline": event.get("baseline"),
            "change": event.get("change"),
        }
        provenance = {
            "adapter": "ChangeEventEvidenceAdapter",
            "asset": asset,
            "raw_source": source,
            "reliability": reliability,
            "related_assets": event.get("related_assets") or [],
            "factual_observation": factual,
        }
        routing = {
            "priority_score": priority.get("priority_score"),
            "priority_factors": priority.get("factors") or {},
            "not_materiality": True,
        }
        return EvidenceCandidate(
            source=source,
            observed_at=observed_at,
            subject=subject,
            metric=metric,
            observed_value=observed,
            fact=_canonical(factual),
            provenance=provenance,
            routing_metadata=routing,
        )


class MarketIndicatorEvidenceAdapter:
    """Convert deterministic market-indicator measurements without filling missing data."""

    ROW_METRICS = (
        "volatility_20d_pct",
        "volatility_percentile",
        "momentum_20d_pct",
        "adx_14",
        "per",
    )

    def convert_row(
        self,
        row: dict,
        *,
        generated_at: str | None,
        schema: str | None,
        board: str,
    ) -> list[EvidenceCandidate]:
        subject = str(row.get("symbol") or row.get("name") or "UNKNOWN")
        source = f"market_indicators.{board}"
        status = row.get("data_status")
        candidates = []
        for metric in self.ROW_METRICS:
            if metric not in row:
                continue
            value = row.get(metric)
            provenance = {
                "adapter": "MarketIndicatorEvidenceAdapter",
                "schema": schema,
                "board": board,
                "name": row.get("name"),
                "data_status": status,
                "metric_status": row.get(f"{metric}_status"),
                "deterministic": True,
                "missing": value is None,
            }
            candidates.append(EvidenceCandidate(
                source=source,
                observed_at=generated_at,
                subject=subject,
                metric=metric,
                observed_value=value,
                fact=_canonical({"metric": metric, "value": value}),
                provenance=provenance,
                routing_metadata={},
            ))
        return candidates

    def convert_correlation(
        self,
        correlation: dict,
        *,
        generated_at: str | None,
        schema: str | None,
    ) -> EvidenceCandidate:
        value = correlation.get("avg_pairwise_correlation")
        return EvidenceCandidate(
            source="market_indicators.state_board.correlation",
            observed_at=generated_at,
            subject="PORTFOLIO",
            metric="avg_pairwise_correlation",
            observed_value=value,
            fact=_canonical({
                "metric": "avg_pairwise_correlation",
                "value": value,
                "pair_count": correlation.get("pair_count"),
                "symbol_count": correlation.get("symbol_count"),
                "window_days": correlation.get("window_days"),
            }),
            provenance={
                "adapter": "MarketIndicatorEvidenceAdapter",
                "schema": schema,
                "deterministic": True,
                "missing": value is None,
            },
            routing_metadata={},
        )

    def convert_document(self, document: dict) -> list[EvidenceCandidate]:
        generated_at = document.get("generated_at")
        schema = document.get("schema")
        out: list[EvidenceCandidate] = []
        for board_name in ("state_board", "indicator_board"):
            board = document.get(board_name) or {}
            for row in board.get("rows") or []:
                out.extend(self.convert_row(
                    row,
                    generated_at=generated_at,
                    schema=schema,
                    board=board_name,
                ))
        correlation = (document.get("state_board") or {}).get("correlation")
        if isinstance(correlation, dict):
            out.append(self.convert_correlation(
                correlation, generated_at=generated_at, schema=schema
            ))
        return out


class EvidenceIngestionService:
    def __init__(self, kernel: Any):
        self.kernel = kernel

    def attach(self, case_id: str, candidate: EvidenceCandidate) -> str:
        provenance = dict(candidate.provenance)
        if candidate.routing_metadata:
            provenance["routing_metadata"] = candidate.routing_metadata
        provenance["fingerprint"] = candidate.fingerprint
        provenance["subject"] = candidate.subject
        provenance["metric"] = candidate.metric
        return self.kernel.add_evidence(
            case_id,
            candidate.source,
            candidate.fact,
            provenance,
            observed_at=candidate.observed_at,
            fingerprint=candidate.fingerprint,
        )

    def attach_many(self, case_id: str, candidates: Iterable[EvidenceCandidate]) -> list[str]:
        return [self.attach(case_id, candidate) for candidate in candidates]


def briefing_presentation_state(briefing: dict) -> dict:
    """Expose briefing health without converting model prose into Evidence."""
    return {
        "schema": briefing.get("schema"),
        "status": briefing.get("status"),
        "generated_at": briefing.get("generated_at"),
        "authoritative_evidence": False,
        "content_available": briefing.get("status") == "ok",
    }


def reject_ai_briefing_as_evidence(briefing: dict) -> None:
    raise NonAuthoritativeSourceError(
        f"ai_briefing status={briefing.get('status')!r} is presentation, not canonical Evidence"
    )
