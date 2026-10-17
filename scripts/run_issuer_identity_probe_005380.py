"""Verify Hyundai Motor's candidate Open DART corp_code without economic data.

The candidate identifier was discovered from a public implementation that
reports a prior real-OpenDART lookup. This probe does not trust that claim as
authority. It calls official Open DART disclosure-list metadata and promotes the
mapping only if returned filings agree on both corp_code and stock_code.

No financial statement amounts are requested.
"""
from __future__ import annotations

import json
from pathlib import Path

from quantrade.capabilities.dart_fundamental_provider import (
    UrlLibDartTransport,
)


ASSET_ID = "KRX:005380"
STOCK_CODE = "005380"
CANDIDATE_CORP_CODE = "00164742"
DISCOVERY_SOURCE = (
    "github:Team-Delgo/korea-stock-mcp/README.md"
)
RESULT_PATH = Path(
    "research/diagnostics/ISSUER_ID_005380_VERIFICATION.json"
)


def run() -> dict:
    transport = UrlLibDartTransport(
        max_attempts=4,
        retry_backoff_seconds=1.0,
    )
    payload = transport.get_json(
        "list.json",
        {
            "corp_code": CANDIDATE_CORP_CODE,
            "bgn_de": "20260801",
            "end_de": "20261005",
            "last_reprt_at": "N",
            "sort": "date",
            "sort_mth": "desc",
            "page_no": 1,
            "page_count": 100,
        },
    )
    status = str(payload.get("status", "")).strip()
    if status != "000":
        raise RuntimeError(
            "Open DART list verification failed "
            f"status={status or 'MISSING'} "
            f"message={str(payload.get('message', '')).strip()}"
        )

    rows = payload.get("list", [])
    if not isinstance(rows, list) or not rows:
        raise RuntimeError(
            "Open DART list verification returned no filings"
        )

    observed_pairs = sorted(
        {
            (
                str(row.get("stock_code", "")).strip(),
                str(row.get("corp_code", "")).strip(),
            )
            for row in rows
            if isinstance(row, dict)
        }
    )
    nonempty_stock_codes = sorted(
        {
            stock
            for stock, _ in observed_pairs
            if stock
        }
    )
    corp_codes = sorted(
        {
            corp
            for _, corp in observed_pairs
            if corp
        }
    )

    if nonempty_stock_codes != [STOCK_CODE]:
        raise RuntimeError(
            "candidate corp_code returned unexpected stock codes: "
            + ",".join(nonempty_stock_codes)
        )
    if corp_codes != [CANDIDATE_CORP_CODE]:
        raise RuntimeError(
            "candidate corp_code returned inconsistent corp codes: "
            + ",".join(corp_codes)
        )

    receipts = []
    for row in rows[:10]:
        if not isinstance(row, dict):
            continue
        receipts.append(
            {
                "rcept_no": str(row.get("rcept_no", "")).strip(),
                "rcept_dt": str(row.get("rcept_dt", "")).strip(),
                "report_nm": str(row.get("report_nm", "")).strip(),
                "stock_code": str(
                    row.get("stock_code", "")
                ).strip(),
                "corp_code": str(row.get("corp_code", "")).strip(),
            }
        )

    result = {
        "schema": "quantrade_issuer_identity_probe_v1",
        "asset_id": ASSET_ID,
        "stock_code": STOCK_CODE,
        "candidate_external_id": CANDIDATE_CORP_CODE,
        "provider_id": "OPEN_DART",
        "discovery_source": DISCOVERY_SOURCE,
        "verification_source": "OPEN_DART:list.json",
        "verification_window": {
            "begin": "2026-08-01",
            "end": "2026-10-05",
        },
        "status": "VERIFIED",
        "filing_count": len(rows),
        "observed_stock_codes": nonempty_stock_codes,
        "observed_corp_codes": corp_codes,
        "sample_filings": receipts,
        "economic_values_requested": False,
        "authority": {
            "canonical_evidence_created": False,
            "valuation_created": False,
            "portfolio_proposal_created": False,
            "execution_authorized": False,
            "live_order_possible": False,
        },
    }
    RESULT_PATH.parent.mkdir(parents=True, exist_ok=True)
    RESULT_PATH.write_text(
        json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    return result


def main() -> None:
    result = run()
    print(
        json.dumps(
            {
                "asset_id": result["asset_id"],
                "stock_code": result["stock_code"],
                "corp_code": result["candidate_external_id"],
                "status": result["status"],
                "filing_count": result["filing_count"],
                "economic_values_requested": result[
                    "economic_values_requested"
                ],
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
