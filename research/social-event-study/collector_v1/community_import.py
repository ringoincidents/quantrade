#!/usr/bin/env python3
"""Manual or rights-cleared forum annotations; no site access or forum scraping."""
import argparse,csv,datetime as dt,hashlib,json
from pathlib import Path
PLATFORMS={'dc_stockus','dc_krstock','dc_tenbagger','reddit_soxl','reddit_wsb',
           'reddit_other','stocktwits_soxl','other_public_forum'}
LEVELS={'L1','L2','L3','UNCERTAIN'}
DIRECTION={'bullish','bearish','neutral','ambiguous','conditional'}

def parse_time(s):
 if not s:return None
 x=dt.datetime.fromisoformat(s.replace('Z','+00:00'))
 if x.tzinfo is None:raise ValueError('timestamp timezone required')
 return x.astimezone(dt.timezone.utc)

def record(r,seen):
 url=r['source_url']
 if not url.startswith(('https://','http://')):raise ValueError('bad source URL')
 key=hashlib.sha256(url.encode('utf-8')).hexdigest()
 if key in seen:raise ValueError('duplicate source URL')
 seen.add(key)
 if r['platform'] not in PLATFORMS:raise ValueError('unrecognized source')
 if r['level'] not in LEVELS or r['direction'] not in DIRECTION:raise ValueError('invalid label')
 seen_at=parse_time(r.get('first_observed_utc'))
 published=parse_time(r.get('published_utc'))
 label_at=parse_time(r.get('label_locked_utc'))
 if seen_at and published and seen_at<published:raise ValueError('observed before published')
 if label_at and seen_at and label_at<seen_at:raise ValueError('label predates source observation')
 if r.get('collection_mode') not in ('retrospective_manual','authorized_manual_live'):raise ValueError('invalid collection mode')
 if r.get('rights_status') not in ('public_link_only','authorized_metadata'):raise ValueError('unknown source rights')
 return {'source_url':url,'url_sha256':key,'platform':r['platform'],
  'discourse_level':r['level'],'implied_direction':r['direction'],
  'category':r.get('category',''),'short_paraphrase':r.get('short_paraphrase','')[:250],
  'published_utc':published.isoformat() if published else None,
  'first_observed_utc':seen_at.isoformat() if seen_at else None,
  'label_locked_utc':label_at.isoformat() if label_at else None,
  'collection_mode':r['collection_mode'],'rights_status':r['rights_status'],
  'representative_population':False,'predictive_eligible':False,
  'warning':'Manual case selection has no complete population sample frame.'}

def ingest(path,outpath):
 with Path(path).open(encoding='utf-8-sig',newline='') as f:rows=list(csv.DictReader(f))
 records=[];seen=set()
 for r in rows:records.append(record(r,seen))
 result={'status':'NONRANDOM_QUALITATIVE_ONLY','sources':records,'n':len(records),
  'predictive_eligible_n':0,'warning':'Retrospective forum cases cannot become tradable signals.'}
 Path(outpath).parent.mkdir(parents=True,exist_ok=True)
 Path(outpath).write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
 return result

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('csv');p.add_argument('--out',required=True)
 a=p.parse_args();print(json.dumps({k:v for k,v in ingest(a.csv,a.out).items() if k!='sources'},ensure_ascii=False))
