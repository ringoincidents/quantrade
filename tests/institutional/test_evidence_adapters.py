from __future__ import annotations

import json
import os
import tempfile
import unittest

from quantrade.institutional.evidence_adapters import (
    ChangeEventEvidenceAdapter,
    EvidenceIngestionService,
    MarketIndicatorEvidenceAdapter,
    NonAuthoritativeSourceError,
    briefing_presentation_state,
    evidence_fingerprint,
    reject_ai_briefing_as_evidence,
)
from quantrade.institutional.service import InstitutionalKernel


CHANGE_EVENT = {
    "timestamp": "2026-09-17T00:00:00+00:00",
    "asset": {
        "symbol": "FIX",
        "name": "Fixture Asset",
        "market_country": "US",
        "currency": "USD",
    },
    "source": "news_event_cards.anomaly",
    "event_type": "변동성_급증",
    "observed_value": 24.15,
    "baseline": None,
    "change": 97.9,
    "reliability": 1.0,
    "related_assets": [],
    "priority": {
        "priority_score": 999.0,
        "factors": {"reliability": 1.0, "magnitude": 97.9},
    },
}

MARKET_DOCUMENT = {
    "generated_at": "2026-09-18T14:28:31+00:00",
    "schema": "market_indicators_fixture",
    "state_board": {
        "rows": [{
            "symbol": "FIX",
            "name": "Fixture Asset",
            "volatility_20d_pct": 24.29,
            "volatility_percentile": 98.9,
            "adx_14": 16.0,
            "data_status": None,
        }],
        "correlation": {
            "avg_pairwise_correlation": None,
            "pair_count": 0,
            "symbol_count": 1,
            "window_days": 60,
        },
    },
    "indicator_board": {
        "rows": [{
            "symbol": "FIX",
            "name": "Fixture Asset",
            "per": None,
            "per_status": "데이터 소스 미연결",
            "volatility_20d_pct": 24.29,
            "momentum_20d_pct": -92.43,
            "adx_14": 16.0,
            "data_status": None,
        }]
    },
}


