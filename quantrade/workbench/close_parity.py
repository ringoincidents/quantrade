"""Offline exact-price parity preflight. Never grants live signal authority.

Provider identity, instrument mapping, session, raw basis and observation time
must be established before comparison. A match is not a finality attestation,
an independent upstream feed, data-use permission or a trading decision.
No networking, storage, logging or credentials in this module.
"""
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
import re

from .entry_monitor import bounded_decimal
from .local_report import MARKETS, market

RAW = "RAW_PER_SHARE"
REGULAR = "REGULAR_CLOSE"
DAILY = "DAILY_CANDLE_CLOSE_UNVERIFIED_SESSION"

@dataclass(frozen=True)
class Observation:
    provider: str
    instrument: str
    currency: str
    session: date
    price: Decimal
    basis: str
    kind: str
    retrieved_at: datetime
    source_ref: str

def price(value):
    # JSON financial numbers must be parsed with parse_float=Decimal.
    # Never convert a binary float or a boolean to a price.
    if type(value) is int:
        value = str(value)
    if isinstance(value, str):
        if not re.fullmatch(r"\d{1,24}(\.\d{1,12})?", value):
            raise ValueError("INVALID_PRICE")
        value = Decimal(value)
    if not isinstance(value, Decimal) or not bounded_decimal(value) or value <= 0:
        raise ValueError("INVALID_PRICE")
    return value

def observation(provider, instrument, currency, session, value, kind, retrieved_at, source_ref):
    if not isinstance(session, date) or isinstance(session, datetime):
        raise ValueError("INVALID_SESSION")
    if currency != MARKETS[market(instrument)][1]:
        raise ValueError("CURRENCY_MISMATCH")
    if not isinstance(retrieved_at, datetime) or retrieved_at.utcoffset() is None:
        raise ValueError("INVALID_RETRIEVAL_TIME")
    if not isinstance(source_ref,str) or not source_ref.strip():
        raise ValueError("MISSING_SOURCE_REFERENCE")
    return Observation(provider,instrument,currency,session,price(value),RAW,kind,retrieved_at,source_ref)

def parse_krx_daily(payload, *, instrument, session, retrieved_at, endpoint):
    # Only known stock daily endpoints. A source response must identify the
    # exact instrument and session uniquely; never choose the first match.
    if market(instrument) != "KRX" or endpoint not in ("stk_bydd_trd","ksq_bydd_trd"):
        raise ValueError("MARKET_OR_ENDPOINT_MISMATCH")
    symbol=instrument.split(":")[1]
    rows=payload.get("OutBlock_1") if isinstance(payload,dict) else None
    if not isinstance(rows,list):
        raise ValueError("INVALID_SCHEMA")
    hits=[r for r in rows if isinstance(r,dict) and r.get("ISU_CD")==symbol and r.get("BAS_DD")==session.strftime("%Y%m%d")]
    if len(hits)!=1:
        raise ValueError("MISSING_OR_AMBIGUOUS_CLOSE")
    return observation("KRX",instrument,"KRW",session,hits[0].get("TDD_CLSPRC"),
                       REGULAR,retrieved_at,"KRX/"+endpoint+"/"+session.isoformat())

def parse_massive_daily(payload, *, instrument, session, retrieved_at, adjusted):
    if market(instrument) not in ("XNYS","XNAS") or adjusted is not False:
        raise ValueError("MARKET_OR_BASIS_MISMATCH")
    symbol=instrument.split(":")[1]
    if not isinstance(payload,dict) or payload.get("status")!="OK" or payload.get("symbol")!=symbol or payload.get("from")!=session.isoformat():
        raise ValueError("MISSING_OR_AMBIGUOUS_CLOSE")
    # The request must use adjusted=false. Never use afterHours or preMarket.
    return observation("MASSIVE",instrument,"USD",session,payload.get("close"),REGULAR,
                       retrieved_at,"MASSIVE/open-close/"+symbol+"/"+session.isoformat())

