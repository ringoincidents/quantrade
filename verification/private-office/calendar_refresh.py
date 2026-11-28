"""On-access bounded public BLS calendar refresh; no provider credentials.
Cache in memory, no background scheduler or guarantee of continuous refresh.
"""
from datetime import datetime,timezone,timedelta
from zoneinfo import ZoneInfo
from urllib.request import Request,build_opener,HTTPRedirectHandler
import threading,time
URL="https://www.bls.gov/schedule/news_release/bls.ics"
KST=ZoneInfo("Asia/Seoul")
MAX=1_000_000
class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self,*a,**k):return None
def fetch():
    opener=build_opener(NoRedirect())
    with opener.open(Request(URL,headers={"User-Agent":"QuanTrade/0.1 public calendar","Accept":"text/calendar"}),timeout=4) as r:
        if r.status!=200 or r.geturl()!=URL:raise ValueError("UNEXPECTED_RESPONSE")
        b=r.read(MAX+1)
        if len(b)>MAX:raise ValueError("TOO_LARGE")
        return b
def parse(raw,now):
    if len(raw)>MAX:raise ValueError("TOO_LARGE")
    lines=[]
    for x in raw.decode("utf-8-sig").splitlines():
        if x.startswith((" ","\t")) and lines:lines[-1]+=x[1:]
        else:lines.append(x)
    if not lines or lines[0]!="BEGIN:VCALENDAR" or lines[-1]!="END:VCALENDAR":raise ValueError("BAD_CALENDAR")
    out=[];current=None;seen=set()
    for line in lines:
        if line=="BEGIN:VEVENT":
            if current is not None:raise ValueError("NESTED_EVENT")
            current={}
        elif line=="END:VEVENT":
            if current is None:raise ValueError("UNEXPECTED_END")
            if current.get("STATUS")!="CANCELLED":
                if any(k.split(";")[0] in ("RRULE","RDATE","RECURRENCE-ID","EXDATE") for k in current):raise ValueError("RECURRENCE_UNSUPPORTED")
                starts=[(k,v) for k,v in current.items() if k.split(";")[0]=="DTSTART"]
                if len(starts)!=1 or not current.get("UID") or not current.get("SUMMARY"):raise ValueError("MISSING_FIELDS")
                k,v=starts[0]
                if v.endswith("Z") and k=="DTSTART":dt=datetime.strptime(v,"%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc)
                elif k in ("DTSTART;TZID=America/New_York","DTSTART;TZID=US/Eastern","DTSTART;TZID=Eastern Standard Time"):
                    dt=datetime.strptime(v,"%Y%m%dT%H%M%S").replace(tzinfo=ZoneInfo("America/New_York"))
                else:raise ValueError("UNKNOWN_EVENT_TIME")
                uid=current["UID"]
                if uid in seen:raise ValueError("DUPLICATE_UID")
                seen.add(uid)
                if now-timedelta(days=2)<=dt<=now+timedelta(days=45):
                    summary=current["SUMMARY"].replace("\\n"," ").replace("\\, ",", ").replace("\\,",",").replace("\\;",";")
                    if len(summary)>300:raise ValueError("SUMMARY_TOO_LONG")
                    out.append({"at_kst":dt.astimezone(KST).isoformat(),"summary":summary,"source":URL})
            current=None
        elif current is not None and ":" in line:
            k,v=line.split(":",1)
            if k in current:raise ValueError("DUPLICATE_FIELD")
            current[k]=v
    if current is not None or not out:raise ValueError("EMPTY_OR_INCOMPLETE")
    if len(out)>500:raise ValueError("TOO_MANY_EVENTS")
    return sorted(out,key=lambda x:x["at_kst"])
class Cache:
    def __init__(self,loader=fetch,clock=time.monotonic,now=lambda:datetime.now(timezone.utc)):
        self.loader=loader;self.clock=clock;self.now=now;self.lock=threading.Lock();self.last_attempt=None;self.events=[];self.checked=None;self.state="NOT_FETCHED"
    def get(self):
        if not self.lock.acquire(False):return {"state":"REFRESH_IN_PROGRESS","events":[],"checked_at":None,"source":URL}
        try:
            at=self.clock()
            if self.last_attempt is None or at-self.last_attempt>=3600:
                self.last_attempt=at
                try:
                    now=self.now();self.events=parse(self.loader(),now);self.checked=now.isoformat();self.state="FETCHED"
                except Exception:
                    self.state="REFRESH_FAILED"
            return {"state":self.state,"events":list(self.events),"checked_at":self.checked,"source":URL,"refresh_mode":"ON_ACCESS_MAX_ONCE_PER_HOUR","historical_only":self.state!="FETCHED"}
        finally:self.lock.release()
CACHE=Cache()
