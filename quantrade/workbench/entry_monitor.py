"""Provisional read-only entry monitor; no broker or AI calls."""
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal

@dataclass(frozen=True)
class Quote:
    instrument: str
    price: Decimal
    currency: str
    observed_at: datetime
    source: str

@dataclass(frozen=True)
class Target:
    instrument: str
    value: Decimal
    margin: Decimal
    currency: str
    version: str
    evidence: str
    approved_at: datetime
    expires_at: datetime

def _aware(dt):
    return isinstance(dt, datetime) and dt.utcoffset() is not None

def check_entry(quote, target, *, as_of, max_age):
    """Compare a supplied quote with a human-approved target; not trade advice.
    An upstream approval adapter and trading-calendar freshness policy are required
    before production. No inference from missing or stale data.
    """
    def result(status, reason, entry=None, margin=None):
        return dict(status=status, reason=reason, entry_price=entry, safety_margin=margin)
    if quote is None or target is None:
        return result("BLOCKED", "MISSING_INPUT")
    if not all(_aware(t) for t in (as_of, quote.observed_at, target.approved_at, target.expires_at)):
        return result("BLOCKED", "INVALID_TIME")
    if not isinstance(max_age, timedelta) or max_age <= timedelta(0):
        return result("BLOCKED", "INVALID_FRESHNESS_POLICY")
    if not all(isinstance(x, str) and x.strip() for x in (quote.instrument, quote.currency, quote.source, target.instrument, target.currency, target.version, target.evidence)):
        return result("BLOCKED", "MISSING_PROVENANCE")
    if quote.instrument != target.instrument or quote.currency != target.currency:
        return result("BLOCKED", "IDENTITY_OR_CURRENCY_MISMATCH")
    if not all(isinstance(x, Decimal) and x.is_finite() for x in (quote.price, target.value, target.margin)):
        return result("BLOCKED", "INVALID_NUMBER")
    if quote.price <= 0 or target.value <= 0 or not Decimal(0) <= target.margin < Decimal(1):
        return result("BLOCKED", "INVALID_NUMBER")
    if not target.approved_at <= as_of < target.expires_at:
        return result("BLOCKED", "TARGET_NOT_CURRENT")
    if quote.observed_at > as_of or as_of - quote.observed_at > max_age:
        return result("BLOCKED", "QUOTE_NOT_CURRENT")
    entry = target.value * (Decimal(1) - target.margin)
    margin = Decimal(1) - quote.price / target.value
    return result("REVIEW" if quote.price <= entry else "WAIT",
                  "ENTRY_CONDITION_MET" if quote.price <= entry else "ABOVE_ENTRY",
                  entry, margin)

if __name__ == "__main__":
    from datetime import timezone
    import json
    now = datetime(2026, 11, 28, tzinfo=timezone.utc)
    q = Quote("DEMO", Decimal("80"), "USD", now, "SYNTHETIC")
    t = Target("DEMO", Decimal("100"), Decimal(".20"), "USD", "demo-v1",
               "SYNTHETIC", now, now + timedelta(days=7))
    print(json.dumps({"mode": "SYNTHETIC_ONLY", "instrument": q.instrument,
                      "as_of": now.isoformat(), "target_version": t.version,
                      **check_entry(q, t, as_of=now, max_age=timedelta(days=1))},
                     default=str, indent=2))
