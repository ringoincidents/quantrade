import unittest

from quantrade.capabilities.fundamental_evidence import (
    FundamentalEvidenceError,
    FundamentalObservation,
    FundamentalProviderMetadata,
    FundamentalQuery,
    StaticFundamentalObservationProvider,
    to_thesis_observation,
)
from quantrade.capabilities.thesis_contract import SourceKind


class FundamentalEvidenceContractTests(unittest.TestCase):
    def _metadata(self):
        return FundamentalProviderMetadata(
            provider_id="FIXTURE",
            provider_version="1",
            source_license="TEST",
            network_required=False,
            model_required=False,
            point_in_time_capable=True,
            capital_authority=False,
        )

    def _obs(
        self,
        *,
        observation_id,
        metric_key="OPERATING_PROFIT",
        value=100.0,
        fiscal_period_end="2025-12-31",
        published_at="2026-02-01T09:00:00+09:00",
        retrieved_at="2026-10-05T12:00:00+09:00",
        revision_id=None,
        revision_of=None,
        restated=False,
    ):
        return FundamentalObservation(
            observation_id=observation_id,
            asset_id="KRX:000000",
            metric_key=metric_key,
            value=value,
            unit="KRW_MILLION",
            currency="KRW",
            fiscal_period_end=fiscal_period_end,
            published_at=published_at,
            retrieved_at=retrieved_at,
            source_provider="FIXTURE",
            source_document_id=f"DOC-{observation_id}",
            source_ref=f"fixture://source/{observation_id}",
            evidence_ref=f"fixture://evidence/{observation_id}",
            revision_id=revision_id,
            revision_of=revision_of,
            restated=restated,
        )

    def test_future_revision_is_excluded_from_historical_query(self):
        original = self._obs(
            observation_id="OBS-ORIGINAL",
            value=100.0,
            published_at="2026-02-01T09:00:00+09:00",
        )
        revision = self._obs(
            observation_id="OBS-REVISION",
            value=80.0,
            published_at="2026-04-01T09:00:00+09:00",
            revision_id="R2",
            revision_of="OBS-ORIGINAL",
            restated=True,
        )
        provider = StaticFundamentalObservationProvider(
            (original, revision),
            metadata=self._metadata(),
        )
        result = provider.query(
            FundamentalQuery(
                asset_id="KRX:000000",
                as_of="2026-03-01T00:00:00+09:00",
                metric_keys=("OPERATING_PROFIT",),
            )
        )
        self.assertEqual(1, len(result.observations))
        self.assertEqual(
            "OBS-ORIGINAL",
            result.observations[0]["observation_id"],
        )
        self.assertEqual(
            ("OBS-REVISION",),
            result.excluded_future_observation_ids,
        )
        self.assertTrue(
            result.revision_resolution[0][
                "future_revision_excluded"
            ]
        )

    def test_later_query_selects_published_revision(self):
        original = self._obs(
            observation_id="OBS-ORIGINAL",
            value=100.0,
            published_at="2026-02-01T09:00:00+09:00",
        )
        revision = self._obs(
            observation_id="OBS-REVISION",
            value=80.0,
            published_at="2026-04-01T09:00:00+09:00",
            revision_id="R2",
            revision_of="OBS-ORIGINAL",
            restated=True,
        )
        provider = StaticFundamentalObservationProvider(
            (original, revision),
            metadata=self._metadata(),
        )
        result = provider.query(
            FundamentalQuery(
                asset_id="KRX:000000",
                as_of="2026-05-01T00:00:00+09:00",
            )
        )
        self.assertEqual(
            "OBS-REVISION",
            result.observations[0]["observation_id"],
        )
        self.assertEqual(80.0, result.observations[0]["value"])

    def test_multiple_metrics_resolve_revisions_independently(self):
        provider = StaticFundamentalObservationProvider(
            (
                self._obs(
                    observation_id="OP-1",
                    metric_key="OPERATING_PROFIT",
                    value=100.0,
                ),
                self._obs(
                    observation_id="REV-1",
                    metric_key="REVENUE",
                    value=500.0,
                ),
            ),
            metadata=self._metadata(),
        )
        result = provider.query(
            FundamentalQuery(
                asset_id="KRX:000000",
                as_of="2026-03-01T00:00:00+09:00",
            )
        )
        self.assertEqual(2, len(result.observations))
        self.assertEqual(
            {"OPERATING_PROFIT", "REVENUE"},
            {item["metric_key"] for item in result.observations},
        )

    def test_published_after_retrieved_is_rejected(self):
        bad = self._obs(
            observation_id="BAD",
            published_at="2026-10-06T00:00:00+09:00",
            retrieved_at="2026-10-05T00:00:00+09:00",
        )
        with self.assertRaisesRegex(
            FundamentalEvidenceError,
            "published_at cannot be after retrieved_at",
        ):
            StaticFundamentalObservationProvider(
                (bad,),
                metadata=self._metadata(),
            )

    def test_duplicate_observation_id_is_rejected(self):
        one = self._obs(observation_id="SAME")
        two = self._obs(
            observation_id="SAME",
            metric_key="REVENUE",
        )
        with self.assertRaisesRegex(
            FundamentalEvidenceError,
            "duplicate observation_id",
        ):
            StaticFundamentalObservationProvider(
                (one, two),
                metadata=self._metadata(),
            )

    def test_provider_cannot_require_model(self):
        metadata = FundamentalProviderMetadata(
            provider_id="FIXTURE",
            provider_version="1",
            source_license="TEST",
            network_required=False,
            model_required=True,
            point_in_time_capable=True,
            capital_authority=False,
        )
        with self.assertRaisesRegex(
            FundamentalEvidenceError,
            "must not require a model",
        ):
            StaticFundamentalObservationProvider(
                (),
                metadata=metadata,
            )

    def test_provider_cannot_have_capital_authority(self):
        metadata = FundamentalProviderMetadata(
            provider_id="FIXTURE",
            provider_version="1",
            source_license="TEST",
            network_required=False,
            model_required=False,
            point_in_time_capable=True,
            capital_authority=True,
        )
        with self.assertRaisesRegex(
            FundamentalEvidenceError,
            "cannot have capital authority",
        ):
            StaticFundamentalObservationProvider(
                (),
                metadata=metadata,
            )

    def test_period_filter_is_deterministic(self):
        provider = StaticFundamentalObservationProvider(
            (
                self._obs(
                    observation_id="OLD",
                    fiscal_period_end="2024-12-31",
                ),
                self._obs(
                    observation_id="NEW",
                    fiscal_period_end="2025-12-31",
                ),
            ),
            metadata=self._metadata(),
        )
        result = provider.query(
            FundamentalQuery(
                asset_id="KRX:000000",
                as_of="2026-03-01T00:00:00+09:00",
                fiscal_period_end_from="2025-01-01",
                fiscal_period_end_to="2025-12-31",
            )
        )
        self.assertEqual(
            ["NEW"],
            [item["observation_id"] for item in result.observations],
        )

    def test_reversed_period_range_is_rejected(self):
        provider = StaticFundamentalObservationProvider(
            (),
            metadata=self._metadata(),
        )
        with self.assertRaisesRegex(
            FundamentalEvidenceError,
            "range is reversed",
        ):
            provider.query(
                FundamentalQuery(
                    asset_id="KRX:000000",
                    as_of="2026-03-01T00:00:00+09:00",
                    fiscal_period_end_from="2025-12-31",
                    fiscal_period_end_to="2025-01-01",
                )
            )

    def test_adapter_creates_external_thesis_observation_reference_only(self):
        item = self._obs(observation_id="OBS-ADAPTER")
        adapted = to_thesis_observation(item)
        self.assertEqual("OBS-ADAPTER", adapted.observation_id)
        self.assertEqual(
            SourceKind.EXTERNAL_EVIDENCE.value,
            adapted.source_kind,
        )
        self.assertEqual(
            "fixture://evidence/OBS-ADAPTER",
            adapted.source_ref,
        )
        self.assertEqual(item.published_at, adapted.observed_at)

    def test_query_result_has_no_investment_authority(self):
        provider = StaticFundamentalObservationProvider(
            (self._obs(observation_id="OBS"),),
            metadata=self._metadata(),
        )
        result = provider.query(
            FundamentalQuery(
                asset_id="KRX:000000",
                as_of="2026-03-01T00:00:00+09:00",
            )
        )
        self.assertFalse(result.authority["model_called"])
        self.assertFalse(
            result.authority["canonical_evidence_created"]
        )
        self.assertFalse(
            result.authority["portfolio_proposal_created"]
        )
        self.assertFalse(
            result.authority["committee_decision_created"]
        )
        self.assertFalse(result.authority["execution_authorized"])


if __name__ == "__main__":
    unittest.main()
