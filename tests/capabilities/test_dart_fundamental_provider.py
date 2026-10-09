import io
import json
import unittest
from datetime import datetime, timezone
import zipfile

from quantrade.capabilities.dart_fundamental_provider import (
    DartApiError,
    DartCorpCodeResolver,
    DartFundamentalObservationProvider,
    DartPointInTimeUnavailable,
    DartProviderConfig,
    DartProviderError,
    UrlLibDartTransport,
)
from quantrade.capabilities.fundamental_evidence import FundamentalQuery


class FakeDartTransport:
    def __init__(self, *, filings, financial_payloads):
        self.filings = filings
        self.financial_payloads = financial_payloads
        self.calls = []

    def get_bytes(self, endpoint, params):
        self.calls.append((endpoint, dict(params)))
        if endpoint != "corpCode.xml":
            raise AssertionError(endpoint)
        xml = """<?xml version="1.0" encoding="UTF-8"?>
<result>
  <list>
    <corp_code>00126380</corp_code>
    <corp_name>삼성전자</corp_name>
    <stock_code>005930</stock_code>
    <modify_date>20261001</modify_date>
  </list>
</result>
""".encode("utf-8")
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as archive:
            archive.writestr("CORPCODE.xml", xml)
        return buffer.getvalue()

    def get_json(self, endpoint, params):
        self.calls.append((endpoint, dict(params)))
        if endpoint == "list.json":
            return {
                "status": "000",
                "message": "정상",
                "page_no": 1,
                "page_count": 100,
                "total_count": len(self.filings),
                "total_page": 1,
                "list": list(self.filings),
            }
        if endpoint == "fnlttSinglAcntAll.json":
            key = (
                str(params["bsns_year"]),
                str(params["reprt_code"]),
                str(params["fs_div"]),
            )
            return self.financial_payloads.get(
                key,
                {
                    "status": "013",
                    "message": "조회된 데이타가 없습니다.",
                },
            )
        raise AssertionError(endpoint)


def filing(
    receipt,
    report_name,
    receipt_date,
    *,
    stock_code="005930",
):
    return {
        "corp_cls": "Y",
        "corp_name": "삼성전자",
        "corp_code": "00126380",
        "stock_code": stock_code,
        "report_nm": report_name,
        "rcept_no": receipt,
        "flr_nm": "삼성전자",
        "rcept_dt": receipt_date,
        "rm": "C",
    }


def financial_payload(
    receipt,
    *,
    amount="10,000",
    ytd="",
    account_id="dart_OperatingIncomeLoss",
    account_nm="영업이익",
    statement_division="IS",
    account_detail="-",
):
    return {
        "status": "000",
        "message": "정상",
        "list": [
            {
                "rcept_no": receipt,
                "reprt_code": "11011",
                "bsns_year": "2025",
                "corp_code": "00126380",
                "sj_div": statement_division,
                "sj_nm": "손익계산서",
                "account_id": account_id,
                "account_nm": account_nm,
                "account_detail": account_detail,
                "thstrm_nm": "제 57 기",
                "thstrm_amount": amount,
                "thstrm_add_amount": ytd,
                "frmtrm_nm": "제 56 기",
                "frmtrm_amount": "9,000",
                "currency": "KRW",
            }
        ],
    }


class DartTransportRetryTests(unittest.TestCase):
    def test_json_transport_retries_truncated_response(self):
        class SequenceTransport(UrlLibDartTransport):
            def __init__(self):
                super().__init__(
                    max_attempts=3,
                    retry_backoff_seconds=0.0,
                )
                self.calls = 0

            def _request(self, endpoint, params):
                self.calls += 1
                if self.calls == 1:
                    return b'{"status":"000","list":[{"broken":"x'
                return b'{"status":"000","list":[]}'

        transport = SequenceTransport()
        payload = transport.get_json("fixture.json", {"secret": "hidden"})
        self.assertEqual("000", payload["status"])
        self.assertEqual(2, transport.calls)

    def test_json_transport_fails_after_retry_bound(self):
        class BrokenTransport(UrlLibDartTransport):
            def __init__(self):
                super().__init__(
                    max_attempts=2,
                    retry_backoff_seconds=0.0,
                )
                self.calls = 0

            def _request(self, endpoint, params):
                self.calls += 1
                return b'{"status":"000","list":['

        transport = BrokenTransport()
        with self.assertRaisesRegex(
            DartProviderError,
            "after 2 attempts",
        ):
            transport.get_json("fixture.json", {})
        self.assertEqual(2, transport.calls)


