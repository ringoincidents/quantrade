import unittest

from quantrade.capabilities.features import (
    NativeFeatureProvider,
    ProviderMetadata,
    FeatureObservation,
    compare_providers,
)


class MirrorProvider:
    metadata = ProviderMetadata(
        provider_id="fixture.mirror.v1",
        capability="FeatureProvider",
        implementation="test-fixture",
        version_or_revision="1",
        license="test-only",
    )

    def compute(self, closes):
        base = NativeFeatureProvider().compute(closes)
        return FeatureObservation(
            schema=base.schema,
            provider={
                **base.provider,
                "provider_id": self.metadata.provider_id,
                "implementation": self.metadata.implementation,
                "version_or_revision": self.metadata.version_or_revision,
                "license": self.metadata.license,
            },
            input_count=base.input_count,
            features=base.features,
            authority=base.authority,
        )


class FeatureProviderTests(unittest.TestCase):
    def test_reference_provider_is_deterministic_and_non_authoritative(self):
        closes = [100, 101, 102, 103, 104, 105]
        first = NativeFeatureProvider().compute(closes)
        second = NativeFeatureProvider().compute(closes)

        self.assertEqual(first, second)
        self.assertEqual("quantrade_feature_observation_v1", first.schema)
        self.assertFalse(first.authority["canonical_evidence_created"])
        self.assertFalse(first.authority["risk_limit_changed"])
        self.assertFalse(first.authority["investment_decision_created"])
        self.assertFalse(first.authority["execution_authorized"])

    def test_provider_and_version_are_preserved_for_reproducibility(self):
        result = NativeFeatureProvider().compute([100, 101, 102])
        self.assertEqual("quantrade.native.features.v1", result.provider["provider_id"])
        self.assertEqual("v1", result.provider["version_or_revision"])
        self.assertEqual("SANDBOX", result.provider["status"])

    def test_invalid_market_data_fails_closed(self):
        provider = NativeFeatureProvider()
        with self.assertRaises(ValueError):
            provider.compute([100])
        with self.assertRaises(ValueError):
            provider.compute([100, 0])

    def test_same_case_can_compare_replaceable_providers_without_promotion(self):
        result = compare_providers(
            [100, 101, 102, 103, 104, 105],
            [NativeFeatureProvider(), MirrorProvider()],
        )
        self.assertEqual(2, len(result["observations"]))
        self.assertEqual(
            result["observations"][0]["features"],
            result["observations"][1]["features"],
        )
        self.assertFalse(result["authority"]["provider_promoted"])
        self.assertFalse(result["authority"]["canonical_evidence_created"])
        self.assertFalse(result["authority"]["execution_authorized"])


if __name__ == "__main__":
    unittest.main()
