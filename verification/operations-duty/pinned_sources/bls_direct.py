"""BLS public API v1, no key; fixed read-only economic series query.
Latest revised monthly observations, not original release vintages.
"""
import json,hashlib,threading,time,copy,csv,io
from datetime import date,datetime,timezone
from urllib.request import Request,build_opener,ProxyHandler,HTTPRedirectHandler
from macro_view import ET,number,parse as macro_parse
URL="https://api.bls.gov/publicAPI/v1/timeseries/data/"
DOC="https://www.bls.gov/developers/api_signature.htm"
MAP={"CUSR0000SA0":"CPIAUCSL","CUSR0000SA0L1E":"CPILFESL","CES0000000001":"PAYEMS","LNS14000000":"UNRATE"}
MAX=500_000
class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self,*a,**k):return None
def fetch(now):
    year=now.astimezone(ET).year
    body=json.dumps({"seriesid":list(MAP),"startyear":str(year-1),"endyear":str(year)}).encode()
    op=build_opener(ProxyHandler({}),NoRedirect())
    with op.open(Request(URL,data=body,headers={"Content-Type":"application/json","Accept":"application/json","User-Agent":"QuanTrade/0.1 public data reference"},method="POST"),timeout=5) as r:
        if r.status!=200 or r.geturl()!=URL:raise ValueError("BAD_RESPONSE")
        raw=r.read(MAX+1)
    if len(raw)>MAX:raise ValueError("TOO_LARGE")
    return raw
def unique(pairs):
    out={}
    for k,v in pairs:
        if k in out:raise ValueError("DUPLICATE_JSON_KEY")
        out[k]=v
    return out
def parse(raw,now):
    if len(raw)>MAX:raise ValueError("TOO_LARGE")
    obj=json.loads(raw,object_pairs_hook=unique)
    if obj.get("status")!="REQUEST_SUCCEEDED":raise ValueError("BLS_REQUEST_FAILED")
    result=obj.get("Results")
    if isinstance(result,list):
        if len(result)!=1:raise ValueError("RESULT_SHAPE")
        result=result[0]
    if not isinstance(result,dict):raise ValueError("RESULT_SHAPE")
    series=result.get("series")
    if not isinstance(series,list) or len(series)!=len(MAP):raise ValueError("SERIES_SET")
    seen=set();rows={};notes={}
    for item in series:
        k=item.get("seriesID")
        if k not in MAP or k in seen:raise ValueError("SERIES_SET")
        seen.add(k);f=MAP[k];periods=set()
        data=item.get("data")
        if not isinstance(data,list) or not data or len(data)>36:raise ValueError("DATA_SHAPE")
        for obs in data:
            yr=obs.get("year");per=obs.get("period")
            if per=="M13":continue
            if not isinstance(yr,str) or not yr.isdigit() or len(yr)!=4 or not isinstance(per,str) or len(per)!=3 or per[0]!="M" or not per[1:].isdigit():raise ValueError("PERIOD")
            day=date(int(yr),int(per[1:]),1)
            if day>now.astimezone(ET).date() or day in periods:raise ValueError("DATE_INVALID")
            periods.add(day)
            val=obs.get("value")
            if val in ("","-","."):continue
            v=number(val);rows.setdefault(day,{})[f]=str(v)
            foot=obs.get("footnotes") or []
            if not isinstance(foot,list) or len(foot)>20:raise ValueError("FOOTNOTES")
            notes[(day.isoformat(),f)]=[str(x.get("text",""))[:200] for x in foot if isinstance(x,dict) and x.get("text")]
    # Shared monthly validation/calculation; non-BLS PCE stays missing, never invented.
    from macro_view import ids
    keys=ids("M");buf=io.StringIO();w=csv.writer(buf);w.writerow(["observation_date",*keys])
    for day,vals in sorted(rows.items()):w.writerow([day.isoformat(),*[vals.get(k,".") for k in keys]])
    parsed=[x for x in macro_parse(buf.getvalue().encode(),"M",now) if x["id"] in MAP.values()]
    for x in parsed:
        bid=next(k for k,v in MAP.items() if v==x["id"])
        x.update({"source_owner":"BLS","source":"https://data.bls.gov/timeseries/"+bid,
                  "source_series_id":bid,"transport":"BLS_API_V1","footnotes":notes.get((x["observation_date"],x["id"]),[])})
    return parsed
class Cache:
    def __init__(self,loader=fetch,clock=time.monotonic,now=lambda:datetime.now(timezone.utc)):
        self.loader=loader;self.clock=clock;self.now=now;self.lock=threading.Lock();self.attempt=None;self.saved=None;self.state="NOT_FETCHED"
    def get(self):
        if not self.lock.acquire(False):return self.out("REFRESH_IN_PROGRESS",None)
        try:
            # v1 quota: one request per 3 hours per process, not a global quota guarantee.
            at=self.clock()
            if self.attempt is None or at-self.attempt>=10800:
                self.attempt=at
                try:
                    now=self.now();raw=self.loader(now);rows=parse(raw,now)
                    self.saved={"rows":rows,"checked_at":now.isoformat(),"raw_sha256":hashlib.sha256(raw).hexdigest()}
                    self.state="FETCHED" if all(x["value"] is not None for x in rows) else "PARTIAL"
                except Exception:self.state="REFRESH_FAILED"
            return self.out(self.state,self.saved)
        finally:self.lock.release()
    def out(self,state,saved):
        out=copy.deepcopy(saved) if saved else {"rows":[],"checked_at":None,"raw_sha256":None}
        now=self.now()
        for x in out["rows"]:
            if x["observation_date"]:x["age_calendar_days"]=(now.astimezone(ET).date()-date.fromisoformat(x["observation_date"])).days
        return {**out,"group":"M","mode":"BLS_DIRECT_REFERENCE","state":state,"historical_only":state!="FETCHED","decision_authorized":False,"order_authorized":False}
CACHE=Cache()
def render(v):
    from html import escape
    e=lambda x:escape(str(x),quote=True)
    out=['<div class="section">BLS / DIRECT API V1</div><p class="notice">'+e(v["state"])+' · 확인 '+e(v["checked_at"] or "없음")+' · 3시간 단위 접속 시 갱신 시도. 최초 발표시각 미검증.</p>']
    for x in v["rows"]:
        out.append('<div class="row"><span>'+e(x["label"])+'<br><small>'+e(x["observation_date"] or "미확인")+' · <a href="'+e(x["source"])+'">BLS 원문</a></small></span><strong>'+e("미확인" if x["value"] is None else x["value"]+" "+x["unit"])+'</strong></div>')
        for k,label in (("mom_pct","전월비 %"),("yoy_pct","전년비 % (계절조정 지수 계산)"),("monthly_change_people","전월 고용차 명")):
            if x[k] is not None:out.append('<div class="row"><span>'+e(label)+'</span><strong>'+e(x[k])+'</strong></div>')
        for note in x["footnotes"]:out.append('<p class="notice">'+e(note)+'</p>')
    if not v["rows"]:out.append('<p class="notice">자동 수집값 없음. <a href="/market/macro/M">날짜가 표시된 FRED 참고값</a>을 확인하세요.</p>')
    out.append('<p class="notice">BLS 원출처의 최신 수정치. PCE는 BEA 별도 경로 필요. <a href="'+DOC+'">공식 API 문서</a></p>')
    return "".join(out)
