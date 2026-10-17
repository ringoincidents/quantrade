#!/usr/bin/env python3
"""QuanTrade social/news attention collector; stdlib only, research-only.

No forum scraping, no market orders, no inference of price prediction.
"""
from __future__ import annotations
import argparse
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
from urllib import parse, request, error

UTC=dt.timezone.utc
API_GDELT='https://api.gdeltproject.org/api/v2/doc/doc'
API_NAVER='https://openapi.naver.com/v1/datalab/search'
ARTICLES_MAX=75
SEARCH_QUERIES={
 'leveraged_semis':'SOXL',
 'semiconductor_macro':'"semiconductor stocks" OR "chip stocks"',
 'ai_chip_supply':'"AI chips" OR "HBM memory"'}
NAVER_GROUPS=[
 {'groupName':'SOXL/속슬','keywords':['SOXL','속슬','속쓸']},
 {'groupName':'SOXS/속스','keywords':['SOXS','속스']},
 {'groupName':'반도체시장','keywords':['반도체 주식','반도체 ETF','필라델피아 반도체']}]

def iso(now:dt.datetime)->str:
 if now.tzinfo is None:raise ValueError('naive datetime')
 return now.astimezone(UTC).isoformat(timespec='seconds').replace('+00:00','Z')

def clock():return dt.datetime.now(UTC)

def decode_gdelt_seen(s):
 if not s:return None
 if len(s)==16 and s.endswith('Z'):
  return iso(dt.datetime.strptime(s,'%Y%m%dT%H%M%SZ').replace(tzinfo=UTC))
 return None

def fetch_json(url,payload=None,headers=None,timeout=18):
 h={'User-Agent':'QuanTrade-Research/0.1 (public metadata; bounded sampling)','Accept':'application/json'}
 h.update(headers or {})
 req=request.Request(url,data=payload,headers=h,method='POST' if payload else 'GET')
 with request.urlopen(req,timeout=timeout) as f:
  if int(f.status)!=200:raise RuntimeError('HTTP status '+str(f.status))
  raw=f.read(4_000_000+1)
  if len(raw)>4_000_000:raise ValueError('payload above 4MB limit')
 return json.loads(raw.decode('utf-8-sig'))

def gdelt_url(query,start,end):
 if (end-start)>dt.timedelta(days=1) or start>=end:
  raise ValueError('bounded request <= 24h')
 args={'query':query,'mode':'artlist','format':'json','maxrecords':str(ARTICLES_MAX),
       'sort':'datedesc','startdatetime':start.strftime('%Y%m%d%H%M%S'),
       'enddatetime':end.strftime('%Y%m%d%H%M%S')}
 return API_GDELT+'?'+parse.urlencode(args)

def gdelt_articles(query_name,blob,retrieved,known):
 entries=blob.get('articles')
 if entries is None:entries=[]
 if not isinstance(entries,list):raise ValueError('invalid articles list')
 result=[]
 for r in entries[:ARTICLES_MAX]:
  link=r.get('url')
  if not isinstance(link,str) or not link.startswith(('https://','http://')):continue
  key=hashlib.sha256(link.encode('utf-8')).hexdigest()
  first=known.setdefault(key,retrieved)
  result.append({'source':'gdelt_doc_artlist','topic':query_name,'url':link,
   'url_sha256':key,'first_seen_utc':first,'retrieved_utc':retrieved,
   'gdelt_seendate_utc':decode_gdelt_seen(r.get('seendate')),
   'domain':r.get('domain'),'language':r.get('language'),
   'published_utc':None,'publish_time_verified':False,
   'rights_status':'public_news_metadata_not_content_republication',
   'predictive_eligible':False,
   'note':'GDELT seen date is not verified original publication time.'})
 return result

def naver_request(start_date,end_date):
 return {'startDate':start_date,'endDate':end_date,'timeUnit':'date','keywordGroups':NAVER_GROUPS}

def naver_series(blob,retrieved,query_window):
 result=[]
 for group in blob.get('results',[]):
  for point in group.get('data',[]):
   result.append({'source':'naver_datalab','group':group['title'],
     'period':point['period'],'ratio':float(point['ratio']),
     'retrieved_utc':retrieved,'first_seen_utc':retrieved,
     'query_window':query_window,'unit':'relative_max_100_within_this_query',
     'predictive_eligible':False,'note':'Backfilled search interest, not sentiment or ex-ante snapshot.'})
 return result

