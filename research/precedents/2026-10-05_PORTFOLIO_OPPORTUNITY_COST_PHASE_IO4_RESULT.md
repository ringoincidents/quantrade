# Phase IO-4 Result — Portfolio Opportunity Cost Assessment

Status: **IMPLEMENTED IN SANDBOX / VERIFIED / NON-AUTHORITATIVE**  
Date: **2026-10-05**

## 1. Purpose

IO-1 through IO-3B establish:

- deterministic Investment Case economics;
- structured Thesis / Counter-Thesis / Falsification;
- point-in-time fundamental evidence contracts;
- a real Open DART provider adapter.

IO-4 adds the next organizational boundary:

> An attractive security is not automatically a good use of this Client's
> capital.

The module asks whether a Case is competitive with explicit capital
alternatives and whether any deterministic capital headroom exists before
Portfolio/Risk review.

## 2. Implemented files

Core:

`quantrade/capabilities/portfolio_opportunity.py`

Reference harness:

`quantrade/capabilities/portfolio_opportunity_evaluation.py`

Tests:

`tests/capabilities/test_portfolio_opportunity.py`

## 3. Scope

IO-4 v1 is intentionally limited to:

`RETURN_SEEKING_ACTIVE`

It does not yet model hedging, liability matching, tax-loss harvesting, or
non-return-seeking strategic positions.

Those use cases should not be forced into one return-ranking formula.

## 4. Capital alternatives

Every Case must compete against explicit alternatives such as:

- CASH;
- CORE_BENCHMARK;
- CURRENT_HOLDING;
- ACTIVE_CASE.

Each alternative carries:

- alternative ID;
- alternative type;
- expected return assumption;
- optional downside assumption;
- basis references.

The module does not infer that cash has 0% return or that a benchmark has a
specific expected return.

Those values must be supplied explicitly and remain assumption-scoped inputs.

If no alternative is supplied, the output is:

`MISSING_CONTEXT`

not approval.

## 5. Opportunity-cost calculation

For a candidate Investment Case, IO-4 calculates:

- candidate expected return;
- best explicit capital alternative;
- best-alternative expected return;
- candidate excess expected return versus best alternative.

A candidate that does not beat the best explicit alternative is not eligible
for downstream Portfolio review in this v1 return-seeking scope.

This makes the question:

> "Is this stock attractive?"

secondary to:

> "Is it a better use of capital than the alternatives available to this
> Client?"

## 6. Explicit Portfolio constraints

The Portfolio constraint snapshot carries:

- snapshot ID / as-of;
- whether the Mandate allows new exposure;
- Mandate reference;
- current candidate-asset weight;
- maximum candidate-asset weight;
- current liquidity;
- minimum liquidity reserve;
- available downside budget;
- constraint references.

No default concentration/liquidity/risk percentages are silently invented by
this module.

The thresholds must come from upstream Client Mandate / Portfolio / Risk
policy.

The snapshot must not be dated after the Investment Case.

## 7. Deterministic capital headroom

The module calculates three independent ceilings.

### Concentration headroom

```text
max asset weight - current asset weight
```

### Liquidity headroom

```text
current liquidity - required liquidity reserve
```

floored at zero.

### Downside-budget headroom

If the Case Bear/lowest scenario is negative:

```text
available portfolio downside budget
÷ candidate downside severity
```

Example:

- candidate Bear case: -40%
- available portfolio downside budget: 2%

Then:

```text
2% / 40% = 5% portfolio-weight ceiling
```

The deterministic capital upper bound is:

```text
min(
  concentration headroom,
  liquidity headroom,
  downside-budget headroom
)
```

## 8. Critical authority distinction

The output explicitly states:

`deterministic_upper_bound_pct != target_weight`

The module may calculate that more than 5% would violate an explicit
constraint.

It may **not** conclude:

> "Therefore buy 5%."

That remains downstream Portfolio/Risk/Committee work.

## 9. Review status

Possible v1 statuses:

- `MISSING_CONTEXT`
- `NOT_COMPETITIVE`
- `ELIGIBLE_FOR_PORTFOLIO_REVIEW`

Eligibility requires:

- Mandate allows new exposure;
- Investment Case's own required-return hurdle is met;
- candidate expected return beats the best explicit capital alternative;
- deterministic capital headroom is greater than zero.

This is review eligibility only.

## 10. Reference harness

Synthetic reference Case:

- positive Investment Case economics;
- CASH alternative;
- CORE benchmark alternative;
- explicit concentration/liquidity/downside constraints.

The candidate clears the return competition.

However the maximum deterministic capital headroom is limited by the Bear-case
downside budget.

A second Case uses the same attractive security economics but a fully used
concentration limit.

Result:

`NOT_COMPETITIVE`

This demonstrates:

> the same attractive security can deserve review in one portfolio state and
> deserve zero new allocation in another.

## 11. Point-in-time Portfolio state

The Portfolio constraint snapshot as-of must be:

```text
constraints_as_of <= InvestmentCase.as_of
```

A future portfolio snapshot cannot be used to make a historical Case look
better or safer.

## 12. Authority invariant

IO-4 reports:

```text
model_called = false
canonical_evidence_created = false
thesis_validated = false
portfolio_review_eligibility_created = true
portfolio_proposal_created = false
target_weight_set = false
risk_opinion_created = false
risk_limit_changed = false
committee_decision_created = false
decision_plan_created = false
paper_authorized = false
execution_authorized = false
live_order_possible = false
```

## 13. Verification

Latest Investment Office Core CI:

`37266720046`

Result: **SUCCESS**

Observed tests:

- Investment Case Economics: **10 passed**
- Thesis Contract: **12 passed**
- PIT Fundamental Evidence: **11 passed**
- Open DART Provider: **12 passed**
- Portfolio Opportunity Cost: **12 passed**
- full capability regression suite: **84 passed**
- reference harnesses: success

## 14. Current executable Investment Office chain

The program can now represent:

```text
Open DART / Fundamental Evidence
        ↓
Observation / Assumption / Inference
        ↓
Investment Thesis
 ↙ Counter-Thesis
 ↘ Falsification
        ↓
Scenario / Valuation Economics
        ↓
Capital Alternatives
        ↓
Portfolio Opportunity Cost
        ↓
Deterministic Capital Headroom
        ↓
ELIGIBLE / NOT_COMPETITIVE / MISSING_CONTEXT
```

No trade recommendation or order is produced.

## 15. Next bounded step

The next layer is:

**IO-5 — Independent Risk Opinion**

Risk should receive the Portfolio-eligible Case and independently test:

- concentration;
- portfolio drawdown budget;
- candidate downside;
- correlation / common-factor concentration where available;
- liquidity;
- leverage;
- mandate/policy violations;
- missing risk context.

Risk must be able to:

- PASS;
- PASS_WITH_LIMITS;
- VETO;
- REQUIRE_MORE_INFORMATION.

It must not be designed merely to justify Portfolio Management.
