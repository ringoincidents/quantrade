"""Public Treasury descriptive observations, never trading signals or PIT history.
Reuse pinned Vault parser. No storage, API keys or broker access.
"""
from datetime import datetime,timezone
from zoneinfo import ZoneInfo
from urllib.request import Request,build_opener,HTTPRedirectHandler,ProxyHandler
from decimal import Decimal
from html import escape
import threading,time,hashlib,copy
from treasury_pilot import official_url,parse_annual_xml,MAX_XML_BYTES
ET=ZoneInfo("America/New_York")
REF="https://home.treasury.gov/resource-center/data-chart-center/interest-rates/TextView?type=daily_treasury_yield_curve&field_tdr_date_value_month=202611"
REFERENCE=[("2026-11-19",4.76,5.04),("2026-11-20",4.63,4.92),("2026-11-23",4.63,4.92),("2026-11-24",4.63,4.91),("2026-11-25",4.61,4.85),("2026-11-27",4.69,4.94)]
class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):return None

def fetch(year):
    url=official_url(year)
    opener=build_opener(ProxyHandler({}),NoRedirect())
    with opener.open(Request(url,headers={"User-Agent":"QuanTradeResearch/0.1 public Treasury data","Accept":"application/atom+xml,application/xml,text/xml"}),timeout=4) as r:
        if r.status!=200 or r.geturl()!=url:raise ValueError("UNEXPECTED_RESPONSE")
        raw=r.read(MAX_XML_BYTES+1)
    if len(raw)>MAX_XML_BYTES or b"<!DOCTYPE" in raw.upper() or b"<!ENTITY" in raw.upper():raise ValueError("UNSAFE_XML")
    return raw,url

def bp(a,b):
    return int((Decimal(str(a))-Decimal(str(b)))*100)

def summarize(rows,now):
    if not rows:raise ValueError("MISSING_PAIRED_OBSERVATIONS")
    if len(rows)>366 or any(d>now.astimezone(ET).date().isoformat() for d,_,_ in rows):raise ValueError("FUTURE_OR_INVALID_OBSERVATION")
    ordered=sorted(rows)
    d,a,b=ordered[-1]
    age=(now.astimezone(ET).date()-datetime.fromisoformat(d).date()).days
    return {"observation_date":d,"ust_par_2y_pct":a,"ust_par_10y_pct":b,"spread_10y_2y_bp":bp(b,a),
        "five_observation_change_10y_bp":bp(b,ordered[-6][2]) if len(ordered)>=6 else None,
        "age_calendar_days_et":age,"age_state":"OLDER_THAN_4_CALENDAR_DAYS" if age>4 else "WITHIN_4_CALENDAR_DAYS",
        "history":[{"date":day,"two_y":x,"ten_y":y} for day,x,y in ordered[-30:]],
        "actual_latest_session_verified":False,"original_publication_time_verified":False,
        "is_fred_series":False,"decision_authorized":False,"order_authorized":False}

def parse(raw,year,now):
    series=parse_annual_xml(raw,year);a=dict(series["2Y"]);b=dict(series["10Y"])
    if not a or not b or max(a)!=max(b):raise ValueError("LATEST_PAIR_MISSING")
    # Both values on the same date only; no forward-fill.
    return summarize([(d,a[d],b[d]) for d in sorted(a.keys()&b.keys())],now)

class Cache:
    def __init__(self,loader=fetch,clock=time.monotonic,now=lambda:datetime.now(timezone.utc)):
        self.loader=loader;self.clock=clock;self.now=now;self.lock=threading.Lock();self.attempt=None;self.saved=None;self.state="NOT_FETCHED"
    def get(self,refresh=False):
        if not self.lock.acquire(False):
            return self.reference("REFRESH_IN_PROGRESS")
        try:
            ts=self.clock()
            if refresh and (self.attempt is None or ts-self.attempt>=3600):
                self.attempt=ts
                try:
                    now=self.now();year=now.astimezone(ET).year
                    raw,url=self.loader(year)
                    if url!=official_url(year):raise ValueError("SOURCE_MISMATCH")
                    value=parse(raw,year,now)
                    self.saved={"data":value,"source":url,"checked_at":now.isoformat(),"raw_sha256":hashlib.sha256(raw).hexdigest()}
                    self.state="FETCHED"
                except Exception:self.state="REFRESH_FAILED"
            if self.saved is None:return self.reference(self.state)
            out=copy.deepcopy(self.saved)
            age=(self.now().astimezone(ET).date()-datetime.fromisoformat(out["data"]["observation_date"]).date()).days
            out["data"]["age_calendar_days_et"]=age
            out["data"]["age_state"]="OLDER_THAN_4_CALENDAR_DAYS" if age>4 else "WITHIN_4_CALENDAR_DAYS"
            return {**out,"state":self.state,"mode":"COLLECTED_OFFICIAL_REFERENCE","refresh_mode":"ON_ACCESS_MAX_ONCE_PER_HOUR","historical_only":self.state!="FETCHED" or age>4}
        finally:self.lock.release()
    def reference(self,state):
        return {"data":summarize(REFERENCE,self.now()),"source":REF,"checked_at":"2026-11-28","raw_sha256":None,
                "state":state,"mode":"MANUAL_DATED_REFERENCE","refresh_mode":"ON_ACCESS_MAX_ONCE_PER_HOUR","historical_only":True}
CACHE=Cache()

def render(v,detail=False):
    x=v["data"]
    def esc(a):return escape(str(a),quote=True)
    def row(a,b):return '<div class="row"><span>'+esc(a)+'</span><strong>'+esc(b)+'</strong></div>'
    out=['<div class="section">US TREASURY / PAR YIELDS</div>',
         row("관측일 (미국 동부)",x["observation_date"]),row("2년물",f'{x["ust_par_2y_pct"]:.2f}%'),
         row("10년물",f'{x["ust_par_10y_pct"]:.2f}%'),row("10년−2년",f'{x["spread_10y_2y_bp"]:+d} bp'),
         row("10년물 / 5개 관측 간격 변화","—" if x["five_observation_change_10y_bp"] is None else f'{x["five_observation_change_10y_bp"]:+d} bp'),
         row("갱신 상태",v["state"]),row("확인 시점",v["checked_at"] or "—"),
         '<p class="notice">'+("과거 참고값 · " if v["historical_only"] else "공식 데이터 수집 성공 · ")+'최신 거래일 확정 여부 미검증. FRED DGS2/DGS10 별도 검증 필요. <a href="'+esc(v["source"])+'">공식 출처</a></p>']
    if detail:
        for p in reversed(x["history"]):out.append(row(p["date"],f'{p["two_y"]:.2f}% / {p["ten_y"]:.2f}%'))
        out.append('<p class="notice">접속 시 최대 한 시간 간격 갱신 시도. 캐시 메모리 전용, 원본 영속 보관 및 최초 공개시점 검증 없음.</p>')
    else:out.append('<p><a href="/market/rates">금리 상세 · 공식 갱신 시도</a></p>')
    return "".join(out)
