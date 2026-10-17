#!/usr/bin/env python3
"""Retrospective forum claims versus selected SOXL closes: NOT INVESTABLE.

Publication *dates only* or true first-seen are absent. Thus this is an
ex-post descriptive check, not historical tradable alpha or statistical test.

For maximum conservatism under date-only publication, compute from the close
of the FIRST TRADING SESSION STRICTLY AFTER the publication ET date. Future
+1/+3/+5 sessions are computed only if *every intervening NYSE session* has
price coverage; no fills/FX/fees. Thread-date dependence is reported.
"""
import argparse
import csv
import datetime as dt
import json
from pathlib import Path
from collections import defaultdict,Counter
from statistics import mean,median

import exchange_calendars as xcals
import pandas as pd

CAL=xcals.get_calendar('XNYS')

def read_csv(f):
    with open(f,encoding='utf-8-sig',newline='') as handle:return list(csv.DictReader(handle))

def session_dates(start,end):
    return [x.date().isoformat() for x in CAL.sessions_in_range(pd.Timestamp(start),pd.Timestamp(end))]

def read_price(f):
    rows=read_csv(f); table={}
    for r in rows:
        d=r['date'];v=float(r['close'])
        if v<=0 or d in table:raise ValueError('bad/duplicate price '+d)
        table[d]=v
    return table

def load_claims(reddit_path,meta_path):
    out=[]
    for r in read_csv(reddit_path):
        val=int(r['stance'])
        if val not in (-1,0,1):raise ValueError('bad stance')
        out.append(dict(id=r['sample_id'],platform='reddit',date=r['posted_date_et'],thread=r['thread_url'],layer='direct',direction=val,category=r['notes'],first_seen_verified=False,selection='retrospective'))
    for r in read_csv(meta_path):
        if r['first_seen_historically_verified'].lower()!='false':raise ValueError('future eligible? forbidden in retrospective report')
        val=int(r['direction'])
        if val not in (-1,1):raise ValueError('bad meta direction')
        out.append(dict(id=r['claim_id'],platform=r['platform'],date=r['post_date_et'],thread=r['thread_url'],layer=r['discourse_layer'],direction=val,category=r['category'],first_seen_verified=False,selection='retrospective'))
    return out

def run(prices,claims,horizons=(1,3,5)):
    if not prices:return None
    maxh=max(horizons)
    calendar=session_dates(min(prices),max(prices))
    idx={d:i for i,d in enumerate(calendar)}
    records=[]
    for c in claims:
        # exact clock timestamps NOT available; never pretend entry same day
        first_later = next((i for i,d in enumerate(calendar) if d>c['date']),None)
        row={**c,'anchor_date':None,'anchor_price':None,'eligible_for_live_replay':False,'missing_reason':None}
        if first_later is None:
            row['missing_reason']='publication_after_last_available_session'
        elif calendar[first_later] not in prices:
            row['missing_reason']='first_later_session_missing_from_prices'
        else:
            row['anchor_date']=calendar[first_later]
            row['anchor_price']=prices[calendar[first_later]]
        for n in horizons:
            value=None
            if row['anchor_date'] is not None and first_later+n<len(calendar):
                segment=calendar[first_later:first_later+n+1]
                if all(d in prices for d in segment):
                    value=(prices[segment[-1]]/row['anchor_price']-1)*100
            row[f'return_{n}d_pct']=None if value is None else round(value,4)
            row[f'correct_{n}d']=None if value is None or c['direction']==0 else int(value*c['direction']>0)
        records.append(row)
    groups={}
    for c in records:
        k=(c['platform'],c['thread'],c['date'],c['layer'])
        groups.setdefault(k,[]).append(c)
    collapsed=[]
    for k,rs in groups.items():
        signs=[r['direction'] for r in rs if r['direction']]
        consensus=sum(signs)
        sign=0 if consensus==0 else (1 if consensus>0 else -1)
        r={'platform':k[0],'thread':k[1],'post_date_et':k[2],'layer':k[3],
           'n_claims':len(rs),'bullish':signs.count(1),'bearish':signs.count(-1),
           'net_direction':sign,'anchor_date':rs[0]['anchor_date']}
        for n in horizons:
            val=rs[0][f'return_{n}d_pct']
            r[f'return_{n}d_pct']=val
            r[f'correct_{n}d']=None if val is None or sign==0 else int(sign*val>0)
        collapsed.append(r)
    def metric(a,n):
        valid=[r for r in a if r.get(f'correct_{n}d') is not None]
        return {'n_evaluable_directional_units':len(valid),
                'n_directionally_correct':sum(r[f'correct_{n}d'] for r in valid),
                'hit_rate_descriptive':round(mean([r[f'correct_{n}d'] for r in valid]),4) if valid else None,
                'median_market_return_pct':round(median([r[f'return_{n}d_pct'] for r in valid]),3) if valid else None}
    summary={'status':'RETROSPECTIVE_SELECTED_CLAIMS_NOT_TRADABLE_NOT_STATISTICALLY_VALIDATED',
             'price_sessions_available':len(prices),'data_gaps_preserved':True,
             'claims_total':len(records),'independent_thread_dates_NOT_established':True,
             'all_historical_first_seen_verified_count':0,
             'units_collapsed_by_platform_thread_date_layer':len(collapsed),
             'hypothetical_close_anchor':'first later NYSE trading session close (not an executable tested order)',
             'group_summary':{layer:{str(n):metric([x for x in collapsed if x['layer']==layer],n) for n in horizons} for layer in ['direct','meta']},
             'warning':'No population random sampling, first-seen timestamps, independent event clusters, or authorized historical action.'}
    return summary,records,collapsed

def write_csv(path,rows):
    if not rows:raise ValueError('no rows')
    with open(path,'w',encoding='utf-8',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0].keys()));w.writeheader();w.writerows(rows)

def main():
    p=argparse.ArgumentParser();p.add_argument('--prices',required=True);p.add_argument('--reddit',required=True);p.add_argument('--claims',required=True);p.add_argument('--out',required=True)
    a=p.parse_args();Path(a.out).mkdir(parents=True,exist_ok=True)
    prices=read_price(a.prices);claims=load_claims(a.reddit,a.claims)
    summary,raw,collapsed=run(prices,claims)
    write_csv(Path(a.out)/'claim_outcomes.csv',raw)
    write_csv(Path(a.out)/'thread_day_outcomes.csv',collapsed)
    (Path(a.out)/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(summary,ensure_ascii=False,indent=2))

if __name__=='__main__':main()