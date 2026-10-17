#!/usr/bin/env python3
"""Price-episode / manually annotated public discussion pilot.

No social price prediction is tested. All sample discussions have day-only
publication precision and unknown first-observation time. This pilot reports
ONLY qualitative patterns and missingness in retrospectively selected cases.
"""
import csv
import json
import argparse
from pathlib import Path
from statistics import mean


def rows(path):
    with Path(path).open(encoding='utf-8-sig', newline='') as f:
        return list(csv.DictReader(f))


def run(price_path, events_path, samples_path):
    price=rows(price_path)
    events=rows(events_path)
    posts=rows(samples_path)
    dates=[r['date'] for r in price]
    if len(dates) != len(set(dates)) or dates != sorted(dates):
        raise ValueError('Price dates must be unique ascending sessions')
    index={d:i for i,d in enumerate(dates)}
    if any(float(p['close']) <= 0 for p in price):
        raise ValueError('Invalid price')
    if len(posts) != len({p['sample_id'] for p in posts}):
        raise ValueError('duplicate sample ID')
    if any(p['stance'] not in ('-1','0','1') for p in posts):
        raise ValueError('unexpected stance')
    if any(p['predictive_eligible'] == 'true' and p['precision'] != 'timestamp_utc'
           for p in posts):
        raise ValueError('date-only content CANNOT be predictive eligible')
    out=[]
    for e in events:
        if e['first_session'] not in index or e['last_session'] not in index:
            raise ValueError('missing event session')
        start=index[e['first_session']]; end=index[e['last_session']]
        if end < start: raise ValueError('event is backwards')
        phase_dates={
            'before':set(dates[max(0,start-5):start]),
            'during':set(dates[start:end+1]),
            'after':set(dates[end+1:min(len(dates),end+6)])
        }
        phase_detail={}
        for phase,ds in phase_dates.items():
            matches=[p for p in posts if p['posted_date_et'] in ds]
            b=sum(p['stance']=='1' for p in matches)
            r=sum(p['stance']=='-1' for p in matches)
            neutral=len(matches)-b-r
            phase_detail[phase]={
                'sessions_observed':len(ds),
                'requested_sessions':end-start+1 if phase=='during' else 5,
                'observations':len(matches),
                'bullish':b,'bearish':r,'neutral':neutral,
                'balance_bull_minus_bear':round((b-r)/(b+r),3) if b+r else None,
                'missing_posts_not_zero_sentiment':len(matches)==0,
                'returns_as_of_only':False
            }
        before_index=start-1 if start>0 else None
        before_close=float(price[before_index]['close']) if before_index is not None else None
        end_close=float(price[end]['close'])
        start_close=float(price[start]['close'])
        out.append({
            'event_id':e['event_id'], 'kind':e['kind'],
            'selection':'RETROSPECTIVE_CASE_STUDY_NOT_RANDOM',
            'start':e['first_session'], 'end':e['last_session'],
            'start_to_end_change_pct':round((end_close/start_close-1)*100,2),
            'pre_start_close_to_end_change_pct':round((end_close/before_close-1)*100,2) if before_close else None,
            'phases':phase_detail,
            'complete_after_window':len(phase_dates['after'])==5
        })
    # Deliberately refuses to present a correlation or p-value based on pseudo-independent comments.
    return {'status':'DESCRIPTIVE_ONLY_NO_PREDICTION_NO_CAUSALITY',
            'data': {'price_sessions':len(price),'curated_posts':len(posts),
                     'exact_timestamps':sum(p['precision']=='timestamp_utc' for p in posts),
                     'predictive_eligible':sum(p['predictive_eligible']=='true' for p in posts),
                     'sources':sorted(set(p['platform'] for p in posts))},
            'nonrepresentative_note':'Hand-selected reddit items and curated events. Posts in same thread are correlated. Date-only publication precision cannot establish price-leading order.',
            'events':out}


def main():
    root=Path(__file__).resolve().parent
    parser=argparse.ArgumentParser()
    parser.add_argument('--price',type=Path,default=root/'soxl_daily_2026_selected.csv')
    parser.add_argument('--events',type=Path,default=root/'events_curated_v0.csv')
    parser.add_argument('--posts',type=Path,default=root/'manual_samples_v0.csv')
    parser.add_argument('--out',type=Path,default=root/'pilot_results.json')
    args=parser.parse_args()
    r=run(args.price,args.events,args.posts)
    args.out.write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'status':r['status'],'price_sessions':r['data']['price_sessions'],
        'curated_posts':r['data']['curated_posts'],
        'episodes':[(x['event_id'],{k:v['observations'] for k,v in x['phases'].items()}) for x in r['events']]},ensure_ascii=False,indent=2))

if __name__=='__main__':
    main()