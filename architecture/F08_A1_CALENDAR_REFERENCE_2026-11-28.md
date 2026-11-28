# A1 reference calendar / publication gate — 2026-11-28

Status: bounded source-reviewed reference only; not an actual session attestation, not full-year production calendar, not provider authorization. Existing MANUAL comparator remains fail-closed. No deployment or actual provider call.

## Sources reviewed
- NYSE official holidays and hours: https://www.nyse.com/trade/hours-calendars — Nov 26 Thanksgiving closure; Nov 27 13:00 ET early close.
- Nasdaq official US equity schedule: https://www.nasdaq.com/market-activity/stock-market-holiday-schedule — same holiday and early close.
- Massive Basic plan date eligibility: https://massive.com/knowledge-base/article/on-the-free-basic-plan-when-can-i-pull-the-previous-trading-days-data — daily ticker summary becomes requestable after the next midnight ET. This does not guarantee the row is available or final.
- Massive raw daily ticker summary: https://massive.com/docs/rest/stocks/aggregates/daily-ticker-summary?assetClass=stocks&license=personal&name=stocks_basic — regular close distinct from extended hours.
- KRX regular market rules: https://global.krx.co.kr/contents/GLB/06/0602/0602010201/GLB0602010201T1.jsp — general rules include exchange-designated exceptions. A complete authoritative date/exception schedule and publication/finality evidence are not established, so KRX is not enabled in the reference module.

## Design
Reference coverage 2026-11-23 through 2026-12-04 ET, XNYS/XNAS only. Ordinary days are scheduled, not actual closes. Use IANA timezone and bounded dates. Thanksgiving 2026-11-26 closed, 2026-11-27 13:00 ET close (18:00 UTC, 03:00 KST next day). Basic plan eligibility at 2026-11-28 00:00 ET (14:00 KST). Between close and eligibility, latest expected session remains Nov 27 and state PUBLICATION_WINDOW_PENDING; never use Nov 25 as a current decision substitute. At eligibility state PLAN_ELIGIBLE_UNVERIFIED. Reference input mismatch is flagged. Outside coverage / KRX / naive datetime fails closed. DST tests verify conversion only, not a full annual schedule.

## Required before integration
Actual exchange exceptions and session evidence (including emergency halts, corrections and special hours); KRX dated authoritative schedule; trusted server as_of; provider response observation and first-known timestamps; independent permitted price parity; identity/raw share basis/corporate actions; finality and revision policy; rights/retention/private display; authenticated approval/revocation. Reference calendar alone cannot enable REVIEW or WAIT. No actual quote prices, no credentials, no trades. Next: verify recent session with lawful independent source in private probe after rights confirmation; no raw restricted data in public repo or CI.
