import unittest

from quantrade.capabilities.issuer_identity import (
    IssuerIdentityError,
    IssuerIdentityRecord,
    IssuerIdentityRegistry,
    dart_override_from_resolution,
    load_identity_registry,
    resolve_verified_issuer_identity,
    validate_registry,
    verify_identity_against_filing,
)


class IssuerIdentityRegistryTests(unittest.TestCase):
    def test_default_registry_loads_verified_records(self):
        registry = load_identity_registry()
        self.assertEqual(
            "quantrade_issuer_identity_registry_v1",
            registry.schema,
        )
        self.assertGreaterEqual(len(registry.records), 2)

    def test_samsung_electronics_resolves_from_verified_cache(self):
        registry = load_identity_registry()
        result = resolve_verified_issuer_identity(
            registry,
            asset_id="KRX:005930",
        )
        self.assertEqual(
            "VERIFIED_CACHED_IDENTITY",
            result.status,
        )
        self.assertEqual("005930", result.stock_code)
        self.assertEqual("00126380", result.external_id)
        self.assertEqual(
            {"005930": "00126380"},
            dart_override_from_resolution(result),
        )

    def test_unregistered_asset_does_not_guess(self):
        registry = load_identity_registry()
        result = resolve_verified_issuer_identity(
            registry,
            asset_id="KRX:005380",
        )
        self.assertEqual("NOT_REGISTERED", result.status)
        self.assertIsNone(result.external_id)
        with self.assertRaisesRegex(
            IssuerIdentityError,
            "VERIFIED_CACHED_IDENTITY",
        ):
            dart_override_from_resolution(result)

    def test_live_filing_match_verifies_cached_identity(self):
        record = IssuerIdentityRecord(
            asset_id="KRX:005930",
            stock_code="005930",
            provider_id="OPEN_DART",
            external_id="00126380",
            source_kind="fixture",
            source_ref="fixture://registry",
            verified_at="2026-10-08T11:19:21Z",
            verification_kind="fixture",
            verification_ref="fixture://verification",
        )
        result = verify_identity_against_filing(
            record,
            observed_stock_code="005930",
            observed_external_id="00126380",
            filing_ref="fixture://filing",
        )
        self.assertEqual("VERIFIED", result.status)
        self.assertFalse(result.authority["execution_authorized"])

    def test_live_filing_mismatch_fails_identity(self):
        record = IssuerIdentityRecord(
            asset_id="KRX:005930",
            stock_code="005930",
            provider_id="OPEN_DART",
            external_id="00126380",
            source_kind="fixture",
            source_ref="fixture://registry",
            verified_at="2026-10-08T11:19:21Z",
            verification_kind="fixture",
            verification_ref="fixture://verification",
        )
        result = verify_identity_against_filing(
            record,
            observed_stock_code="006400",
            observed_external_id="00126380",
            filing_ref="fixture://wrong-filing",
        )
        self.assertEqual("MISMATCH", result.status)

    def test_duplicate_external_id_is_rejected(self):
        first = IssuerIdentityRecord(
            asset_id="KRX:005930",
            stock_code="005930",
            provider_id="OPEN_DART",
            external_id="00126380",
            source_kind="fixture",
            source_ref="fixture://one",
            verified_at="2026-10-08T00:00:00Z",
            verification_kind="fixture",
            verification_ref="fixture://one-verify",
        )
        second = IssuerIdentityRecord(
            asset_id="KRX:000001",
            stock_code="000001",
            provider_id="OPEN_DART",
            external_id="00126380",
            source_kind="fixture",
            source_ref="fixture://two",
            verified_at="2026-10-08T00:00:00Z",
            verification_kind="fixture",
            verification_ref="fixture://two-verify",
        )
        with self.assertRaisesRegex(
            IssuerIdentityError,
            "duplicate provider external identity",
        ):
            validate_registry(
                IssuerIdentityRegistry(
                    schema="quantrade_issuer_identity_registry_v1",
                    version="fixture",
                    records=(first, second),
                )
            )

    def test_registry_has_no_capital_authority(self):
        registry = load_identity_registry()
        result = resolve_verified_issuer_identity(
            registry,
            asset_id="KRX:006400",
        )
        self.assertFalse(result.authority["valuation_created"])
        self.assertFalse(
            result.authority["portfolio_proposal_created"]
        )
        self.assertFalse(result.authority["execution_authorized"])


if __name__ == "__main__":
    unittest.main()
