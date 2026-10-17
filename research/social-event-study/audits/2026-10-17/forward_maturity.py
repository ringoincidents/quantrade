#!/usr/bin/env python3
"""Paper-only future SOXL open-to-close outcome maturity evaluator.

NO platform API, orders, accounts or execution. Use authoritative NYSE
sessions and fully observed verified historical bars. Synthetic test only.
"""
import datetime as dt
import pandas as pd
import exchange_calendars as xcals

UTC=dt.timezone.utc
CAL=xcals.get_calendar('XNYS')

def tm(s):
    if not s:raise ValueError('timestamp missing')
    t=dt.datetime.fromisoformat(s.replace('Z','+00:00'))
    if t.tzinfo is None:raise ValueError('naive timestamp forbidden')
    return t.astimezone(UTC)

def session_list(cutoff,evaluation_asof,horizon=5):
    first=tm(cutoff)+dt.timedelta(minutes=15)
    last=tm(evaluation_asof)
    if last<first:return []
    start=(first-dt.timedelta(days=1)).date().isoformat()
    end=(last+dt.timedelta(days=7)).date().isoformat()
    dates=CAL.sessions_in_range(pd.Timestamp(start),pd.Timestamp(end))
    futures=[]
    for session in dates:
        op=CAL.session_open(session).to_pydatetime().astimezone(UTC)
        if op>first:
            futures.append((session.date().isoformat(),op,CAL.session_close(session).to_pydatetime().astimezone(UTC)))
        if len(futures)>=horizon:break
    return futures

def paper_horizon(signal,bar_rows,evaluation_asof,horizons=(1,3,5)):
    if signal.get('state')!='FEATURES_ONLY_NO_TRADE':
        return {'status':'NO_SIGNAL','horizons':{}}
    frozen=tm(signal.get('features_locked_at_utc'))
    decision=tm(signal.get('decision_cutoff_utc'))
    asof=tm(evaluation_asof)
    if frozen>decision-dt.timedelta(minutes=15):
        return {'status':'INVALID_FEATURE_LOCK','horizons':{}}
    if not all(isinstance(h,int) and 0<h<=20 for h in horizons):
        raise ValueError('invalid horizons')
    sessions=session_list(signal['decision_cutoff_utc'],evaluation_asof,max(horizons))
    by_date={}
    for row in bar_rows:
        d=row.get('session_date')
        if d in by_date:raise ValueError('duplicate session')
        by_date[d]=row
    output={}
    for h in horizons:
        s=sessions[:h]
        if len(s)<h or s[-1][2]>asof:
            output[str(h)]={'state':'AWAITING_FUTURE_CLOSE'};continue
        missing=[d for d,_,_ in s if d not in by_date]
        if missing:
            output[str(h)]={'state':'MISSING_SESSION_PRICE','missing':missing};continue
        for date,op,cl in s:
            row=by_date[date]
            if row.get('source_verified') is not True or row.get('corporate_actions_verified') is not True:
                output[str(h)]={'state':'UNVERIFIED_PRICE_SOURCE','date':date};break
            if abs((tm(row['session_open_utc'])-op).total_seconds())>60 or abs((tm(row['session_close_utc'])-cl).total_seconds())>60:
                output[str(h)]={'state':'CLOCK_DISAGREEMENT','date':date};break
            first_seen=tm(row['price_first_observed_utc'])
            if first_seen>asof or first_seen<cl:
                output[str(h)]={'state':'INVALID_PRICE_OBSERVATION_TIME','date':date};break
            if float(row['open'])<=0 or float(row['close'])<=0:
                output[str(h)]={'state':'INVALID_PRICE','date':date};break
        else:
            a=float(by_date[s[0][0]]['open'])
            b=float(by_date[s[-1][0]]['close'])
            output[str(h)]={'state':'PAPER_OUTCOME_ONLY',
              'start_session':s[0][0],'end_session':s[-1][0],
              'ideal_open_to_close_return_pct':round((b/a-1)*100,5),
              'note':'Not executable PnL: no broker order, slippage, bid-ask, costs'}
    return {'status':'PAPER_ONLY_NOT_ALPHA','horizons':output,
      'data_policy':'No future prices, calendar gaps or unverified first-seen data'}
