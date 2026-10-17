#!/usr/bin/env python3
"""QuanTrade social/price feasibility probe. Standard library; no network/API calls.

Accepted inputs are rights-cleared structured annotations, not scraped post text.
Only a post first observed >=15 min before next US market open may contribute.
Price labels are next open-to-close, NOT the already-known past trading day.
All correlations are exploratory, not trading alpha or causal inference.
"""
import argparse
import csv
import datetime as dt
import json
from pathlib import Path
from statistics import mean

UTC = dt.timezone.utc


def utc_time(s):
    if not s: raise ValueError('Timestamp missing: unknown must remain unknown')
    x = dt.datetime.fromisoformat(s.replace('Z','+00:00'))
    if x.tzinfo is None: raise ValueError('Timezone-naive timestamp')
    return x.astimezone(UTC)


def read_csv(path):
    with open(path, encoding='utf-8-sig', newline='') as f:
        return list(csv.DictReader(f))


def pilot_labels(path):
    rows = read_csv(path)
    evaluated = []
    for r in rows:
        label = r['human_direction']
        if label not in ('-1','0','1'): raise ValueError('invalid human_direction')
        score = float(r['third_party_sentiment_score'])
        vendor_direction = 1 if score > 0.2 else (-1 if score < -0.2 else 0)
        if int(label) != 0:
            evaluated.append(int(label) == vendor_direction)
    return {'status': 'CURATED_NONRANDOM_LABEL_QUALITY_ONLY',
            'examples': len(rows), 'directional_labeled': len(evaluated),
            'agreement_on_directional_items': sum(evaluated),
            'future_return_predictions_tested': 0,
            'warning': 'selection biased, date-only timestamps, not OOS evidence'}


def prospective_features(posts, bars, lookback_hours=72):
    checked = []
    for p in posts:
        if p.get('ticker','').upper() != 'SOXL': continue
        if p.get('direction') not in ('-1','0','1'):
            raise ValueError('direction must be -1, 0, or 1')
        a,b=utc_time(p['published_utc']),utc_time(p['first_seen_utc'])
        if b < a: raise ValueError('first_seen precedes publication')
        checked.append((max(a,b),int(p['direction']),p['platform'],p.get('source_kind','community')))
    out=[]
    for bar in bars:
        open_time=utc_time(bar['open_utc']); close_time=utc_time(bar['close_utc'])
        if close_time <= open_time: raise ValueError('close before open')
        cutoff=open_time - dt.timedelta(minutes=15)
        lo=cutoff-dt.timedelta(hours=lookback_hours)
        rows=[r for r in checked if lo <= r[0] <= cutoff]
        vals=[r[1] for r in rows]
        news=[r[1] for r in rows if r[3]=='news']
        community=[r[1] for r in rows if r[3]=='community']
        def intraday(t):
            a,b=float(bar[t+'_open']),float(bar[t+'_close'])
            if a<=0 or b<=0: raise ValueError('Invalid prices')
            return round((b/a-1)*100,5)
        out.append({'session_date':bar['session_date'],
                    'cutoff_utc':cutoff.isoformat(),
                    'n_messages':len(rows),'n_news':len(news),'n_community':len(community),
                    'direction_mean':round(mean(vals),5) if vals else None,
                    'community_mean':round(mean(community),5) if community else None,
                    'news_mean':round(mean(news),5) if news else None,
                    'disagreement':round(2*min(vals.count(-1),vals.count(1))/len(vals),5) if vals else None,
                    'soxl_intraday_return_pct':intraday('soxl'),
                    'qqq_intraday_return_pct':intraday('qqq')})
    return out


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--pilot',type=Path)
    parser.add_argument('--posts',type=Path)
    parser.add_argument('--bars',type=Path)
    args=parser.parse_args()
    if args.pilot:
        print(json.dumps(pilot_labels(args.pilot),ensure_ascii=False,indent=2))
    if args.posts and args.bars:
        result=prospective_features(read_csv(args.posts),read_csv(args.bars))
        print(json.dumps({'status':'FEATURE_ALIGNMENT_ONLY_NOT_STRATEGY_VALIDATION',
                          'sessions':len(result), 'records':result,
                          'inferential_status':'NOT_TESTED - requires more independent sessions, controls, and holdout'},ensure_ascii=False,indent=2))
    elif bool(args.posts) != bool(args.bars):
        parser.error('both --posts and --bars required')
    if not (args.pilot or args.posts):
        parser.error('provide --pilot or --posts/--bars')


if __name__=='__main__': main()
