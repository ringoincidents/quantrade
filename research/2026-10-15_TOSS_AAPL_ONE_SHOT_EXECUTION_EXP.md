# 2026-10-15 — One-time US fractional sell execution experiment

- Status: PROPOSED LIVE PATH; **NO BROKER ORDER EVIDENCE YET** at creation
- Intent: Founder previously requested liquidation of a single tiny Apple fractional holding and instructed the team to proceed with actual capability testing.
- Existing read-only evidence: [2026-10-15 account/sellability preflight](https://github.com/ringoincidents/quantrade/actions/runs/38712284664); user account values and identifiers are **not preserved in the public repository**.
- First-party order schema: [Toss OpenAPI v1.2.24](https://openapi.tossinvest.com/openapi-docs/latest/openapi.json): only US+MARKET+SELL accepts fractional share quantity up to six decimals; fractional order acceptance from US regular open through one hour before close.
- Trade is restricted to AAPL SELL MARKET only; shares less than 0.01, estimated gross notional below 10 USD using account-reported lastPrice, no purchases/short sales/funding.
- Date: **US exchange date 2026-10-15 ONLY**, after regular opening plus five minutes and before close minus one hour plus five-minute buffer, using live official US market-calendar GET. A date rollover or holiday must veto.
- Access: existing GitHub Actions → fixed-IP proxy → Toss API. Workflow `.github/workflows/toss_aapl_once.yml` has an explicit **one-time dated scheduled attempt** 2026-10-15 13:40 UTC (22:40 KST), not a recurring trading strategy. GitHub schedule drift may result in no trade; script fails closed outside window. Manual/PR/push workflows are read-only.
- Pre-submit: GET calendar/accounts/holdings/sellable/open orders/full closed-order history; account must be unique, holding must be a tiny <=6-decimal US AAPL fractional share, fully sellable, no duplicate SELL order, no previously attempted fixed clientOrderId. Any unknown schema, pagination, changed position, missing data: BLOCK.
- Broker POST: at most once on original **schedule** attempt (`GITHUB_RUN_ATTEMPT=1`), `POST /api/v1/orders`, fixed clientOrderId, DAY, US AAPL SELL MARKET, quantity from **fresh** authenticated account response. Never re-submit after timeout; no automated order retries, status requery is GET-only.
- Output to public CI logs: coarse status codes only; no exact holding quantity, account number, price, access token, or broker order id.
- Accepted order != filled order. Only a verified GET order detail status may establish filled/partial; if ambiguous, investigate without new POST.
- No changes to `autoexec.py`, broad live execution authorization, strategy models, unrelated positions or Holdings canonical Memory.
- Constraints: no persistent private execution journal integrated; GitHub Actions scheduler reliability known problematic. Time/date/session and one-attempt guard are intentionally narrow; do not extrapolate to ongoing bot operations. External account trading risks include market price at fill and fractional rounding.
- Offline verification: `python -m unittest discover -s tests -p 'test_toss_one_shot_aapl.py' -v` mocked broker 18 cases locally passed; require independent PR CI before merge.
- Outcome status must be updated only after actual GitHub workflow and broker GET evidence is observed. **Do not call the sell completed on CI alone.**
