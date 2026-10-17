#!/usr/bin/env python3
"""Rights-aware forum research snapshot validator, standard library only.

Does not fetch pages. Inputs are human-vetted observations and documented search
attempts. Never interprets search-engine non-results as zero forum posts.
"""
import csv, json, argparse
from collections import Counter
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ALLOWED = {'stockus','krstock','tenbagger'}
ALIASES = {'SOXL','속슬','속쓸'}
PHASES = {'bullish','bearish','neutral','ambiguous'}
STATUS = {'NO_SAME_DAY_VERIFIED','FOUND','INCOMPLETE','BLOCKED'}


def iso(s):
    if not s: raise ValueError('missing timestamp')
    x=datetime.fromisoformat(s.replace('Z','+00:00'))
    if x.tzinfo is None: raise ValueError('naive timestamp forbidden')
    return x


def load(path):
    with Path(path).open(encoding='utf-8-sig',newline='') as f:
        return list(csv.DictReader(f))


def analyze(attempts, observations, asof):
    cutoff=iso(asof)
    keys=set(); per={v:[] for v in ALLOWED}
    for row in attempts:
        if row['gallery'] not in ALLOWED or row['alias'] not in ALIASES: raise ValueError('unsupported gallery/alias')
        key=(row['gallery'],row['alias'])
        if key in keys: raise ValueError('duplicate search attempt')
        keys.add(key)
        if row['status'] not in STATUS: raise ValueError('unknown status')
        if iso(row['queried_at_utc']) > cutoff: raise ValueError('future query')
        if row['method']!='web_search_engine': raise ValueError('wrong method')
        # A search engine cannot establish full forum coverage.
        if row['exhaustive'].lower()!='false': raise ValueError('search-engine coverage cannot be exhaustive')
    if keys != {(g,a) for g in ALLOWED for a in ALIASES}: raise ValueError('missing fixed-query attempt')

    urls=set(); prospective=0
    for r in observations:
        if r['gallery'] not in ALLOWED: raise ValueError('unknown source gallery')
        if r['post_url'] in urls: raise ValueError('duplicate post URL')
        urls.add(r['post_url'])
        if r['direction'] not in PHASES: raise ValueError('unknown stance')
        publish=iso(r['published_at_kst'])
        seen=iso(r['first_seen_at_utc'])
        if publish > seen: raise ValueError('first seen before published')
        if seen > cutoff: raise ValueError('not yet observed at snapshot')
        if r['collection_method'] not in {'retrospective_search','prospective_authorized'}: raise ValueError('unapproved method')
        if r['eligible_for_forward_test'].lower()=='true':
            if r['collection_method']!='prospective_authorized': raise ValueError('retrospective source cannot be predictive')
            if r['time_precision'] not in {'second','minute'}: raise ValueError('unreliable timestamp')
            prospective+=1
        per[r['gallery']].append(r)
    gallery_summary={}
    for g in sorted(ALLOWED):
        a=[x for x in attempts if x['gallery']==g]
        subset=per[g]
        same_day=[x for x in subset if iso(x['published_at_kst']).astimezone(ZoneInfo('Asia/Seoul')).date()==cutoff.astimezone(ZoneInfo('Asia/Seoul')).date()]
        gallery_summary[g]={
            'fixed_alias_queries':len(a), 'verified_new_posts_today':len(same_day),
            'added_historical_sources':len(subset)-len(same_day),
            'population_sentiment':'UNKNOWN', 'full_index_coverage':False,
            'reason':'Search results are incomplete and older posts may appear despite date filters.'
        }
    return {'asof_utc':cutoff.astimezone(ZoneInfo('UTC')).isoformat(),
            'status':'DISCOVERY_SNAPSHOT_NOT_POLL',
            'fixed_queries_attempted':len(attempts),
            'new_verified_same_day_posts':sum(v['verified_new_posts_today'] for v in gallery_summary.values()),
            'qualitative_historical_sources_added':len(observations)-sum(v['verified_new_posts_today'] for v in gallery_summary.values()),
            'forward_eligible_records':prospective,
            'gallery_coverage':gallery_summary,
            'soxl_market_session_status':'WEEKEND_CLOSED' if cutoff.astimezone(ZoneInfo('America/New_York')).weekday()>=5 else 'CHECK_EXCHANGE_CALENDAR',
            'interpretation':'No current-day posts verified in this limited search; NOT evidence of zero posts or neutral sentiment.',
            'alpha_validation':'NOT_TESTED'}


def main():
    p=argparse.ArgumentParser();p.add_argument('--attempts',required=True);p.add_argument('--observations',required=True)
    p.add_argument('--asof',required=True);p.add_argument('--output');a=p.parse_args()
    r=analyze(load(a.attempts),load(a.observations),a.asof)
    s=json.dumps(r,ensure_ascii=False,indent=2)+'\n'
    if a.output: Path(a.output).write_text(s,encoding='utf-8')
    print(s)


if __name__=='__main__':main()
