# QuanTrade P1.2 — Evidence Adapter Spec

Date: 2026-09-19
Status: Ready for implementation
Base: P1.1 validated institutional runtime

## Objective

Move existing Research/Intelligence outputs into the institutional Evidence model without treating AI prose, priority scores, or market indicators as investment decisions.

Target sources:
- `news_event_cards.json.change_events`
- `market_indicators.json`
- selected factual fields from news/event cards
- `ai_briefing.json` only as a presentation/secretary layer, never as canonical Evidence

## Core rule

Evidence is an observed fact plus provenance.

`AI explanation != Evidence`

An LLM may summarize or connect already-recorded Evidence, but its prose must not silently become a sourced fact, RiskAssessment, InstitutionalPosition, or InvestmentDecision.

## Source classification

### change_events — canonical Evidence candidate

Existing fields already support institutional provenance:
- timestamp
- asset
- source
- event_type
- observed_value
- baseline
- change
- reliability
- related_assets
- priority

Adapter must preserve the raw observation and source. Priority is routing metadata, not evidentiary strength and not Founder materiality.

### market_indicators — deterministic Observation / Evidence candidate

Examples:
- volatility_20d_pct
- volatility_percentile
- momentum_20d_pct
- adx_14
- portfolio correlation

These are deterministic measurements. Missing values and `data_status` must remain missing/status-labelled; no filling or inference.

### display cards

`cards[].summary` may contain AI-generated factual explanation for news cards or deterministic text for anomaly cards. The adapter must not assume all summary text has equal provenance.

Use the structured `change_events` representation when available. If a display-only card lacks structured provenance, keep it as a presentation artifact or mark it as unverified context rather than canonical Evidence.

### ai_briefing

`ai_briefing.json` is not an Evidence source.

Allowed future role:
- Secretary / Founder briefing presentation
- links to canonical Evidence IDs
- hypotheses explicitly marked as hypotheses

Forbidden:
- creating Evidence solely from briefing prose
- creating an InstitutionalPosition or Decision from briefing prose
- hiding `api_failed` behind fabricated fallback text

## Required adapters

### ChangeEventEvidenceAdapter

Input: one structured `change_event`.

Output:
- source
- observed_at
- subject / asset identity
- fact payload
- provenance containing raw event type, source, reliability, observed/baseline/change, related assets
- routing metadata kept separate from evidence content

### MarketIndicatorEvidenceAdapter

Input: one indicator row or portfolio-level correlation observation.

Output:
- deterministic Evidence candidate
- as-of timestamp from parent document
- explicit missing-data fields
- source schema/version

### EvidenceDeduplicator

P1.2 must avoid creating duplicate Evidence every time a scheduled JSON file is reread.

Deterministic fingerprint should include stable factual identity such as:
`source + observed_at + subject + event_type/metric + observed value`

Do not use generated UUID alone for deduplication.

### Evidence ingestion service

For an existing Case:
- attach canonical Evidence through `InstitutionalKernel.add_evidence()`
- preserve provenance
- return Evidence IDs for later InstitutionalPosition references

For observations not yet associated with a Case:
- retain them as Events / observation records
- do not create a Case solely because a priority score is high

## Priority vs materiality

Existing `priority_score` is an information-routing heuristic.

It is NOT:
- Evidence reliability
- Case LOW/MEDIUM/HIGH
- Risk severity
- Founder urgency
- investment conviction

P1.2 must keep these concepts separate.

## Tests

- structured change_event converts without losing provenance
- priority_score never becomes Case materiality
- deterministic indicator values remain unchanged
- missing indicator values remain missing
- duplicate source observation produces the same fingerprint
- AI briefing prose cannot be ingested through canonical Evidence adapter
- Evidence can attach to an existing Case and be referenced by an InstitutionalPosition
- no broker, autoexec, pending_actions, or live-order dependency
- `api_failed` briefing state remains visible and does not fabricate content

## Gate to P1.3

P1.2 passes when:

`Research observation → canonical Evidence → Case → InstitutionalPosition`

is reproducible with provenance and deduplication, while AI-generated briefing remains a non-authoritative presentation layer.
