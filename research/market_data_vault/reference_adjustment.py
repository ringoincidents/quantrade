"""Bounded calendar reference and split-only historical research adjustment.
No external data fetch, no independent calendar/rights/corporate-action attestation.
"""
from datetime import timedelta
from fractions import Fraction
from math import isfinite
from zoneinfo import ZoneInfo
from quantrade.workbench.session_calendar import START,END,VERSION as CALENDAR_VERSION,us_scheduled_session
from feature_bridge import (_select_raw_bars,select_bars,measure_bars,instant,iso_day,need,digest,evidence,Blocked)
from indicators import LIBRARY_VERSION

VERSION="reference_calendar_split.v1"
PIN="f64b61c088a8e17cb04617f95d4f458671bea602"

def reference_plan(dataset_id,market,start,end,as_of,action_ref,*,split=False):
    lo,hi=iso_day(start),iso_day(end);now=instant(as_of)
    need(market in ("XNYS","XNAS"),"CALENDAR_MARKET_UNVERIFIED")
    need(START<=lo<=hi<=END,"CALENDAR_OUTSIDE_COVERAGE")
    need(evidence(action_ref) and evidence(dataset_id),"EVIDENCE_MISSING")
    sessions=[];closed=[]
    for i in range((hi-lo).days+1):
        day=lo+timedelta(days=i);s=us_scheduled_session(market,day)
        if s is None:closed.append(day.isoformat());continue
        need(s.close_at<=now,"SESSION_NOT_COMPLETED")
        sessions.append({"session":day.isoformat(),"close_at":s.close_at.isoformat()})
    need(bool(sessions),"NO_COMPLETED_SESSION")
    return {"dataset_id":dataset_id,"market":market,"timezone":"America/New_York",
        "coverage_start":start,"coverage_end":end,"calendar_ref":"F08:"+PIN+":"+CALENDAR_VERSION,
        "calendar_version":CALENDAR_VERSION,"closed_dates":closed,"sessions":sessions,
        "corporate_action_ref":action_ref,"corporate_action_state":"SPLIT_TRANSFORM_REQUIRED" if split else "NO_ACTIONS_IN_WINDOW"}

def action_events(manifest,plan,as_of):
    now=instant(as_of)
    need(isinstance(manifest,dict),"INVALID_ACTION_MANIFEST")
    need(manifest.get("schema")=="qt-split-manifest-v1" and manifest.get("dataset_id")==plan["dataset_id"],"ACTION_IDENTITY_MISMATCH")
    need(manifest.get("coverage_start")==plan["coverage_start"] and manifest.get("coverage_end")==plan["coverage_end"],"ACTION_COVERAGE_MISMATCH")
    need(manifest.get("source_ref")==plan["corporate_action_ref"] and manifest.get("coverage_state")=="ALL_ACTIONS_DECLARED","ACTION_COVERAGE_UNVERIFIED")
    need(instant(manifest.get("coverage_known_at"))<=now,"ACTION_COVERAGE_NOT_KNOWN")
    # All actions, not only split events, must be declared. Dividends and other
    # actions deliberately block this split-only path.
    events=manifest.get("events")
    need(isinstance(events,list) and len(events)<=100,"INVALID_ACTION_EVENTS")
    accepted={};sessions={s["session"]:instant(s["close_at"]) for s in plan["sessions"]}
    for e in events:
        need(isinstance(e,dict) and e.get("kind")=="SPLIT","UNSUPPORTED_CORPORATE_ACTION")
        day=e.get("effective_session")
        need(isinstance(day,str) and day in sessions and day not in accepted,"ACTION_SESSION_INVALID_OR_DUPLICATE")
        need(evidence(e.get("event_ref")),"ACTION_EVENT_EVIDENCE_MISSING")
        known=instant(e.get("first_known_at"))
        need(known<=now,"ACTION_NOT_KNOWN_AS_OF")
        # A split must be effective for the completed session's bar, not
        # merely an announced future action. Scope assumes open-effective.
        need(e.get("effective_basis")=="BEFORE_SESSION_OPEN","UNSUPPORTED_EFFECTIVE_BASIS")
        new,old=e.get("new_shares"),e.get("old_shares")
        need(type(new) is int and type(old) is int and 1<=new<=10000 and 1<=old<=10000 and new!=old,"INVALID_SPLIT_RATIO")
        accepted[day]=(Fraction(new,old),known)
    return accepted

def adjusted_bars(bars,events):
    out=[]
    for bar in bars:
        f=Fraction(1)
        for day,(ratio,_) in events.items():
            if bar["session"]<day:f*=ratio
        row=dict(bar)
        try:
            for k in ("open","high","low","close"):row[k]=float(Fraction(str(bar[k]))/f)
            row["volume"]=float(Fraction(str(bar["volume"]))*f)
        except (OverflowError,ValueError,ZeroDivisionError):raise Blocked("INVALID_ADJUSTED_VALUE") from None
        need(all(isfinite(row[k]) and row[k]>0 for k in ("open","high","low","close")) and isfinite(row["volume"]) and row["volume"]>=0,"INVALID_ADJUSTED_VALUE")
        need(row["low"]<=min(row["open"],row["close"])<=max(row["open"],row["close"])<=row["high"],"INVALID_ADJUSTED_OHLC")
        row["split_factor_new_over_old"]=str(f);out.append(row)
    return out

def build_reference_bundle(db,dataset_id,market,start,end,as_of,manifest,*,mode="SYNTHETIC"):
    need(isinstance(manifest,dict),"INVALID_ACTION_MANIFEST")
    plan=reference_plan(dataset_id,market,start,end,as_of,manifest.get("source_ref"),split=True)
    events=action_events(manifest,plan,as_of)
    meta,now,raw=_select_raw_bars(db,dataset_id,as_of,plan,mode=mode,split_transform=True)
    # Identity binding is explicit, not inferred from ticker name.
    need(manifest.get("asset_id")==meta[0] and manifest.get("market")==market,"ACTION_IDENTITY_MISMATCH")
    rows=adjusted_bars(raw,events)
    snapshot={"dataset_id":dataset_id,"asset_id":meta[0],"provider":meta[1],"currency":meta[2],"as_of":now.isoformat(),"plan":plan,"raw":raw,"actions":manifest}
    return {"schema":VERSION,"mode":mode,"dataset_id":dataset_id,"market":market,
        "calendar_version":CALENDAR_VERSION,"calendar_pin":PIN,"plan":plan,"basis":"SPLIT_ADJUSTED_PRICE_ONLY",
        "library_version":LIBRARY_VERSION,"snapshot_sha256":digest(snapshot),"bars":rows,
        "features":measure_bars(rows,meta[2]),"split_count":len(events),
        "independent_calendar_verified":False,"independent_action_verified":False,
        "total_return":False,"g0_approved":False,"decision_authorized":False,"order_authorized":False}
