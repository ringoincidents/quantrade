#!/usr/bin/env python3
"""Retrospective SOXL forum-bias audit. Research only, not trading performance."""
import argparse, csv, json
from collections import defaultdict
from pathlib import Path
from statistics import mean
import pandas as pd
import exchange_calendars as xcals

META_STRICT_IDS={'META-005','META-006'}
META_AMBIGUOUS_IDS={'META-004','DC-019'}

def read_csv(path):
    with open(path,encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))

def values(row,horizon):
    r=row.get(f'ret_{horizon}d_pct','')
    return float(r) if r not in ('',None,'nan') else None

def candidate_rows(rows,horizon,layer='meta',strict=False):
    return [r for r in rows if r['layer']==layer and int(r['net_direction'])!=0
            and values(r,horizon) is not None
            and (not strict or '1vay6w3' in r.get('source_url','') or '1wvx45p' in r.get('source_url',''))]

def score(rows,horizon,min_move=0):
    vals=[(int(r['net_direction']),values(r,horizon)) for r in rows
          if values(r,horizon) is not None and int(r['net_direction'])!=0]
    return {'n':len(vals),'direction_matches':sum(d*v>0 for d,v in vals),
            'threshold_matches':sum(d*v>=min_move if min_move>0 else d*v>0 for d,v in vals),
            'always_long_matches':sum(v>0 for d,v in vals),
            'always_short_matches':sum(v<0 for d,v in vals),
            'expected_directional_return_mean_pct':round(mean(d*v for d,v in vals),4) if vals else None,
            'note':'Descriptive signed future-price change, NOT an executable strategy return'}

def calendar_clusters(rows,horizon=5):
    if not rows:return []
    anchor=sorted({r['anchor_date'] for r in rows if r.get('anchor_date')})
    cal=xcals.get_calendar('XNYS')
    sessions=[x.date().isoformat() for x in cal.sessions_in_range(pd.Timestamp(min(anchor)),pd.Timestamp(max(anchor)))]
    index={d:i for i,d in enumerate(sessions)}
    clusters=[]
    for date in anchor:
        if not clusters or index[date]-index[clusters[-1][-1]]>horizon:clusters.append([date])
        else:clusters[-1].append(date)
    return clusters

def date_aggregate(rows,horizon):
    groups=defaultdict(list)
    for r in rows:
        if values(r,horizon) is not None:groups[(r['published_date_et'],r['layer'])].append(r)
    out=[]
    for key,rr in sorted(groups.items()):
        if len({values(r,horizon) for r in rr})!=1:raise AssertionError('Same-date contradictory prices')
        total=sum(int(r['net_direction']) for r in rr)
        row=rr[0].copy()
        row['net_direction']=1 if total>0 else -1 if total<0 else 0
        row['thread_count']=len(rr);out.append(row)
    return out

def report(rows):
    meta=[r for r in rows if r['layer']=='meta' and values(r,1) is not None]
    if len(meta)!=4:raise ValueError('Evolved source samples require new human audit')
    result={'status':'RETROSPECTIVE_BIAS_AUDIT_NOT_A_TRADING_BACKTEST',
            'source':'2026-10-17 hand-curated thread-day outcomes',
            'first_seen_historically_verified':0,
            'meta_categories':{'strict_future':{'ids':sorted(META_STRICT_IDS),'n':2},
              'ambiguous_or_retrospective':{'ids':sorted(META_AMBIGUOUS_IDS),'n':2}},
            'horizons':{},
            'red_flags':['Four meta examples occupy just two overlapping 5-day price-event clusters.',
                         'Two claimed 1-day correct directions move less than 1% in anticipated direction.',
                         'Retrospective forecaster praise and skeptical question are not future predictions.',
                         'Multiple same-date forum threads share identical market prices.',
                         'No original first-seen timestamps or probability-based source sampling.',
                         'Retrospective keyword discovery prevents alpha or causal inference.']}
    for h in (1,3,5):
        m=candidate_rows(rows,h)
        s=candidate_rows(rows,h,strict=True)
        d=candidate_rows(rows,h,layer='direct')
        both={r['published_date_et'] for r in m}&{r['published_date_et'] for r in d}
        result['horizons'][str(h)]={
          'meta_all_descriptive':score(m,h,1),
          'meta_strict_only':score(s,h,1),
          'direct_thread_day_descriptive':score(d,h,1),
          'direct_publication_day_collapsed':score(date_aggregate(d,h),h,1),
          'meta_unique_publication_dates':len({r['published_date_et'] for r in m}),
          'paired_meta_and_direct_publication_dates':sorted(both),
          'meta_overlapping_clusters_window_5d':calendar_clusters(m,5),
          'meta_overlapping_cluster_count':len(calendar_clusters(m,5))}
    return result

def main():
    ap=argparse.ArgumentParser();ap.add_argument('csv');ap.add_argument('--output');a=ap.parse_args()
    s=json.dumps(report(read_csv(a.csv)),indent=2,ensure_ascii=False)+'\n'
    if a.output:Path(a.output).write_text(s,encoding='utf-8')
    print(s)

if __name__=='__main__':main()
