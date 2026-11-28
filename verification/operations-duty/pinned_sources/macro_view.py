"""Personal read-only public macro observation viewer, not a vintage database."""
import csv,io,hashlib,threading,time,copy
from datetime import date,datetime,timezone,timedelta
from decimal import Decimal,InvalidOperation
from urllib.parse import urlencode
from urllib.request import Request,build_opener,ProxyHandler,HTTPRedirectHandler
from html import escape
from zoneinfo import ZoneInfo
ET=ZoneInfo("America/New_York")
BASE="https://fred.stlouisfed.org/graph/fredgraph.csv"
TERMS="https://fred.stlouisfed.org/legal/"
# source owner, units, frequency, manually checked observation/date
SERIES={
"DGS2":("미국 2년물 CMT","Federal Reserve Board","%", "D","2026-11-25","4.61"),
"DGS10":("미국 10년물 CMT","Federal Reserve Board","%","D","2026-11-25","4.85"),
"DFEDTARU":("연방기금금리 상단","Federal Reserve Board","%","D","2026-11-27","4.00"),
"DCOILBRENTEU":("브렌트 현물","EIA","USD/bbl","D","2026-11-24","91.80"),
"DCOILWTICO":("WTI 현물","EIA","USD/bbl","D","2026-11-24","82.24"),
"DTWEXBGS":("광의 달러 지수 (DXY 아님)","Federal Reserve Board","2006=100","D","2026-11-20","123.5978"),
"CPIAUCSL":("CPI 계절조정","BLS","1982–84=100","M","2026-10-01","337.476"),
"CPILFESL":("근원 CPI 계절조정","BLS","1982–84=100","M","2026-10-01","339.900"),
"PCEPI":("PCE 물가지수 계절조정","BEA","2017=100","M","2026-10-01","132.703"),
"PCEPILFE":("근원 PCE 계절조정","BEA","2017=100","M","2026-10-01","131.312"),
"PAYEMS":("비농업 고용 계절조정","BLS","천 명","M","2026-10-01","159293"),
"UNRATE":("실업률 계절조정","BLS","%","M","2026-10-01","4.1"),
}
BLOCKED={"VIXCLS":("VIX","CBOE copyright; review before automated retention"),"BAMLH0A0HYM2":("HY OAS","ICE internal-use restriction; no redistribution"),"SP500":("S&P 500","price license review"),"NASDAQCOM":("NASDAQ Composite","price license review")}
MAX=1_000_000
class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self,*a,**k):return None
def ids(group):
    if group not in ("D","M"):raise ValueError("UNKNOWN_GROUP")
    return tuple(k for k,v in SERIES.items() if v[3]==group)
def url(group,now):
    end=now.astimezone(ET).date();start=end-timedelta(days=60 if group=="D" else 500)
    return BASE+"?"+urlencode({"id":",".join(ids(group)),"cosd":start.isoformat(),"coed":end.isoformat()})
def fetch(group,now):
    u=url(group,now)
    op=build_opener(ProxyHandler({}),NoRedirect())
    with op.open(Request(u,headers={"User-Agent":"QuanTrade/0.1 personal data reference","Accept":"text/csv"}),timeout=5) as res:
        if res.status!=200 or res.geturl()!=u:raise ValueError("BAD_RESPONSE")
        raw=res.read(MAX+1)
    if len(raw)>MAX:raise ValueError("TOO_LARGE")
    return raw
def number(s):
    try:
        x=Decimal(s)
        if not x.is_finite() or abs(x)>Decimal("1e9"):raise ValueError("NONFINITE_OR_RANGE")
        return x
    except InvalidOperation:raise ValueError("INVALID_NUMBER") from None
def parse(raw,group,now):
    if len(raw)>MAX:raise ValueError("TOO_LARGE")
    reader=csv.reader(io.StringIO(raw.decode("utf-8-sig")))
    header=next(reader,[])
    names=ids(group)
    if len(header)!=1+len(names) or header[0] not in ("DATE","observation_date") or set(header[1:])!=set(names):raise ValueError("HEADER_MISMATCH")
    data={k:{} for k in names};seen=set();last=None
    today=now.astimezone(ET).date()
    for row in reader:
        if len(row)!=len(header) or len(seen)>=600:raise ValueError("ROW_LIMIT_OR_WIDTH")
        day=date.fromisoformat(row[0])
        if day.isoformat()!=row[0] or day>today or day in seen or last is not None and day<=last:raise ValueError("DATE_INVALID")
        seen.add(day);last=day
        for k,txt in zip(header[1:],row[1:]):
            if txt in ("","."):continue
            if group=="M" and day.day!=1:raise ValueError("MONTHLY_DATE_INVALID")
            v=number(txt)
            if k in ("CPIAUCSL","CPILFESL","PCEPI","PCEPILFE","PAYEMS","DTWEXBGS") and v<=0:raise ValueError("INVALID_LEVEL")
            if k=="UNRATE" and not 0<=v<=100:raise ValueError("INVALID_RATE")
            data[k][day]=v
    result=[]
    for k in names:
        vals=data[k]
        if not vals:result.append(record(k,None,None,[],now));continue
        day=max(vals);v=vals[day]
        item=record(k,day,str(v),[{"date":x.isoformat(),"value":str(vals[x])} for x in sorted(vals)[-30:]],now)
        if group=="M":
            prev=date(day.year-int(day.month==1),12 if day.month==1 else day.month-1,1)
            yoy=date(day.year-1,day.month,1)
            if k in ("CPIAUCSL","CPILFESL","PCEPI","PCEPILFE"):
                for label,when in (("mom_pct",prev),("yoy_pct",yoy)):
                    if vals.get(when):item[label]=str((100*(v/vals[when]-1)).quantize(Decimal(".0001")))
            elif k=="PAYEMS" and prev in vals:item["monthly_change_people"]=str((v-vals[prev])*1000)
        result.append(item)
    if not any(x["value"] is not None for x in result):raise ValueError("EMPTY_DATA")
    return result
