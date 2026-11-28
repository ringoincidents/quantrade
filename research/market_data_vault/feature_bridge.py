"""Strict read-only RAW_OHLCV feature bundle for offline research.
Uses existing vault and indicator functions; not a new production FeatureProvider.
Declared session and corporate-action evidence is not independent attestation.
"""
import hashlib
import json
import math
from datetime import date, datetime
from zoneinfo import ZoneInfo
from indicators import LIBRARY_VERSION,sma,ema,rsi_wilder,atr_wilder,macd,bollinger,volume_ratio,cmf,ma_geometry
from vault import parse_utc

VERSION="vault_feature_bridge.v3"
MAX_SESSIONS=10000
MAX_REVISIONS=100000

class Blocked(ValueError): pass
def need(ok,reason):
    if not ok:raise Blocked(reason)
def instant(s):
    try:return datetime.fromisoformat(parse_utc(s))
    except (TypeError,ValueError,AttributeError):raise Blocked("INVALID_TIMESTAMP") from None
def iso_day(s):
    try:
        d=date.fromisoformat(s)
        need(d.isoformat()==s,"INVALID_SESSION")
        return d
    except (TypeError,ValueError):raise Blocked("INVALID_SESSION") from None
def evidence(s):
    return isinstance(s,str) and bool(s.strip()) and len(s)<=2048
def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(",",":"),allow_nan=False).encode()).hexdigest()

def select_bars(db,dataset_id,as_of,plan,*,mode="SYNTHETIC"):
    """Return complete declared-window measurements or fail closed.

    Plan binds ordered sessions, close instants, venue timezone, and coverage
    of corporate actions. No live claims; a hash is not evidence authenticity.
    """
    need(mode in ("SYNTHETIC","RESEARCH_CANDIDATE"),"INVALID_MODE")
    now=instant(as_of)
    need(isinstance(plan,dict),"INVALID_PLAN")
    need(plan.get("dataset_id")==dataset_id,"DATASET_PLAN_MISMATCH")
    need(evidence(plan.get("calendar_ref")) and evidence(plan.get("corporate_action_ref")),"EVIDENCE_MISSING")
    need(plan.get("corporate_action_state")=="NO_ACTIONS_IN_WINDOW","RAW_ACTIONS_UNRESOLVED")
    need(plan.get("timezone") in ("America/New_York","Asia/Seoul"),"UNSUPPORTED_TIMEZONE")
    zone=ZoneInfo(plan["timezone"])
    sessions=plan.get("sessions")
    need(isinstance(sessions,list) and 1<=len(sessions)<=MAX_SESSIONS,"INVALID_WINDOW")
    expected={}
    last=None
    for item in sessions:
        need(isinstance(item,dict),"INVALID_SESSION")
        session=item.get("session")
        d=iso_day(session);close=instant(item.get("close_at"))
        need(close.astimezone(zone).date()==d and close<=now,"SESSION_CLOSE_INVALID")
        need(last is None or d>last,"DUPLICATE_OR_UNSORTED_SESSION")
        expected[session]=close;last=d
    meta=db.execute("SELECT asset_id,provider,currency,basis,rights_note FROM datasets WHERE id=?",(dataset_id,)).fetchone()
    need(meta is not None,"DATASET_NOT_FOUND")
    need(meta[3]=="RAW_OHLCV" and all(evidence(x) for x in meta),"DATASET_METADATA_INVALID")
    if mode=="SYNTHETIC":
        need(meta[1]=="SyntheticTestProvider","NON_FIXTURE_IN_SYNTHETIC_MODE")
    else:
        need(meta[1]!="SyntheticTestProvider","FIXTURE_IN_RESEARCH_MODE")
    # Rank ALL revisions first, then verify the latest known one. Unlike the
    # legacy verified-only query, never silently substitute an older revision.
    sql="""SELECT b.session,b.available_at,b.open,b.high,b.low,b.close,b.volume,
        b.availability_verified,b.batch_sha,a.captured_at
        FROM bars b LEFT JOIN batches a ON a.dataset_id=b.dataset_id AND a.sha256=b.batch_sha
        WHERE b.dataset_id=? AND b.session BETWEEN ? AND ? LIMIT ?"""
    raw=db.execute(sql,(dataset_id,next(iter(expected)),next(reversed(expected)),MAX_REVISIONS+1)).fetchall()
    need(len(raw)<=MAX_REVISIONS,"REVISION_LIMIT")
    selected={}
    for session,available,o,h,l,c,v,verified,sha,captured in raw:
        published=instant(available)
        if published>now:continue
        need(session in expected,"UNEXPECTED_SESSION")
        need(published>=expected[session],"PRICE_BEFORE_CLOSE")
        prior=selected.get(session)
        need(prior is None or prior[0]!=published,"AMBIGUOUS_REVISION")
        if prior is None or prior[0]<published:
            selected[session]=(published,o,h,l,c,v,verified,sha,captured)
    need(set(selected)==set(expected),"MISSING_SESSION")
    bars=[]
    for session in expected:
        published,o,h,l,c,v,verified,sha,captured=selected[session]
        need(verified==1,"LATEST_REVISION_UNVERIFIED")
        need(isinstance(sha,str) and len(sha)==64 and all(x in "0123456789abcdef" for x in sha) and captured is not None,"BATCH_PROVENANCE_MISSING")
        capture=instant(captured)
        need(capture>=published,"CAPTURE_BEFORE_PUBLICATION")
        need(all(isinstance(x,(int,float)) and math.isfinite(x) for x in (o,h,l,c,v)) and
             min(o,h,l,c)>0 and v>=0 and l<=min(o,c,h) and h>=max(o,c,l),"INVALID_OHLCV")
        bars.append({"session":session,"available_at":published.isoformat(),"captured_at":capture.isoformat(),
                     "open":o,"high":h,"low":l,"close":c,"volume":v,"batch_sha256":sha})
    return meta,now,bars