class EvidenceAdapterTests(unittest.TestCase):
    def setUp(self):
        fd, self.path = tempfile.mkstemp(suffix=".sqlite3")
        os.close(fd)
        self.kernel = InstitutionalKernel(self.path)
        self.case_id = self.kernel.ingest_event(
            "MATERIAL_REVIEW_REQUIRED",
            "fixture",
            "FIX",
            {"reason": "fixture evidence review"},
            case_id="QT-2026-5201",
        )["case_id"]

    def tearDown(self):
        self.kernel.close()
        if os.path.exists(self.path):
            os.remove(self.path)

    def test_change_event_preserves_fact_and_provenance(self):
        candidate = ChangeEventEvidenceAdapter().convert(CHANGE_EVENT)
        self.assertEqual("FIX", candidate.subject)
        self.assertEqual("변동성_급증", candidate.metric)
        self.assertEqual(24.15, candidate.observed_value)
        self.assertEqual(1.0, candidate.provenance["reliability"])
        self.assertEqual(97.9, candidate.provenance["factual_observation"]["change"])
        self.assertEqual(999.0, candidate.routing_metadata["priority_score"])
        self.assertTrue(candidate.routing_metadata["not_materiality"])

    def test_priority_score_never_becomes_case_materiality(self):
        candidate = ChangeEventEvidenceAdapter().convert(CHANGE_EVENT)
        evidence_id = EvidenceIngestionService(self.kernel).attach(self.case_id, candidate)
        case = self.kernel.get_case(self.case_id)
        self.assertIsNone(case["materiality"])
        self.assertEqual([], self.kernel.founder_desk())
        row = self.kernel.conn.execute(
            "SELECT provenance FROM evidence WHERE evidence_id=?", (evidence_id,)
        ).fetchone()
        provenance = json.loads(row["provenance"])
        self.assertEqual(999.0, provenance["routing_metadata"]["priority_score"])
        self.assertNotIn("materiality", provenance["routing_metadata"])

    def test_indicator_values_and_missingness_are_preserved(self):
        candidates = MarketIndicatorEvidenceAdapter().convert_document(MARKET_DOCUMENT)
        vol = next(
            c for c in candidates
            if c.source.endswith("indicator_board") and c.metric == "volatility_20d_pct"
        )
        per = next(c for c in candidates if c.metric == "per")
        corr = next(c for c in candidates if c.metric == "avg_pairwise_correlation")
        self.assertEqual(24.29, vol.observed_value)
        self.assertIsNone(per.observed_value)
        self.assertTrue(per.provenance["missing"])
        self.assertEqual("데이터 소스 미연결", per.provenance["metric_status"])
        self.assertIsNone(corr.observed_value)
        self.assertTrue(corr.provenance["missing"])

    def test_fingerprint_is_stable_and_excludes_priority(self):
        first = ChangeEventEvidenceAdapter().convert(CHANGE_EVENT)
        changed = dict(CHANGE_EVENT)
        changed["priority"] = {"priority_score": 0.0001, "factors": {"magnitude": 0}}
        second = ChangeEventEvidenceAdapter().convert(changed)
        self.assertEqual(first.fingerprint, second.fingerprint)
        direct = evidence_fingerprint(
            source=first.source,
            observed_at=first.observed_at,
            subject=first.subject,
            metric=first.metric,
            observed_value=first.observed_value,
        )
        self.assertEqual(first.fingerprint, direct)

    def test_reingestion_is_idempotent_per_case(self):
        candidate = ChangeEventEvidenceAdapter().convert(CHANGE_EVENT)
        service = EvidenceIngestionService(self.kernel)
        first = service.attach(self.case_id, candidate)
        ledger_before = len(self.kernel.ledger(self.case_id))
        second = service.attach(self.case_id, candidate)
        ledger_after = len(self.kernel.ledger(self.case_id))
        self.assertEqual(first, second)
        self.assertEqual(ledger_before, ledger_after)
        count = self.kernel.conn.execute(
            "SELECT COUNT(*) c FROM evidence WHERE case_id=?", (self.case_id,)
        ).fetchone()["c"]
        self.assertEqual(1, count)

    def test_observation_timestamp_is_preserved(self):
        candidate = ChangeEventEvidenceAdapter().convert(CHANGE_EVENT)
        evidence_id = EvidenceIngestionService(self.kernel).attach(self.case_id, candidate)
        row = self.kernel.conn.execute(
            "SELECT observed_at FROM evidence WHERE evidence_id=?", (evidence_id,)
        ).fetchone()
        self.assertEqual(CHANGE_EVENT["timestamp"], row["observed_at"])

    def test_evidence_can_back_institutional_position(self):
        candidate = ChangeEventEvidenceAdapter().convert(CHANGE_EVENT)
        evidence_id = EvidenceIngestionService(self.kernel).attach(self.case_id, candidate)
        position_id = self.kernel.add_position(
            self.case_id,
            "IID",
            "OBSERVED",
            "Structured anomaly requires institutional review; no trade conclusion.",
            evidence_refs=[evidence_id],
        )
        row = self.kernel.conn.execute(
            "SELECT evidence_refs FROM institutional_positions WHERE position_id=?",
            (position_id,),
        ).fetchone()
        self.assertEqual([evidence_id], json.loads(row["evidence_refs"]))

    def test_ai_briefing_is_presentation_not_evidence(self):
        briefing = {
            "schema": "ai_briefing_v1",
            "status": "api_failed",
            "generated_at": "2026-09-18T13:53:49+00:00",
            "summary": None,
        }
        state = briefing_presentation_state(briefing)
        self.assertFalse(state["authoritative_evidence"])
        self.assertFalse(state["content_available"])
        self.assertEqual("api_failed", state["status"])
        with self.assertRaises(NonAuthoritativeSourceError):
            reject_ai_briefing_as_evidence(briefing)
        count = self.kernel.conn.execute("SELECT COUNT(*) c FROM evidence").fetchone()["c"]
        self.assertEqual(0, count)

    def test_adapter_has_no_execution_dependency(self):
        import inspect
        import quantrade.institutional.evidence_adapters as module

        source = inspect.getsource(module)
        for forbidden in (
            "import autoexec",
            "from autoexec",
            "pending_actions",
            "import real_portfolio_sync",
            "from real_portfolio_sync",
        ):
            self.assertNotIn(forbidden, source)


if __name__ == "__main__":
    unittest.main()