def load_state(path):
 if not path.exists():return {'schema_version':1,'first_seen_urls':{}}
 x=json.loads(path.read_text('utf-8'))
 if not isinstance(x.get('first_seen_urls'),dict):raise ValueError('invalid state')
 return x

def collect(now,root,http=fetch_json,use_naver=False,dry_run=False):
 root=Path(root);retrieved=iso(now)
 start=now-dt.timedelta(hours=6)  # 3h schedule with overlap
 state_path=root/'state.json';state=load_state(state_path)
 run_id=now.strftime('%Y%m%dT%H%M%SZ');folder=root/'runs'/run_id
 status={'run_id':run_id,'observed_at_utc':retrieved,'status':'DIAGNOSTIC_ONLY_NO_TRADE',
   'queries':{},'naver':None,'social_forum_api_access':'NOT_AUTHORIZED',
   'live_forum_posts_ingested':0,'usable_price_predictions':0,
   'disclaimer':'News metadata and search volume are NOT forum sentiments.'}
 posts=[];trends=[]
 for name,query in SEARCH_QUERIES.items():
  url=gdelt_url(query,start,now)
  if dry_run:
   status['queries'][name]={'status':'DRY_RUN_NOT_FETCHED','url':url};continue
  try:
   raw=http(url)
   entries=gdelt_articles(name,raw,retrieved,state['first_seen_urls'])
   posts.extend(entries)
   status['queries'][name]={'status':'OK','returned':len(entries),'at_cap':len(entries)>=ARTICLES_MAX}
  except (ValueError,KeyError,error.URLError,TimeoutError,RuntimeError) as ex:
   status['queries'][name]={'status':'FAILED','reason':type(ex).__name__,'message':str(ex)[:160]}
 if use_naver:
  client=os.environ.get('NAVER_CLIENT_ID');secret=os.environ.get('NAVER_CLIENT_SECRET')
  if not client or not secret:status['naver']={'status':'NO_CREDENTIALS_NOT_FETCHED'}
  elif dry_run:status['naver']={'status':'DRY_RUN_NOT_FETCHED'}
  else:
   today=now.astimezone(dt.timezone(dt.timedelta(hours=9))).date()
   oldest=(today-dt.timedelta(days=365)).isoformat()
   period=oldest+'..'+today.isoformat()
   try:
    raw=http(API_NAVER,payload=json.dumps(naver_request(oldest,today.isoformat())).encode('utf-8'),
      headers={'Content-Type':'application/json','X-Naver-Client-Id':client,'X-Naver-Client-Secret':secret})
    trends=naver_series(raw,retrieved,period)
    status['naver']={'status':'OK','points':len(trends),'window':period}
   except (ValueError,KeyError,error.URLError,TimeoutError,RuntimeError) as ex:
    status['naver']={'status':'FAILED','reason':type(ex).__name__,'message':str(ex)[:160]}
 else:status['naver']={'status':'DISABLED_NO_API_KEY_REQUESTED'}
 status['gdelt_articles_sampled']=len(posts)
 status['naver_trend_points_sampled']=len(trends)
 folder.mkdir(parents=True,exist_ok=True)
 if not dry_run:
  (folder/'news_metadata.json').write_text(json.dumps(posts,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
  (folder/'naver_trends.json').write_text(json.dumps(trends,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
  state_path.parent.mkdir(parents=True,exist_ok=True)
  state_path.write_text(json.dumps(state,ensure_ascii=False,sort_keys=True,indent=2)+'\n',encoding='utf-8')
 (folder/'run_status.json').write_text(json.dumps(status,ensure_ascii=False,sort_keys=True,indent=2)+'\n',encoding='utf-8')
 return status

def main():
 p=argparse.ArgumentParser()
 p.add_argument('--root',default='research/social-event-study/live')
 p.add_argument('--naver',action='store_true');p.add_argument('--dry-run',action='store_true')
 a=p.parse_args()
 print(json.dumps(collect(clock(),a.root,use_naver=a.naver,dry_run=a.dry_run),ensure_ascii=False,indent=2))

if __name__=='__main__':main()
