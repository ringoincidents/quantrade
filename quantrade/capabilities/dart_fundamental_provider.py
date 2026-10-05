"""Open DART adapter for QuanTrade point-in-time fundamental evidence.

The adapter is a network/data boundary only. It does not create canonical
Evidence, a Thesis, Portfolio Proposal, Risk Opinion, Committee Decision, or
execution authority.

Security:
- the API key is supplied explicitly or read from OPEN_DART_API_KEY;
- the key is never persisted in artifacts or provider metadata;
- stdlib urllib is used so QuanTrade does not need a new runtime dependency.

Point-in-time rule:
Open DART's full-financial-statement endpoint is keyed by company/year/report
code and returns a filing receipt number. QuanTrade resolves that receipt
against the disclosure-search endpoint to recover the filing date. Because the
financial endpoint may expose a later corrected filing instead of the original
historical filing, a historical query fails closed when an earlier filing was
available by the Case as-of date but the returned financial data belongs to a
later correction. A future XBRL-by-receipt parser can close that gap.
"""
from __future__ import annotations

import calendar
from dataclasses import dataclass, replace
from datetime import date, datetime, timedelta, timezone
import io
import json
import os
import re
from typing import Callable, Iterable, Protocol
from urllib.parse import urlencode
from urllib.request import Request, urlopen
import xml.etree.ElementTree as ET
import zipfile

from quantrade.capabilities.fundamental_evidence import (
    FundamentalEvidenceError,
    FundamentalObservation,
    FundamentalProviderMetadata,
    FundamentalQuery,
    FundamentalQueryResult,
    StaticFundamentalObservationProvider,
)


DART_BASE_URL = "https://opendart.fss.or.kr/api"
DART_API_KEY_ENV = "OPEN_DART_API_KEY"
KST = timezone(timedelta(hours=9))

REPORT_CODES = {
    "11013": "FIRST_QUARTER",
    "11012": "HALF_YEAR",
    "11014": "THIRD_QUARTER",
    "11011": "ANNUAL",
}

CORE_ACCOUNT_MAP = {
    "ifrs-full_Assets": "TOTAL_ASSETS",
    "ifrs-full_Liabilities": "TOTAL_LIABILITIES",
    "ifrs-full_Equity": "TOTAL_EQUITY",
    "ifrs-full_Revenue": "REVENUE",
    "ifrs-full_ProfitLoss": "NET_INCOME",
    "dart_OperatingIncomeLoss": "OPERATING_INCOME",
}

CORRECTION_PREFIXES = (
    "[기재정정]",
    "[첨부정정]",
    "[첨부추가]",
    "[변경등록]",
    "[연장결정]",
    "[발행조건확정]",
    "[정정명령부과]",
    "[정정제출요구]",
)


class DartProviderError(FundamentalEvidenceError):
    """Base error for Open DART provider failures."""


class DartApiError(DartProviderError):
    """Raised when Open DART returns a non-success status."""


class DartPointInTimeUnavailable(DartProviderError):
    """Raised when current DART data cannot reconstruct a historical filing."""


class DartTransport(Protocol):
    def get_json(self, endpoint: str, params: dict[str, object]) -> dict:
        ...

    def get_bytes(self, endpoint: str, params: dict[str, object]) -> bytes:
        ...


