"""Bounded, source-reviewed calendar reference. No production authorization.

This module separates scheduled regular close, plan eligibility and observed
provider availability. It does NOT attest exceptional closures, provider
finality, data rights or an authenticated approval.
"""
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

VERSION = "2026-11-28-reference-v1"
US_ZONE = ZoneInfo("America/New_York")
KR_ZONE = ZoneInfo("Asia/Seoul")
NY_SOURCE = "https://www.nyse.com/trade/hours-calendars"
NASDAQ_SOURCE = "https://www.nasdaq.com/market-activity/stock-market-holiday-schedule"
KR_SOURCE = "https://global.krx.co.kr/contents/GLB/06/0602/0602010201/GLB0602010201T1.jsp"
MASSIVE_SOURCE = "https://massive.com/knowledge-base/article/on-the-free-basic-plan-when-can-i-pull-the-previous-trading-days-data"

# Deliberately bounded review window: Thanksgiving week and the next week.
# Ordinary weekdays are reference schedules, not actual-exchange close evidence.
START = date(2026,11,23)
END = date(2026,12,4)
HOLIDAYS = frozenset({date(2026,11,26)})
EARLY_CLOSE = {date(2026,11,27):time(13)}

@dataclass(frozen=True)
class Session:
    market: str
    session_date: date
    close_at: datetime
    source: str
    version: str = VERSION

def require_aware(value):
    if not isinstance(value,datetime) or value.utcoffset() is None:
        raise ValueError("INVALID_AS_OF")

def us_scheduled_session(market, day):
    if market not in ("XNYS","XNAS"):
        raise ValueError("CALENDAR_MARKET_UNVERIFIED")
    if not START <= day <= END:
        raise ValueError("CALENDAR_OUTSIDE_COVERAGE")
    if day.weekday() >= 5 or day in HOLIDAYS:
        return None
    return Session(market,day,datetime.combine(day,EARLY_CLOSE.get(day,time(16)),US_ZONE),
                   NY_SOURCE if market=="XNYS" else NASDAQ_SOURCE)

def latest_scheduled_close(market, as_of):
    require_aware(as_of)
    if market not in ("XNYS","XNAS"):
        raise ValueError("CALENDAR_MARKET_UNVERIFIED")
    day=as_of.astimezone(US_ZONE).date()
    if not START <= day <= END:
        raise ValueError("CALENDAR_OUTSIDE_COVERAGE")
    while day >= START:
        session=us_scheduled_session(market,day)
        if session is not None and session.close_at <= as_of:
            return session
        day-=timedelta(days=1)
    raise ValueError("NO_COMPLETED_SESSION_IN_COVERAGE")

def massive_basic_eligible_at(session):
    if session.market not in ("XNYS","XNAS"):
        raise ValueError("PROVIDER_MARKET_MISMATCH")
    # Plan's date boundary, not a guarantee of actual publication/finality.
    return datetime.combine(session.session_date+timedelta(days=1),time(0),US_ZONE)

def assess(market, as_of, *, declared_session=None):
    """Reference assessment, never an executable trade/entry signal."""
    try:
        expected=latest_scheduled_close(market,as_of)
    except ValueError as e:
        return {"state":"BLOCKED","reason":str(e),"calendar_version":VERSION,
                "decision_authorized":False}
    eligible=massive_basic_eligible_at(expected)
    state="PLAN_ELIGIBLE_UNVERIFIED" if as_of>=eligible else "PUBLICATION_WINDOW_PENDING"
    if declared_session is not None and declared_session!=expected.session_date.isoformat():
        state="SESSION_MISMATCH"
    return {"state":state,"reason":"REFERENCE_ONLY_NO_ACTUAL_CLOSE_ATTESTATION",
            "market":market,"session_date":expected.session_date.isoformat(),
            "scheduled_close":expected.close_at.isoformat(),
            "plan_eligible_at":eligible.isoformat(),"calendar_version":VERSION,
            "calendar_source":expected.source,"provider_source":MASSIVE_SOURCE,
            "actual_finality_verified":False,"decision_authorized":False}
