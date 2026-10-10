"""Read-only Open DART schema probe for QT-CASE-003 portability failure.

The probe reports account identity / statement placement only. It intentionally
does not emit financial amounts and has no investment authority.
"""
from __future__ import annotations

import json
import os

from quantrade.capabilities.dart_fundamental_provider import (
    UrlLibDartTransport,
)


CORP_CODE = "00126362"
STOCK_CODE = "006400"

TARGET_ACCOUNT_IDS = {
    "ifrs-full_BasicEarningsLossPerShare",
    "ifrs-full_ProfitLossAttributableToOwnersOfParent",
    "ifrs-full_CashFlowsFromUsedInOperatingActivities",
    "ifrs-full_PurchaseOfPropertyPlantAndEquipmentClassifiedAsInvestingActivities",
    "ifrs-full_PurchaseOfIntangibleAssetsClassifiedAsInvestingActivities",
    "ifrs-full_EquityAttributableToOwnersOfParent",
}

NAME_HINTS = (
    "주당",
    "지배기업",
    "영업활동",
    "유형자산",
    "무형자산",
)


def _key() -> str:
    value = os.getenv("OPEN_DART_API_KEY", "").strip()
    if not value:
        raise RuntimeError("OPEN_DART_API_KEY is required")
    return value


def probe_report(
    transport: UrlLibDartTransport,
    *,
    year: str,
    report_code: str,
) -> dict:
    payload = transport.get_json(
        "fnlttSinglAcntAll.json",
        {
            "crtfc_key": _key(),
            "corp_code": CORP_CODE,
            "bsns_year": year,
            "reprt_code": report_code,
            "fs_div": "CFS",
        },
    )
    status = str(payload.get("status", "")).strip()
    if status != "000":
        return {
            "year": year,
            "report_code": report_code,
            "status": status,
            "message": str(payload.get("message", "")).strip(),
            "matches": [],
        }

    rows = payload.get("list", [])
    matches = []
    seen = set()
    for row in rows:
        if not isinstance(row, dict):
            continue
        account_id = str(row.get("account_id", "")).strip()
        account_nm = str(row.get("account_nm", "")).strip()
        if (
            account_id not in TARGET_ACCOUNT_IDS
            and not any(hint in account_nm for hint in NAME_HINTS)
        ):
            continue
        identity = (
            account_id,
            account_nm,
            str(row.get("sj_div", "")).strip(),
            str(row.get("account_detail", "")).strip(),
        )
        if identity in seen:
            continue
        seen.add(identity)
        matches.append(
            {
                "account_id": account_id,
                "account_nm": account_nm,
                "sj_div": str(row.get("sj_div", "")).strip(),
                "sj_nm": str(row.get("sj_nm", "")).strip(),
                "account_detail": str(
                    row.get("account_detail", "")
                ).strip(),
                "has_current_period": bool(
                    str(row.get("thstrm_amount", "")).strip()
                ),
                "has_current_ytd": bool(
                    str(row.get("thstrm_add_amount", "")).strip()
                ),
            }
        )

    matches.sort(
        key=lambda row: (
            row["account_id"],
            row["sj_div"],
            row["account_nm"],
            row["account_detail"],
        )
    )
    return {
        "year": year,
        "report_code": report_code,
        "status": status,
        "match_count": len(matches),
        "matches": matches,
    }


def main() -> None:
    transport = UrlLibDartTransport()
    result = {
        "schema": "quantrade_dart_metric_schema_probe_v1",
        "asset_id": f"KRX:{STOCK_CODE}",
        "corp_code": CORP_CODE,
        "amounts_emitted": False,
        "reports": [
            probe_report(
                transport,
                year="2025",
                report_code="11011",
            ),
            probe_report(
                transport,
                year="2025",
                report_code="11012",
            ),
            probe_report(
                transport,
                year="2026",
                report_code="11012",
            ),
        ],
        "authority": {
            "model_called": False,
            "canonical_evidence_created": False,
            "valuation_created": False,
            "portfolio_proposal_created": False,
            "execution_authorized": False,
        },
    }
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
