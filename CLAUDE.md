# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

Quantrade is a personal quant portfolio bot ("분석, 추후엔 자동 거래" — analysis now, autotrading later). It scans Korean crypto (Upbit) and US stocks, asks Claude for buy/sell/hold decisions, executes small/low-risk trades automatically, and queues larger or riskier trades for manual approval via Telegram. State lives entirely in JSON files committed to the repo; GitHub Actions is the runtime (there is no server).

There are no tests, no linter config, and no dependency manifest (`requirements.txt`) in this repo — the only third-party dependency is `requests`, installed inline in CI (`pip install requests`). When changing code, mirror that: keep dependencies minimal and don't introduce a build/test toolchain unless asked.

## Project context

- This is a personal AI investment-decision *assistant*, not an autotrader — every non-trivial trade is either auto-executed under tightly bounded safety rules or held for explicit human approval via Telegram. Do not blur that line.
- The user is doing mandatory military service and only has PC access ~6-9am at a "cyber knowledge information room" (사이버지식정보방); the rest of the time they interact via the mobile Claude app. Code changes now happen through Claude Code. Keep this in mind for anything time-sensitive (e.g. don't assume same-day follow-up is possible outside that window).
- The project is in a validation/trial phase running through December 2026 — this is a virtual simulation with no real trades yet. Expanding to real trading is only to be discussed after backtest validation, not implemented unprompted.
- Asset coverage is actively transitioning from crypto (Upbit) to domestic Korean stocks via the Toss Securities API, because crypto exchange sites are blocked on the military network. Expect `analyze_lib.py`'s crypto-scanning code to be gradually replaced/supplemented by Toss-based stock scanning — when working here, check whether the crypto path is still the active one or already superseded.
- Overall project direction/roadmap lives in a separate planning document outside this repo; ask the user for it if you need it rather than assuming.

## Running

```bash
pip install requests
export TELEGRAM_TOKEN=...      # bot token
export TELEGRAM_CHAT_ID=...    # chat to notify
export CLAUDE_API_KEY=...      # Claude API key for trade decisions
python analyze.py          # run one full daily analysis/trade cycle
python check_updates.py    # poll Telegram for /approve /reject /keep /unkeep /status commands
python backtest.py         # run the backtest engine against historical data (see below)
```

Both `analyze.py` and `check_updates.py` read and rewrite the JSON state files in the repo root, then (in CI) those files are committed back. There's no test suite to run — verify changes by running the script locally against the existing JSON state and inspecting the diff/output, or by mocking `requests` calls if testing logic in isolation.

## Architecture

**`analyze_lib.py`** — all shared logic and I/O: technical indicators (MA, RSI, Bollinger bands), Upbit/Yahoo/stooq/Naver market data fetchers (including `get_krx_candles`, a Naver-based historical fetcher for Korean stocks used until the Toss Securities API is wired in), the shared entry-scoring rule (`entry_score`, used by both live scanning and the backtest engine so they can't drift apart), crypto/stock candidate scanning (`scan_crypto`, `scan_stocks`), Google News RSS headline fetching (`get_news_headlines`), the Claude API call that turns holdings + candidates + news into a decision JSON (`ask_claude_decision`), Telegram sending, and generic `load_json`/`save_json` helpers. Constants here (`HARD_STOP_LOSS`, `EXCLUDE_MARKETS`, `US_STOCKS`, `TRADING_COSTS`) are the tunable knobs for strategy behavior.

**Phase 2 shift (2026-08-01, after Phase 1's backtest gate failed — see `backtest.py` below): price signals are demoted to a pre-filter, news/events are the actual decision basis.** `entry_score` (RSI + Bollinger) still gates which candidates `scan_crypto`/`scan_stocks` surface each day — that's kept purely for practical reasons, since the full ~80-market crypto universe can't all be sent to Claude daily — but it's no longer treated as a trading thesis. `get_news_headlines` replaced the old `get_news_sentiment` (which counted positive/negative keyword hits into a single label like "긍정 우세 (3/1)", discarding the actual headline content): it now returns raw headline text (or `None` on fetch failure, distinct from an empty list meaning "genuinely no news"), which `ask_claude_decision` passes straight into the prompt. The prompt itself now explicitly instructs Claude that price/filter metrics aren't the basis for a decision — news-driven events are — and to default to hold/wait when there's no news or the fetch failed, rather than trading on price metrics alone. `HARD_STOP_LOSS` is untouched throughout — it was already the one AI-independent, unconditional safety net this shift is modeled after.

`get_us_closes` tries Yahoo Finance's chart API first, then falls back to stooq — stooq alone was confirmed (during the phase-1 backtest run) to return a bot-detection challenge page instead of CSV from GitHub Actions IPs, which meant `scan_stocks` had likely been silently finding zero US stock candidates in every daily run (no `asset_class: "stock"` entries ever appear in `portfolio.json`/`trade_history.json`). This edit could not be network-tested in the editing sandbox (all outbound hosts were proxy-blocked there) — confirm it actually works by checking `daily.yml`/`backtest.yml` logs after this lands, and add another fallback if Yahoo also turns out to be blocked from Actions IPs.

**`analyze.py`** — the daily cycle (`run()`), driven by `daily.yml`:
1. Price every held position, compute return %.
2. Scan for new crypto/stock candidates, classify each by expected holding period into a strategy: 단타 (day, ≤6 days), 스윙 (swing, ≤20 days), 장기 (long-term, >20 days) — see `classify_strategy`/`estimate_holding_period`.
3. Send all holdings + candidates + news to Claude (`ask_claude_decision`) for a market summary and per-market decisions.
4. Apply decisions:
   - Hard stop-loss (`HARD_STOP_LOSS` per strategy type) always fires immediately regardless of AI decision.
   - Otherwise, a sell/buy either executes automatically or goes into `pending_actions.json` awaiting Telegram approval, based on `needs_approval()`: 장기 (long-term) positions, `stock`/`krx` asset classes, or positions ≥25% of total assets (`LARGE_POSITION_THRESHOLD`) all require approval; small crypto swing/day trades execute automatically.
   - Positions flagged `conviction: true` are excluded from all automated sell/hold decisions (user has manually pinned them).
5. Persist `portfolio.json`, `trade_history.json`, `pending_actions.json`, and a dashboard-facing snapshot `last_report.json`, then send the report text to Telegram.

**`check_updates.py`** — the Telegram command loop (`run()`), driven by `poll.yml` every 15 min. Long-polls `getUpdates` since `telegram_offset.json`'s last update id, and handles:
- `/approve <id>` / `/reject <id>` — resolve a pending action from `pending_actions.json`.
- `/keep <market>` / `/unkeep <market>` — toggle the `conviction` flag on a held position.
- `/status` — report current positions back to Telegram.

After any state change it also refreshes `last_report.json` (`refresh_last_report`) so the web dashboard reflects approvals immediately rather than waiting for the next daily run.

**`backtest.py`** — Phase 1 backtest engine (계획서 v3 §5), run manually (CLI or `backtest.yml` workflow_dispatch), separate from the daily/poll cycle. **Its entry signal is intentionally decoupled from live scanning** (`scan_crypto`/`scan_stocks`/`entry_score` in `analyze_lib.py` are untouched): after the first RSI+Bollinger-only backtest failed to hold up in validation, the strategy was redesigned around trend-following — a 20/60-day moving-average golden cross gated by ADX ≥ 25 (`is_golden_cross`, `calc_adx` in `analyze_lib.py`) as the main signal, with RSI/Bollinger demoted to an entry-timing filter (skip if RSI ≥ 75 or price already above the upper band) rather than an independent trigger. Don't assume backtest changes here apply to live trading — promoting a backtested rule into `entry_score` is a deliberate, separate step per "전략 검증이 아키텍처보다 먼저다" (validate before wiring into live scanning). Since past Claude decisions can't be replayed (cost + non-determinism), sell-side is still approximated with rule-based exits (hard stop-loss, RSI overbought, a time-stop at 2x the expected holding period) — a known simplification to revisit once Phase 2's AI-confidence calibration exists. Applies `TRADING_COSTS` (fee + slippage assumptions, plus a KRX sell-only `sell_tax_pct` for 증권거래세) on entry/exit, splits trades into a 70/30 train/validation set by date, and buckets results by market regime (상승장/하락장/횡보장, from trailing 60-day return) and by strategy type. Also computes a simple buy-and-hold benchmark over the same instruments/period (`buy_hold_trades`) so the strategy's numbers can be judged against "would just holding have done better" (`benchmark_buy_hold`/`strategy_vs_buy_hold` in the report) — not just against the frozen success criteria. Buy-and-hold trades are also regime-tagged (at entry only, not day-by-day through the multi-year hold) so `by_regime_strategy`/`by_regime_buy_hold` can be compared per regime. Results are checked against the frozen success criteria from 계획서 v3 §4.3 (`SUCCESS_CRITERIA`: ≥30 trades, sharpe-like ratio) and written to `backtest_report.json`; MDD is reported but treated as reference-only (`MDD_CAVEAT`) until Phase 2's position sizing lands, since the current single combined equity curve overstates drawdown versus a real multi-position portfolio. Per the plan, the ≥30-trade/sharpe thresholds are fixed on purpose and shouldn't be adjusted after the fact to fit results. `evaluate_gate()` bundles the full pass/fail check from the 2026-08-01 handoff doc's §2.1 gate (≥30 trades each split, validation sharpe ≥1.0, train/validation same-sign sharpe as an overfitting check, beats buy-and-hold on both splits — MDD is reported but excluded from pass/fail per its own reference-only caveat) into `report["gate"]`. `--max-hold-multiplier`/`--rsi-exit` override the exit rule's time-stop multiplier and RSI-overbought threshold (default 2x/70, matching the validated rule) — added specifically for the handoff doc's one-shot "relax the exit and re-test once, no iterating" experiment; don't treat repeated use of these flags as license to keep tuning past that one attempt.

Default universe/lookback are wide by design (a first narrower run undershot the 30-trade minimum): `--crypto` omitted means all `get_all_krw_markets()[:80]` (same range as live `scan_crypto`) at `--crypto-count` candles (default 5000 — `get_krw_candles`'s pagination just stops early once a market's listing history runs out, so this isn't a hard requirement); `--krx` omitted means `KRX_MARKET_CAP_TOP`, a static large-cap KOSPI/KOSDAQ snapshot pending real market-cap-ranked scanning once Toss API integration lands (delisted/merged codes in it just get skipped). `--count` (KRX/US-stock lookback) defaults to 1500. Both `--crypto` and `--krx` still accept explicit values to narrow scope for a quick run.

**`index.html`** — static single-page dashboard (Chart.js via CDN) that fetches `portfolio.json` and `last_report.json` directly (cache-busted) and renders cash/positions/pending approvals/conviction holdings. It has no build step; it's served as-is (e.g. GitHub Pages) and only reads JSON, never writes it — approve/reject from the dashboard just copies the `/approve <id>` / `/reject <id>` command to the clipboard for the user to paste into Telegram.

## State files (all in repo root, treated as a database)

- `portfolio.json` — `cash` + `positions[]` (market, asset_class, strategy_type, entry_price/date, amount_krw, conviction flag).
- `trade_history.json` — closed trades log (`trades[]`).
- `pending_actions.json` — actions awaiting Telegram approval (`actions[]`, status: `waiting`/`approved`/`rejected`).
- `last_report.json` — denormalized snapshot for `index.html`; kept in sync by both `analyze.py` and `check_updates.py`.
- `telegram_offset.json` — last processed Telegram `update_id`, owned by `check_updates.py`.

Both GitHub Actions workflows commit these files back to the branch after running (`git add ...; git commit; git push`), so the two workflows (`daily.yml` at 11:00 UTC, `poll.yml` every 15 min) can race on the same files — be aware of that when changing commit/push logic or file schemas, since a schema change must stay compatible with whatever the other workflow's last commit wrote.

`backtest_report.json` (repo root, written by `backtest.py`/`backtest.yml`) is a separate output, not part of the daily/poll state and not read by `index.html` — it doesn't participate in the race above.

## Conventions specific to this repo

- User-facing strings (Telegram messages, report text, dashboard labels) and strategy-type values (`단타`/`스윙`/`장기`, `매수`/`매도`/`보유`/`비중조정`) are in Korean — keep new user-facing text and the JSON `action`/`strategy_type` vocabulary consistent with the existing Korean terms rather than switching to English.
- Claude is prompted to return *only* raw JSON; `ask_claude_decision` defensively strips code fences and extracts the outermost `{...}` before parsing, and retries once on failure. Preserve this defensiveness if you touch the prompt or parsing.
- Failures in price lookups, news fetches, or AI calls are caught and degrade gracefully (falling back to entry price, "뉴스 조회 실패", or an error message sent to Telegram) rather than crashing the workflow — the daily/poll Actions must keep running and committing state even when an external API is down.

## Working principles

- When you modify code, briefly explain *why* you changed it that way, not just what changed.
- Never remove or weaken the safety guardrails (hard stop-loss thresholds, the approval requirements for long-term/stock/large-position trades) as a side effect of an unrelated change. If a guardrail genuinely needs to change, call it out explicitly and confirm with the user first.
- Don't take this simulation toward real-money execution on your own initiative — that transition is a deliberate, separately-discussed decision gated on backtest results.
