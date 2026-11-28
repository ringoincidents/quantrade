"""Completed higher-timeframe RAW OHLCV aggregation. Research only.

Calendar coverage and action evidence are caller declarations, not independent
exchange verification. Conservative calendar-period closure: next local midnight
after the final calendar day, not merely after the most recent trading session.
"""
from datetime import date,datetime,time,timedelta
from zoneinfo import ZoneInfo
import math
from feature_bridge import (Blocked,need,instant,iso_day,evidence,digest,select_bars,
                            measure_bars,MAX_SESSIONS)
from indicators import LIBRARY_VERSION
VERSION="vault_multiframe.v1"

def bounds(d,frame):
    if frame=="W":
        a=d-timedelta(days=d.weekday())
        return a,a+timedelta(days=6)
    if frame=="M":
        a=d.replace(day=1)
        n=date(a.year+int(a.month==12),a.month%12+1,1)
        return a,n-timedelta(days=1)
    if frame=="Y":
        return date(d.year,1,1),date(d.year,12,31)
    raise Blocked("INVALID_FRAME")

def build_multiframe(db,dataset_id,as_of,plan,frame,*,mode="SYNTHETIC"):
    need(frame in ("W","M","Y"),"INVALID_FRAME")
    now=instant(as_of)
    need(isinstance(plan,dict) and plan.get("dataset_id")==dataset_id,"DATASET_PLAN_MISMATCH")
    need(plan.get("timezone") in ("America/New_York","Asia/Seoul"),"UNSUPPORTED_TIMEZONE")
    need(evidence(plan.get("calendar_ref")) and evidence(plan.get("corporate_action_ref")),"EVIDENCE_MISSING")
    need(plan.get("corporate_action_state")=="NO_ACTIONS_IN_WINDOW","RAW_ACTIONS_UNRESOLVED")
    zone=ZoneInfo(plan["timezone"])
    lo,hi=iso_day(plan.get("coverage_start")),iso_day(plan.get("coverage_end"))
    need(lo<=hi and 1<=lo.year<=hi.year<9999 and (hi-lo).days<=16000,"INVALID_COVERAGE")
    sessions=plan.get("sessions")
    need(isinstance(sessions,list) and 1<=len(sessions)<=MAX_SESSIONS,"INVALID_WINDOW")
    by_period={};last=None
    for item in sessions:
        need(isinstance(item,dict),"INVALID_SESSION")
        d=iso_day(item.get("session"));c=instant(item.get("close_at"))
        need(lo<=d<=hi and c.astimezone(zone).date()==d,"SESSION_OUTSIDE_COVERAGE")
        need(last is None or d>last,"DUPLICATE_OR_UNSORTED_SESSION")
        last=d
        a,_=bounds(d,frame)
        by_period.setdefault(a,[]).append(item)
    accepted=[];excluded=[];cursor=bounds(lo,frame)[0]
    while cursor<=hi:
        a,z=bounds(cursor,frame)
        closed=datetime.combine(z+timedelta(days=1),time.min,tzinfo=zone)
        if a<lo or z>hi:
            excluded.append({"period_start":a.isoformat(),"state":"PARTIAL_COVERAGE"})
        elif now<closed:
            excluded.append({"period_start":a.isoformat(),"state":"PERIOD_NOT_CLOSED"})
        else:
            group=by_period.get(a,[])
            need(bool(group),"EMPTY_DECLARED_PERIOD")
            accepted.append((a,z,group))
        cursor=z+timedelta(days=1)
    need(bool(accepted),"NO_COMPLETED_PERIOD")
    daily_plan={**plan,"sessions":[item for _,_,group in accepted for item in group]}
    meta,_,daily=select_bars(db,dataset_id,as_of,daily_plan,mode=mode)
    lookup={x["session"]:x for x in daily}
    result=[]
    for a,z,group in accepted:
        rows=[lookup[x["session"]] for x in group]
        # Every constituent daily bar is known and latest verified at as_of.
        # The higher-timeframe bar is not usable before calendar-period closure.
        known=max([instant(x["available_at"]) for x in rows]+
                  [datetime.combine(z+timedelta(days=1),time.min,tzinfo=zone)])
        volume=math.fsum(x["volume"] for x in rows)
        need(math.isfinite(volume),"NONFINITE_VOLUME")
        result.append({"period_start":a.isoformat(),"period_end":z.isoformat(),
                       "first_session":rows[0]["session"],"last_session":rows[-1]["session"],
                       "session_count":len(rows),"open":rows[0]["open"],"high":max(x["high"] for x in rows),
                       "low":min(x["low"] for x in rows),"close":rows[-1]["close"],"volume":volume,
                       "available_at":known.isoformat(),"constituent_sha256":digest(rows)})
    return {"schema":VERSION,"mode":mode,"frame":frame,"basis":meta[3],"currency":meta[2],
            "dataset_id":dataset_id,"as_of":now.isoformat(),"library_version":LIBRARY_VERSION,
            "period_count":len(result),"bars":result,"excluded_periods":excluded,
            "features":measure_bars(result,meta[2]),"period_unit":"COMPLETED_"+frame,
            "snapshot_sha256":digest({"frame":frame,"as_of":now.isoformat(),"plan":plan,"bars":result}),
            "independent_calendar_verified":False,"independent_action_verified":False,
            "independent_rights_verified":False,"g0_approved":False,"decision_authorized":False,"order_authorized":False}