def measure_bars(bars,currency):
    need(bool(bars),"EMPTY_BARS")
    prices=[b["close"] for b in bars]
    highs=[b["high"] for b in bars];lows=[b["low"] for b in bars]
    measures={}
    def add(name,period,series,unit):
        value=series[-1]
        need(value is None or math.isfinite(value),"NONFINITE_FEATURE")
        measures[name]={"value":value,"unit":unit,"period":period,"state":"WARMUP" if value is None else "COMPUTED"}
    for period in (5,20,25,50,60,200):
        a=sma(prices,period);add("SMA:"+str(period),period,a,currency)
        # Disparity is 100 at equality, not percent distance from average.
        if a[-1] is not None:need(a[-1]>0,"INVALID_AVERAGE")
        add("DISPARITY:"+str(period),period,[None if a[-1] is None else 100*prices[-1]/a[-1]],"INDEX_BASE_100")
    for period in (12,26):add("EMA:"+str(period),period,ema(prices,period),currency)
    add("RSI:WILDER:14",14,rsi_wilder(prices,14),"INDEX_0_100")
    add("ATR:WILDER:14",14,atr_wilder(highs,lows,prices,14),currency)
    for period in (1,5,20,60,120):
        add("PRICE_RETURN:"+str(period),period,[None if len(prices)<=period else prices[-1]/prices[-1-period]-1],"FRACTION")
    m=macd(prices)
    for k,series in m.items():add("MACD:12:26:9:"+k,26,series,currency)
    bands=bollinger(prices)
    for k,series in bands.items():add("BOLLINGER:20:2:"+k,20,series,"FRACTION" if k=="width" else currency)
    volumes=[b["volume"] for b in bars]
    add("VOLUME_RATIO:20",20,volume_ratio(volumes),"RATIO")
    add("CMF:20",20,cmf(highs,lows,prices,volumes),"FRACTION")
    # Distinguish insufficient observations from a zero-volume denominator.
    for key,n in (("VOLUME_RATIO:20",21),("CMF:20",20)):
        if len(bars)>=n and measures[key]["value"] is None:
            measures[key]["state"]="UNDEFINED_ZERO_VOLUME"
    # Two explicitly provisional groups; not a named strategy or score.
    for periods in ((5,20,60),(20,60,200)):
        tag=":".join(map(str,periods))
        g=ma_geometry(prices,periods,5)
        add("MA_WIDTH:"+tag,max(periods),g["width"],"FRACTION")
        add("MA_WIDTH_DELTA_5:"+tag,5,g["width_change"],"FRACTION_DELTA")
        for n,series in g["slopes"].items():
            add("MA_SLOPE_5:"+str(n),5,series,"FRACTION")
        for pair,series in g["pair_gaps"].items():
            add("MA_PAIR_GAP:"+pair, max(map(int,pair.split(":"))),series,"FRACTION")
    return measures

def build_bundle(db,dataset_id,as_of,plan,*,mode="SYNTHETIC"):
    meta,now,bars=select_bars(db,dataset_id,as_of,plan,mode=mode)
    measures=measure_bars(bars,meta[2])
    plan_hash=digest(plan)
    snapshot={"dataset_id":dataset_id,"asset_id":meta[0],"provider":meta[1],"currency":meta[2],"basis":meta[3],
        "as_of":now.isoformat(),"plan_sha256":plan_hash,"bars":bars}
    return {"schema":VERSION,"mode":mode,"library_version":LIBRARY_VERSION,"snapshot_sha256":digest(snapshot),
        "dataset_id":dataset_id,"asset_id":meta[0],"currency":meta[2],"basis":meta[3],
        "as_of":now.isoformat(),"first_session":bars[0]["session"],"last_session":bars[-1]["session"],
        "input_count":len(bars),"batch_sha256":sorted({b["batch_sha256"] for b in bars}),
        "plan_sha256":plan_hash,"features":measures,"historical_reconstruction":True,
        "independent_calendar_verified":False,"independent_action_verified":False,
        "independent_rights_verified":False,"g0_approved":False,"decision_authorized":False,"order_authorized":False}