class DartFundamentalProviderTests(unittest.TestCase):
    def _provider(self, transport):
        return DartFundamentalObservationProvider(
            api_key="x" * 40,
            transport=transport,
            config=DartProviderConfig(
                statement_scope="CFS",
                allow_ofs_fallback=True,
            ),
            now=lambda: datetime(
                2026,
                10,
                5,
                4,
                0,
                0,
                tzinfo=timezone.utc,
            ),
        )

    def test_corp_code_seed_mapping_avoids_archive_request(self):
        transport = FakeDartTransport(
            filings=[],
            financial_payloads={},
        )
        resolver = DartCorpCodeResolver(
            api_key="x" * 40,
            transport=transport,
            seed_mapping={"005930": "00126380"},
        )
        self.assertEqual("00126380", resolver.resolve("005930"))
        self.assertEqual([], transport.calls)

    def test_corp_code_resolver_retries_invalid_zip(self):
        valid_transport = FakeDartTransport(
            filings=[],
            financial_payloads={},
        )

        class SequenceTransport:
            def __init__(self):
                self.calls = 0

            def get_bytes(self, endpoint, params):
                self.calls += 1
                if self.calls == 1:
                    return b'{"status":"020","message":"temporary"}'
                return valid_transport.get_bytes(endpoint, params)

            def get_json(self, endpoint, params):
                raise AssertionError(endpoint)

        transport = SequenceTransport()
        resolver = DartCorpCodeResolver(
            api_key="x" * 40,
            transport=transport,
            archive_max_attempts=2,
            archive_retry_backoff_seconds=0.0,
        )
        self.assertEqual("00126380", resolver.resolve("005930"))
        self.assertEqual(2, transport.calls)

    def test_corp_code_resolver_reports_final_dart_status(self):
        class BrokenTransport:
            def __init__(self):
                self.calls = 0

            def get_bytes(self, endpoint, params):
                self.calls += 1
                return b'{"status":"020","message":"request limit"}'

            def get_json(self, endpoint, params):
                raise AssertionError(endpoint)

        transport = BrokenTransport()
        resolver = DartCorpCodeResolver(
            api_key="x" * 40,
            transport=transport,
            archive_max_attempts=2,
            archive_retry_backoff_seconds=0.0,
        )
        with self.assertRaisesRegex(
            DartProviderError,
            "after 2 attempts status=020",
        ):
            resolver.resolve("005930")
        self.assertEqual(2, transport.calls)

    def test_corp_code_resolver_reads_official_zip_shape(self):
        transport = FakeDartTransport(
            filings=[],
            financial_payloads={},
        )
        resolver = DartCorpCodeResolver(
            api_key="x" * 40,
            transport=transport,
        )
        self.assertEqual("00126380", resolver.resolve("005930"))

    def test_seeded_corp_code_must_match_filing_stock_code(self):
        receipt = "20260315000123"
        transport = FakeDartTransport(
            filings=[
                filing(
                    receipt,
                    "사업보고서 (2025.12)",
                    "20260315",
                    stock_code="005930",
                )
            ],
            financial_payloads={},
        )
        provider = DartFundamentalObservationProvider(
            api_key="x" * 40,
            transport=transport,
            corp_code_overrides={"006400": "00126380"},
            now=lambda: datetime(
                2026,
                10,
                5,
                4,
                0,
                0,
                tzinfo=timezone.utc,
            ),
        )
        with self.assertRaisesRegex(
            DartProviderError,
            "does not match requested stock_code",
        ):
            provider.query(
                FundamentalQuery(
                    asset_id="KRX:006400",
                    as_of="2026-03-16T00:00:00+09:00",
                    fiscal_period_end_from="2025-12-31",
                    fiscal_period_end_to="2025-12-31",
                )
            )

    def test_current_report_becomes_pit_fundamental_observation(self):
        receipt = "20260315000123"
        transport = FakeDartTransport(
            filings=[
                filing(
                    receipt,
                    "사업보고서 (2025.12)",
                    "20260315",
                )
            ],
            financial_payloads={
                ("2025", "11011", "CFS"): financial_payload(
                    receipt,
                    amount="12,345",
                )
            },
        )
        provider = self._provider(transport)
        result = provider.query(
            FundamentalQuery(
                asset_id="KRX:005930",
                as_of="2026-03-16T00:00:00+09:00",
                fiscal_period_end_from="2025-12-31",
                fiscal_period_end_to="2025-12-31",
            )
        )
        self.assertEqual(1, len(result.observations))
        item = result.observations[0]
        self.assertEqual(
            "OPERATING_INCOME:IS:CURRENT_PERIOD",
            item["metric_key"],
        )
        self.assertEqual(12345.0, item["value"])
        self.assertEqual("2025-12-31", item["fiscal_period_end"])
        self.assertEqual("DATE", item["published_at_precision"])
        self.assertEqual(
            "2026-03-15T23:59:59+09:00",
            item["published_at"],
        )
        self.assertEqual("OPEN_DART", item["source_provider"])
        self.assertFalse(result.authority["execution_authorized"])
        self.assertFalse(result.provider["api_key_persisted"])

    def test_same_filing_date_before_end_of_day_is_conservatively_unavailable(self):
        receipt = "20260315000123"
        transport = FakeDartTransport(
            filings=[
                filing(
                    receipt,
                    "사업보고서 (2025.12)",
                    "20260315",
                )
            ],
            financial_payloads={
                ("2025", "11011", "CFS"): financial_payload(receipt)
            },
        )
        provider = self._provider(transport)
        result = provider.query(
            FundamentalQuery(
                asset_id="KRX:005930",
                as_of="2026-03-15T12:00:00+09:00",
                fiscal_period_end_from="2025-12-31",
                fiscal_period_end_to="2025-12-31",
            )
        )
        self.assertEqual(0, len(result.observations))

    def test_historical_query_fails_closed_when_latest_is_future_correction(self):
        original = "20260315000123"
        correction = "20260415000456"
        transport = FakeDartTransport(
            filings=[
                filing(
                    original,
                    "사업보고서 (2025.12)",
                    "20260315",
                ),
                filing(
                    correction,
                    "[기재정정]사업보고서 (2025.12)",
                    "20260415",
                ),
            ],
            financial_payloads={
                ("2025", "11011", "CFS"): financial_payload(
                    correction,
                    amount="8,000",
                )
            },
        )
        provider = self._provider(transport)
        with self.assertRaisesRegex(
            DartPointInTimeUnavailable,
            "XBRL-by-receipt",
        ):
            provider.query(
                FundamentalQuery(
                    asset_id="KRX:005930",
                    as_of="2026-03-20T00:00:00+09:00",
                    fiscal_period_end_from="2025-12-31",
                    fiscal_period_end_to="2025-12-31",
                )
            )

    def test_query_after_correction_uses_corrected_filing_and_revision_metadata(self):
        original = "20260315000123"
        correction = "20260415000456"
        transport = FakeDartTransport(
            filings=[
                filing(
                    original,
                    "사업보고서 (2025.12)",
                    "20260315",
                ),
                filing(
                    correction,
                    "[기재정정]사업보고서 (2025.12)",
                    "20260415",
                ),
            ],
            financial_payloads={
                ("2025", "11011", "CFS"): financial_payload(
                    correction,
                    amount="8,000",
                )
            },
        )
        provider = self._provider(transport)
        result = provider.query(
            FundamentalQuery(
                asset_id="KRX:005930",
                as_of="2026-04-16T00:00:00+09:00",
                fiscal_period_end_from="2025-12-31",
                fiscal_period_end_to="2025-12-31",
            )
        )
        item = result.observations[0]
        self.assertTrue(item["restated"])
        self.assertEqual(correction, item["revision_id"])
        self.assertEqual(original, item["revision_of"])
        self.assertEqual(8000.0, item["value"])

    def test_cfs_can_fall_back_to_ofs_when_explicitly_configured(self):
        receipt = "20260315000123"
        transport = FakeDartTransport(
            filings=[
                filing(
                    receipt,
                    "사업보고서 (2025.12)",
                    "20260315",
                )
            ],
            financial_payloads={
                ("2025", "11011", "OFS"): financial_payload(receipt)
            },
        )
        result = self._provider(transport).query(
            FundamentalQuery(
                asset_id="KRX:005930",
                as_of="2026-03-16T00:00:00+09:00",
                fiscal_period_end_from="2025-12-31",
                fiscal_period_end_to="2025-12-31",
            )
        )
        self.assertIn(":OFS:", result.observations[0]["observation_id"])
        self.assertIn(
            "DART:OFS:",
            result.observations[0]["normalization_method"],
        )

    def test_dimensional_duplicate_account_rows_are_preserved(self):
        receipt = "20260315000123"
        payload = financial_payload(
            receipt,
            amount="1,000",
            account_id="dart_ChangesInConsolidatedCompanies",
            account_nm="연결범위변동",
            statement_division="SCE",
            account_detail="Member A",
        )
        second = dict(payload["list"][0])
        second["account_detail"] = "Member B"
        second["thstrm_amount"] = "2,000"
        payload["list"].append(second)

        transport = FakeDartTransport(
            filings=[
                filing(
                    receipt,
                    "사업보고서 (2025.12)",
                    "20260315",
                )
            ],
            financial_payloads={
                ("2025", "11011", "CFS"): payload
            },
        )
        result = self._provider(transport).query(
            FundamentalQuery(
                asset_id="KRX:005930",
                as_of="2026-03-16T00:00:00+09:00",
                fiscal_period_end_from="2025-12-31",
                fiscal_period_end_to="2025-12-31",
            )
        )
        self.assertEqual(2, len(result.observations))
        keys = {item["metric_key"] for item in result.observations}
        self.assertEqual(2, len(keys))
        self.assertTrue(all(":DIM:" in key for key in keys))
        details = {
            item["dimension_detail"]
            for item in result.observations
        }
        self.assertEqual({"Member A", "Member B"}, details)

    def test_metric_filter_runs_after_dart_normalization(self):
        receipt = "20260315000123"
        transport = FakeDartTransport(
            filings=[
                filing(
                    receipt,
                    "사업보고서 (2025.12)",
                    "20260315",
                )
            ],
            financial_payloads={
                ("2025", "11011", "CFS"): financial_payload(receipt)
            },
        )
        provider = self._provider(transport)
        result = provider.query(
            FundamentalQuery(
                asset_id="KRX:005930",
                as_of="2026-03-16T00:00:00+09:00",
                metric_keys=("OPERATING_INCOME:IS:CURRENT_PERIOD",),
                fiscal_period_end_from="2025-12-31",
                fiscal_period_end_to="2025-12-31",
            )
        )
        self.assertEqual(1, len(result.observations))

    def test_unavailable_report_is_not_fabricated(self):
        transport = FakeDartTransport(
            filings=[],
            financial_payloads={},
        )
        provider = self._provider(transport)
        result = provider.query(
            FundamentalQuery(
                asset_id="KRX:005930",
                as_of="2026-03-01T00:00:00+09:00",
                fiscal_period_end_from="2025-12-31",
                fiscal_period_end_to="2025-12-31",
            )
        )
        self.assertEqual(0, len(result.observations))

    def test_api_error_fails_closed_without_exposing_key(self):
        class ErrorTransport(FakeDartTransport):
            def get_json(self, endpoint, params):
                if endpoint == "list.json":
                    return {
                        "status": "020",
                        "message": "요청 제한 초과",
                    }
                return super().get_json(endpoint, params)

        provider = self._provider(
            ErrorTransport(
                filings=[],
                financial_payloads={},
            )
        )
        with self.assertRaises(DartApiError) as ctx:
            provider.query(
                FundamentalQuery(
                    asset_id="KRX:005930",
                    as_of="2026-03-01T00:00:00+09:00",
                    fiscal_period_end_from="2025-12-31",
                    fiscal_period_end_to="2025-12-31",
                )
            )
        self.assertNotIn("x" * 40, str(ctx.exception))

    def test_query_requires_explicit_fiscal_bounds(self):
        transport = FakeDartTransport(
            filings=[],
            financial_payloads={},
        )
        provider = self._provider(transport)
        with self.assertRaisesRegex(
            DartProviderError,
            "requires fiscal_period_end_from",
        ):
            provider.query(
                FundamentalQuery(
                    asset_id="KRX:005930",
                    as_of="2026-03-01T00:00:00+09:00",
                )
            )

    def test_provider_rejects_non_krx_asset_id(self):
        transport = FakeDartTransport(
            filings=[],
            financial_payloads={},
        )
        provider = self._provider(transport)
        with self.assertRaisesRegex(
            DartProviderError,
            "KRX:<6-digit-code>",
        ):
            provider.query(
                FundamentalQuery(
                    asset_id="NASDAQ:AAPL",
                    as_of="2026-03-01T00:00:00+09:00",
                    fiscal_period_end_from="2025-01-01",
                    fiscal_period_end_to="2025-12-31",
                )
            )

    def test_amount_parentheses_are_parsed_as_negative(self):
        receipt = "20260315000123"
        transport = FakeDartTransport(
            filings=[
                filing(
                    receipt,
                    "사업보고서 (2025.12)",
                    "20260315",
                )
            ],
            financial_payloads={
                ("2025", "11011", "CFS"): financial_payload(
                    receipt,
                    amount="(1,234)",
                )
            },
        )
        result = self._provider(transport).query(
            FundamentalQuery(
                asset_id="KRX:005930",
                as_of="2026-03-16T00:00:00+09:00",
                fiscal_period_end_from="2025-12-31",
                fiscal_period_end_to="2025-12-31",
            )
        )
        self.assertEqual(-1234.0, result.observations[0]["value"])


if __name__ == "__main__":
    unittest.main()