def record(k,day,value,history,now):
    label,owner,unit,freq,_,_=SERIES[k]
    return {"id":k,"label":label,"source_owner":owner,"source":"https://fred.stlouisfed.org/series/"+k,"unit":unit,"frequency":freq,
            "observation_date":day.isoformat() if day else None,"value":value,"history":history,
            "age_calendar_days":(now.astimezone(ET).date()-day).days if day else None,
            "original_publication_time_verified":False,"mom_pct":None,"yoy_pct":None,"monthly_change_people":None}
class Cache:
    def __init__(self,loader=fetch,clock=time.monotonic,now=lambda:datetime.now(timezone.utc)):
        self.loader=loader;self.clock=clock;self.now=now;self.locks={g:threading.Lock() for g in ("D","M")};self.attempt={};self.saved={};self.status={}
    def get(self,g,refresh=False):
        names=ids(g);now=self.now()
        if not self.locks[g].acquire(False):return self.fallback(g,now,"REFRESH_IN_PROGRESS")
        try:
            at=self.clock()
            if refresh and (g not in self.attempt or at-self.attempt[g]>=3600):
                self.attempt[g]=at
                try:
                    raw=self.loader(g,now);rows=parse(raw,g,now)
                    self.saved[g]={"rows":rows,"checked_at":now.isoformat(),"raw_sha256":hashlib.sha256(raw).hexdigest()}
                    self.status[g]="FETCHED" if all(x["value"] is not None for x in rows) else "PARTIAL"
                except Exception:self.status[g]="REFRESH_FAILED"
            state=self.status.get(g,"NOT_FETCHED")
            if g not in self.saved:return self.fallback(g,now,state)
            out=copy.deepcopy(self.saved[g])
            for row in out["rows"]:
                if row["observation_date"]:row["age_calendar_days"]=(now.astimezone(ET).date()-date.fromisoformat(row["observation_date"])).days
            return {**out,"mode":"COLLECTED_FRED_REFERENCE","group":g,"state":state,"historical_only":state!="FETCHED","decision_authorized":False,"order_authorized":False}
        finally:self.locks[g].release()
    def fallback(self,g,now,state):
        rows=[record(k,date.fromisoformat(SERIES[k][4]),SERIES[k][5],[],now) for k in ids(g)]
        return {"rows":rows,"checked_at":"2026-11-28","raw_sha256":None,"mode":"MANUAL_DATED_REFERENCE","group":g,"state":state,"historical_only":True,"decision_authorized":False,"order_authorized":False}
CACHE=Cache()
def render(v,detail=False):
    e=lambda x:escape(str(x),quote=True)
    out=['<div class="section">FRED / '+("DAILY" if v["group"]=="D" else "MONTHLY")+'</div>',
        '<p class="notice">'+e(v["state"])+' · 확인 '+e(v["checked_at"])+' · '+("과거 참고값" if v["historical_only"] else "수집 성공 / 발표시각 미검증")+' · 최신 시장시세 아님</p>']
    for x in v["rows"]:
        val="미확인" if x["value"] is None else x["value"]+" "+x["unit"]
        extra=[]
        if x["mom_pct"] is not None:extra.append("전월비 "+x["mom_pct"]+"%")
        if x["yoy_pct"] is not None:extra.append("전년비 "+x["yoy_pct"]+"% (계절조정 지수 계산)")
        if x["monthly_change_people"] is not None:extra.append("전월차 "+x["monthly_change_people"]+"명")
        out.append('<div class="row"><span>'+e(x["label"])+'<br><small>'+e(x["observation_date"] or "—")+' · '+e(x["source_owner"])+' via <a href="'+e(x["source"])+'">FRED</a></small></span><strong>'+e(val)+'</strong></div>')
        if extra:out.append('<p class="notice">'+e(" / ".join(extra))+'</p>')
        if detail and len(x["history"])>1:
            vals=[float(p["value"]) for p in x["history"]];lo=min(vals);span=max(vals)-lo or 1
            points=" ".join(f"{10+i*300/(len(vals)-1):.1f},{70-60*(z-lo)/span:.1f}" for i,z in enumerate(vals))
            out.append('<svg viewBox="0 0 320 80" role="img" aria-label="최근 관측값 추이" style="width:100%;height:auto"><polyline fill="none" stroke="#333" stroke-width="1.4" points="'+points+'"/></svg><p class="notice">'+e(x["history"][0]["date"])+' – '+e(x["history"][-1]["date"])+' · 관측 간격 동일 표시, 실제 날짜 간격 아님</p>')
    if v["group"]=="M":out.append('<p><a href="/market/bls">BLS 직접 수집 / 물가·고용</a></p>')
    if not detail:out.append('<p><a href="/market/macro/'+v["group"]+'">상세 / 공식 데이터 갱신 시도</a></p>')
    out.append('<p class="notice">출처: 각 원기관 via FRED, Federal Reserve Bank of St. Louis. 최신 수정치이며 최초 발표값·실시간·투자 신호 아님. <a href="'+TERMS+'">이용 조건</a></p>')
    if detail and v["group"]=="D":
        for k,(label,why) in BLOCKED.items():out.append('<div class="row"><span>'+e(label)+' · '+e(why)+'</span><strong><a href="https://fred.stlouisfed.org/series/'+k+'">원문</a></strong></div>')
    return "".join(out)