def parse_toss_kr_daily(payload, *, instrument, session, retrieved_at, adjusted):
    # Only documented KR daily timestamp convention is accepted here.
    # US daily bar timezone/session semantics still need live/schema review.
    if market(instrument)!="KRX" or adjusted is not False:
        raise ValueError("MARKET_OR_BASIS_MISMATCH")
    rows=payload.get("result",{}).get("candles") if isinstance(payload,dict) and isinstance(payload.get("result"),dict) else None
    if not isinstance(rows,list):
        raise ValueError("INVALID_SCHEMA")
    hits=[]
    for row in rows:
        if not isinstance(row,dict):
            raise ValueError("INVALID_SCHEMA")
        stamp=row.get("timestamp")
        if not isinstance(stamp,str):
            raise ValueError("INVALID_TIMESTAMP")
        d=datetime.fromisoformat(stamp)
        if d.utcoffset() is None:
            raise ValueError("INVALID_TIMESTAMP")
        from datetime import timedelta
        if d.utcoffset()!=timedelta(hours=9) or (d.hour,d.minute,d.second,d.microsecond)!=(0,0,0,0):
            raise ValueError("UNVERIFIED_DAILY_TIMESTAMP_CONVENTION")
        if d.date()==session:
            hits.append(row)
    if len(hits)!=1:
        raise ValueError("MISSING_OR_AMBIGUOUS_CLOSE")
    # Symbol is bound to the requested endpoint, not echoed by its response.
    # Midnight timestamp is a label, never publication or close time.
    return observation("TOSS",instrument,hits[0].get("currency"),session,hits[0].get("closePrice"),
                       DAILY,retrieved_at,"TOSS/candles/1d/"+instrument+"/"+session.isoformat())

def compare(primary, reference, *, expected_instrument, expected_session, scheduled_close, as_of):
    """Status-only; no price, difference, hash or raw response is returned."""
    def result(state):
        return {"state":state,"decision_authorized":False,"actual_finality_verified":False,
                "independent_upstream_verified":False,"rights_verified":False}
    if primary is None or reference is None:
        return result("MISSING_SOURCE")
    if not all(isinstance(x,Observation) for x in (primary,reference)):
        return result("INVALID_OBSERVATION")
    if not all(isinstance(x,datetime) and x.utcoffset() is not None for x in (scheduled_close,as_of)):
        return result("INVALID_TIME")
    if scheduled_close > as_of:
        return result("SESSION_NOT_COMPLETED")
    try:
        currency=MARKETS[market(expected_instrument)][1]
        from zoneinfo import ZoneInfo
        if scheduled_close.astimezone(ZoneInfo(MARKETS[market(expected_instrument)][0])).date()!=expected_session:
            return result("SESSION_TIME_MISMATCH")
        for q in (primary,reference):
            if q.instrument!=expected_instrument or q.session!=expected_session:
                return result("IDENTITY_OR_SESSION_MISMATCH")
            if q.currency!=currency or q.basis!=RAW:
                return result("CURRENCY_OR_BASIS_MISMATCH")
            if not isinstance(q.retrieved_at,datetime) or q.retrieved_at.utcoffset() is None or not scheduled_close<=q.retrieved_at<=as_of:
                return result("INVALID_RETRIEVAL_TIME")
            price(q.price)
            if not q.source_ref or q.kind not in (REGULAR,DAILY):
                return result("INVALID_OBSERVATION")
    except (KeyError,TypeError,ValueError,ArithmeticError):
        return result("INVALID_OBSERVATION")
    if primary.provider==reference.provider:
        return result("SAME_PROVIDER")
    if primary.kind!=REGULAR or reference.kind!=REGULAR:
        return result("SESSION_DEFINITION_UNVERIFIED_MATCH" if primary.price==reference.price
                      else "SESSION_DEFINITION_UNVERIFIED_MISMATCH")
    return result("EXACT_MATCH_UNVERIFIED" if primary.price==reference.price else "PRICE_MISMATCH")