class UrlLibDartTransport:
    """Minimal stdlib HTTPS transport."""

    def __init__(
        self,
        *,
        base_url: str = DART_BASE_URL,
        timeout_seconds: float = 20.0,
        user_agent: str = "QuanTrade/1.0 OpenDART",
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self.user_agent = user_agent

    def _request(self, endpoint: str, params: dict[str, object]) -> bytes:
        query = urlencode(
            {
                key: str(value)
                for key, value in params.items()
                if value is not None
            }
        )
        url = f"{self.base_url}/{endpoint.lstrip('/')}?{query}"
        request = Request(
            url,
            headers={
                "User-Agent": self.user_agent,
                "Accept": "application/json, application/xml, */*",
            },
        )
        with urlopen(request, timeout=self.timeout_seconds) as response:
            return response.read()

    def get_json(self, endpoint: str, params: dict[str, object]) -> dict:
        payload = self._request(endpoint, params)
        try:
            decoded = json.loads(payload.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise DartProviderError(
                f"Open DART returned invalid JSON for {endpoint}"
            ) from exc
        if not isinstance(decoded, dict):
            raise DartProviderError(
                f"Open DART JSON root must be an object for {endpoint}"
            )
        return decoded

    def get_bytes(self, endpoint: str, params: dict[str, object]) -> bytes:
        return self._request(endpoint, params)


@dataclass(frozen=True)
class DartFiling:
    rcept_no: str
    corp_code: str
    stock_code: str
    report_nm: str
    rcept_dt: str
    note: str


@dataclass(frozen=True)
class DartProviderConfig:
    statement_scope: str = "CFS"
    allow_ofs_fallback: bool = True
    max_list_pages: int = 50
    page_count: int = 100


def _required_text(value: object, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise DartProviderError(f"{field_name} is required")
    return value.strip()


def _api_key(explicit_key: str | None) -> str:
    value = explicit_key if explicit_key is not None else os.getenv(DART_API_KEY_ENV)
    if not isinstance(value, str) or not value.strip():
        raise DartProviderError(
            f"Open DART API key is required via {DART_API_KEY_ENV}"
        )
    return value.strip()


def _dart_status(payload: dict, endpoint: str, *, no_data_ok: bool = False) -> bool:
    status = str(payload.get("status", "")).strip()
    if status == "000":
        return True
    if status == "013" and no_data_ok:
        return False
    message = str(payload.get("message", "")).strip()
    raise DartApiError(
        f"Open DART {endpoint} failed with status={status or 'MISSING'}"
        + (f" message={message}" if message else "")
    )


def _normalize_report_name(report_nm: str) -> str:
    value = _required_text(report_nm, "report_nm")
    changed = True
    while changed:
        changed = False
        for prefix in CORRECTION_PREFIXES:
            if value.startswith(prefix):
                value = value[len(prefix):].strip()
                changed = True
    return re.sub(r"\s+", "", value)


def _is_correction_report(report_nm: str) -> bool:
    compact = report_nm.strip()
    return any(compact.startswith(prefix) for prefix in CORRECTION_PREFIXES)


def _dart_date_to_timestamp(date_text: str) -> str:
    raw = _required_text(date_text, "rcept_dt")
    try:
        parsed = datetime.strptime(raw, "%Y%m%d").date()
    except ValueError as exc:
        raise DartProviderError("rcept_dt must be YYYYMMDD") from exc
    # list.json exposes filing date, not an intraday timestamp. End-of-day KST
    # is conservative: a filing is never assumed usable before its reported day
    # has finished.
    return datetime(
        parsed.year,
        parsed.month,
        parsed.day,
        23,
        59,
        59,
        tzinfo=KST,
    ).isoformat()


def _parse_as_of(value: str) -> datetime:
    raw = _required_text(value, "as_of").replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(raw)
    except ValueError as exc:
        raise DartProviderError("as_of must be valid ISO-8601") from exc
    if parsed.tzinfo is None:
        raise DartProviderError("as_of must include timezone information")
    return parsed.astimezone(KST)


def _date_text(value: date) -> str:
    return value.strftime("%Y%m%d")


def _period_from_report_name(report_nm: str) -> str:
    matches = re.findall(r"\((\d{4})[.\-/](\d{1,2})\)", report_nm)
    if not matches:
        raise DartProviderError(
            f"cannot derive fiscal period from report name: {report_nm}"
        )
    year_text, month_text = matches[-1]
    year = int(year_text)
    month = int(month_text)
    if month < 1 or month > 12:
        raise DartProviderError("report fiscal month is invalid")
    last_day = calendar.monthrange(year, month)[1]
    return date(year, month, last_day).isoformat()


def _parse_amount(value: object) -> float | None:
    if value is None:
        return None
    raw = str(value).strip()
    if not raw or raw in {"-", "N/A"}:
        return None
    normalized = raw.replace(",", "").replace(" ", "")
    if normalized.startswith("(") and normalized.endswith(")"):
        normalized = f"-{normalized[1:-1]}"
    try:
        return float(normalized)
    except ValueError as exc:
        raise DartProviderError(f"invalid DART amount: {raw}") from exc


def _metric_base(account_id: str, account_nm: str) -> str:
    if account_id in CORE_ACCOUNT_MAP:
        return CORE_ACCOUNT_MAP[account_id]
    cleaned = account_id.strip()
    if cleaned and cleaned != "-표준계정코드 미사용-":
        return f"DART_ACCOUNT:{cleaned}"
    fallback = re.sub(r"\s+", "_", account_nm.strip())
    if not fallback:
        raise DartProviderError("financial row lacks account identifier/name")
    return f"DART_ACCOUNT_NAME:{fallback}"


def _report_is_same_family(left: DartFiling, right: DartFiling) -> bool:
    return _normalize_report_name(left.report_nm) == _normalize_report_name(
        right.report_nm
    )


class DartCorpCodeResolver:
    """Resolve KRX stock code to Open DART corp_code from corpCode.xml."""

    def __init__(
        self,
        *,
        api_key: str | None = None,
        transport: DartTransport | None = None,
    ) -> None:
        self._key = _api_key(api_key)
        self._transport = transport or UrlLibDartTransport()
        self._by_stock: dict[str, str] | None = None

    def _load(self) -> dict[str, str]:
        payload = self._transport.get_bytes(
            "corpCode.xml",
            {"crtfc_key": self._key},
        )
        try:
            with zipfile.ZipFile(io.BytesIO(payload)) as archive:
                names = archive.namelist()
                if not names:
                    raise DartProviderError(
                        "Open DART corpCode archive is empty"
                    )
                xml_bytes = archive.read(names[0])
        except (zipfile.BadZipFile, KeyError) as exc:
            raise DartProviderError(
                "Open DART corpCode response is not a valid zip"
            ) from exc

        try:
            root = ET.fromstring(xml_bytes)
        except ET.ParseError as exc:
            raise DartProviderError(
                "Open DART corpCode XML is invalid"
            ) from exc

        mapping: dict[str, str] = {}
        for node in root.findall(".//list"):
            stock_code = (node.findtext("stock_code") or "").strip()
            corp_code = (node.findtext("corp_code") or "").strip()
            if stock_code and corp_code:
                if stock_code in mapping and mapping[stock_code] != corp_code:
                    raise DartProviderError(
                        f"duplicate stock_code mapping: {stock_code}"
                    )
                mapping[stock_code] = corp_code
        if not mapping:
            raise DartProviderError(
                "Open DART corpCode response contained no listed companies"
            )
        return mapping

    def resolve(self, stock_code: str) -> str:
        code = _required_text(stock_code, "stock_code")
        if not re.fullmatch(r"\d{6}", code):
            raise DartProviderError(
                "stock_code must be a six-digit KRX code"
            )
        if self._by_stock is None:
            self._by_stock = self._load()
        try:
            return self._by_stock[code]
        except KeyError as exc:
            raise DartProviderError(
                f"stock_code not found in Open DART corpCode: {code}"
            ) from exc


class DartFundamentalObservationProvider:
    """Network-backed Open DART FundamentalObservationProvider.

    For deterministic historical replay, callers must provide both fiscal
    period bounds. Current and historical queries use the same PIT gate.
    """

    def __init__(
        self,
        *,
        api_key: str | None = None,
        transport: DartTransport | None = None,
        config: DartProviderConfig | None = None,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        self._key = _api_key(api_key)
        self._transport = transport or UrlLibDartTransport()
        self._config = config or DartProviderConfig()
        if self._config.statement_scope not in {"CFS", "OFS"}:
            raise DartProviderError(
                "statement_scope must be CFS or OFS"
            )
        if self._config.page_count < 1 or self._config.page_count > 100:
            raise DartProviderError("page_count must be between 1 and 100")
        if self._config.max_list_pages < 1:
            raise DartProviderError("max_list_pages must be positive")
        self._now = now or (lambda: datetime.now(timezone.utc))
        self._resolver = DartCorpCodeResolver(
            api_key=self._key,
            transport=self._transport,
        )

    @property
    def metadata(self) -> FundamentalProviderMetadata:
        return FundamentalProviderMetadata(
            provider_id="OPEN_DART",
            provider_version="fnlttSinglAcntAll+list+corpCode:v1",
            source_license="Open DART public API; verify source filing",
            network_required=True,
            model_required=False,
            point_in_time_capable=True,
            capital_authority=False,
        )

    def _list_filings(
        self,
        corp_code: str,
        *,
        begin: date,
        end: date,
    ) -> tuple[DartFiling, ...]:
        page = 1
        filings: list[DartFiling] = []
        while page <= self._config.max_list_pages:
            payload = self._transport.get_json(
                "list.json",
                {
                    "crtfc_key": self._key,
                    "corp_code": corp_code,
                    "bgn_de": _date_text(begin),
                    "end_de": _date_text(end),
                    "last_reprt_at": "N",
                    "pblntf_ty": "A",
                    "sort": "date",
                    "sort_mth": "asc",
                    "page_no": page,
                    "page_count": self._config.page_count,
                },
            )
            has_data = _dart_status(
                payload,
                "list.json",
                no_data_ok=True,
            )
            if not has_data:
                return tuple(filings)

            rows = payload.get("list", [])
            if not isinstance(rows, list):
                raise DartProviderError(
                    "Open DART list.json list must be an array"
                )
            for row in rows:
                if not isinstance(row, dict):
                    raise DartProviderError(
                        "Open DART filing row must be an object"
                    )
                filings.append(
                    DartFiling(
                        rcept_no=_required_text(
                            row.get("rcept_no"),
                            "rcept_no",
                        ),
                        corp_code=_required_text(
                            row.get("corp_code"),
                            "corp_code",
                        ),
                        stock_code=str(row.get("stock_code", "")).strip(),
                        report_nm=_required_text(
                            row.get("report_nm"),
                            "report_nm",
                        ),
                        rcept_dt=_required_text(
                            row.get("rcept_dt"),
                            "rcept_dt",
                        ),
                        note=str(row.get("rm", "")).strip(),
                    )
                )

            total_page = int(payload.get("total_page") or 1)
            if page >= total_page:
                break
            page += 1
        else:
            raise DartProviderError(
                "Open DART disclosure pagination exceeded configured limit"
            )
        return tuple(filings)

    def _financial_rows(
        self,
        corp_code: str,
        *,
        business_year: int,
        report_code: str,
        scope: str,
    ) -> tuple[dict, ...]:
        payload = self._transport.get_json(
            "fnlttSinglAcntAll.json",
            {
                "crtfc_key": self._key,
                "corp_code": corp_code,
                "bsns_year": business_year,
                "reprt_code": report_code,
                "fs_div": scope,
            },
        )
        has_data = _dart_status(
            payload,
            "fnlttSinglAcntAll.json",
            no_data_ok=True,
        )
        if not has_data:
            return ()
        rows = payload.get("list", [])
        if not isinstance(rows, list):
            raise DartProviderError(
                "Open DART financial list must be an array"
            )
        return tuple(
            row for row in rows if isinstance(row, dict)
        )

    def _fetch_report_rows(
        self,
        corp_code: str,
        *,
        business_year: int,
        report_code: str,
    ) -> tuple[str, tuple[dict, ...]]:
        primary = self._config.statement_scope
        rows = self._financial_rows(
            corp_code,
            business_year=business_year,
            report_code=report_code,
            scope=primary,
        )
        if rows:
            return primary, rows
        if (
            primary == "CFS"
            and self._config.allow_ofs_fallback
        ):
            fallback = self._financial_rows(
                corp_code,
                business_year=business_year,
                report_code=report_code,
                scope="OFS",
            )
            if fallback:
                return "OFS", fallback
        return primary, ()

    def _rows_to_observations(
        self,
        rows: tuple[dict, ...],
        *,
        filing: DartFiling,
        fiscal_period_end: str,
        scope: str,
        retrieved_at: str,
        prior_filing: DartFiling | None,
    ) -> tuple[FundamentalObservation, ...]:
        result: list[FundamentalObservation] = []
        seen_ids: set[str] = set()
        for row in rows:
            rcept_no = _required_text(row.get("rcept_no"), "rcept_no")
            if rcept_no != filing.rcept_no:
                raise DartProviderError(
                    "financial rows contain multiple/mismatched receipt numbers"
                )
            account_id = str(row.get("account_id", "")).strip()
            account_nm = str(row.get("account_nm", "")).strip()
            base = _metric_base(account_id, account_nm)
            currency = str(row.get("currency", "")).strip() or None

            amount_fields = (
                ("thstrm_amount", "CURRENT_PERIOD"),
                ("thstrm_add_amount", "CURRENT_YTD"),
            )
            for field_name, suffix in amount_fields:
                amount = _parse_amount(row.get(field_name))
                if amount is None:
                    continue
                observation_id = (
                    f"DART:{rcept_no}:{scope}:{base}:{suffix}"
                )
                if observation_id in seen_ids:
                    # DART can expose dimension/member rows with the same
                    # standard account ID. Preserve only unambiguous rows in
                    # this first provider slice; force later normalization work
                    # instead of silently summing or picking one.
                    raise DartProviderError(
                        f"ambiguous duplicate financial metric: "
                        f"{observation_id}"
                    )
                seen_ids.add(observation_id)
                source_ref = (
                    "https://dart.fss.or.kr/dsaf001/main.do"
                    f"?rcpNo={rcept_no}"
                )
                evidence_ref = (
                    f"{source_ref}#account={account_id or account_nm}"
                    f"&field={field_name}&scope={scope}"
                )
                result.append(
                    FundamentalObservation(
                        observation_id=observation_id,
                        asset_id=f"KRX:{filing.stock_code}",
                        metric_key=f"{base}:{suffix}",
                        value=amount,
                        unit=currency or "REPORTED_UNIT",
                        currency=currency,
                        fiscal_period_end=fiscal_period_end,
                        published_at=_dart_date_to_timestamp(
                            filing.rcept_dt
                        ),
                        retrieved_at=retrieved_at,
                        source_provider="OPEN_DART",
                        source_document_id=rcept_no,
                        source_ref=source_ref,
                        evidence_ref=evidence_ref,
                        revision_id=(
                            rcept_no
                            if _is_correction_report(filing.report_nm)
                            else None
                        ),
                        revision_of=(
                            prior_filing.rcept_no
                            if prior_filing is not None
                            else None
                        ),
                        restated=_is_correction_report(
                            filing.report_nm
                        ),
                        normalization_method=(
                            f"DART:{scope}:{account_id or account_nm}:"
                            f"{field_name}"
                        ),
                        published_at_precision="DATE",
                    )
                )
        return tuple(result)

    def query(self, request: FundamentalQuery) -> FundamentalQueryResult:
        asset_id = _required_text(request.asset_id, "asset_id")
        match = re.fullmatch(r"KRX:(\d{6})", asset_id)
        if not match:
            raise DartProviderError(
                "Open DART provider requires asset_id KRX:<6-digit-code>"
            )
        if (
            request.fiscal_period_end_from is None
            or request.fiscal_period_end_to is None
        ):
            raise DartProviderError(
                "Open DART query requires fiscal_period_end_from and "
                "fiscal_period_end_to"
            )

        try:
            lower = date.fromisoformat(request.fiscal_period_end_from)
            upper = date.fromisoformat(request.fiscal_period_end_to)
        except ValueError as exc:
            raise DartProviderError(
                "fiscal period bounds must be YYYY-MM-DD"
            ) from exc
        if lower > upper:
            raise DartProviderError("fiscal period range is reversed")

        as_of = _parse_as_of(request.as_of)
        retrieved = self._now()
        if retrieved.tzinfo is None:
            raise DartProviderError(
                "provider clock must return timezone-aware datetime"
            )
        retrieved = retrieved.astimezone(timezone.utc)
        if as_of.astimezone(timezone.utc) > retrieved:
            raise DartProviderError(
                "as_of cannot be after provider retrieval time"
            )
        retrieved_at = retrieved.isoformat()

        stock_code = match.group(1)
        corp_code = self._resolver.resolve(stock_code)

        # Annual reports for a fiscal period may be filed in the following
        # calendar year, so begin one year before the lower period and search
        # through retrieval date. Keeping corrections in the list is necessary
        # for PIT detection.
        filing_begin = date(max(2015, lower.year - 1), 1, 1)
        filing_end = retrieved.astimezone(KST).date()
        filings = self._list_filings(
            corp_code,
            begin=filing_begin,
            end=filing_end,
        )
        filing_by_receipt = {
            filing.rcept_no: filing
            for filing in filings
        }

        collected: list[FundamentalObservation] = []
        for business_year in range(lower.year, upper.year + 1):
            for report_code in REPORT_CODES:
                scope, rows = self._fetch_report_rows(
                    corp_code,
                    business_year=business_year,
                    report_code=report_code,
                )
                if not rows:
                    continue
                receipt_ids = {
                    _required_text(row.get("rcept_no"), "rcept_no")
                    for row in rows
                }
                if len(receipt_ids) != 1:
                    raise DartProviderError(
                        "financial endpoint returned multiple receipt numbers"
                    )
                receipt = next(iter(receipt_ids))
                if receipt not in filing_by_receipt:
                    raise DartProviderError(
                        f"financial receipt {receipt} was not found in "
                        "disclosure search"
                    )
                filing = filing_by_receipt[receipt]
                fiscal_period_end = _period_from_report_name(
                    filing.report_nm
                )
                fiscal_date = date.fromisoformat(fiscal_period_end)
                if fiscal_date < lower or fiscal_date > upper:
                    continue

                publication = datetime.fromisoformat(
                    _dart_date_to_timestamp(filing.rcept_dt)
                ).astimezone(timezone.utc)

                same_family = sorted(
                    (
                        candidate
                        for candidate in filings
                        if candidate.rcept_no != filing.rcept_no
                        and _report_is_same_family(candidate, filing)
                    ),
                    key=lambda item: (
                        item.rcept_dt,
                        item.rcept_no,
                    ),
                )
                prior = (
                    max(
                        (
                            candidate
                            for candidate in same_family
                            if candidate.rcept_dt < filing.rcept_dt
                        ),
                        key=lambda item: (
                            item.rcept_dt,
                            item.rcept_no,
                        ),
                        default=None,
                    )
                )

                if publication > as_of.astimezone(timezone.utc):
                    earlier_available = [
                        candidate
                        for candidate in same_family
                        if datetime.fromisoformat(
                            _dart_date_to_timestamp(
                                candidate.rcept_dt
                            )
                        ).astimezone(timezone.utc)
                        <= as_of.astimezone(timezone.utc)
                    ]
                    if earlier_available:
                        raise DartPointInTimeUnavailable(
                            "Open DART full-financial endpoint exposes a "
                            "later corrected filing while an earlier filing "
                            "was available at the requested as_of. Exact "
                            "historical reconstruction requires XBRL-by-"
                            "receipt parsing before this Case can proceed."
                        )
                    continue

                collected.extend(
                    self._rows_to_observations(
                        rows,
                        filing=filing,
                        fiscal_period_end=fiscal_period_end,
                        scope=scope,
                        retrieved_at=retrieved_at,
                        prior_filing=prior,
                    )
                )

        # Reuse the generic deterministic PIT/revision/filter logic, but keep
        # Open DART provider metadata instead of fixture metadata.
        static = StaticFundamentalObservationProvider(
            collected,
            metadata=self.metadata,
        )
        result = static.query(request)
        return replace(
            result,
            provider={
                **result.provider,
                "corp_code": corp_code,
                "stock_code": stock_code,
                "api_key_persisted": False,
                "publication_time_precision": "DATE_CONSERVATIVE_EOD_KST",
                "historical_correction_policy": (
                    "FAIL_CLOSED_UNTIL_XBRL_BY_RECEIPT"
                ),
            },
        )
