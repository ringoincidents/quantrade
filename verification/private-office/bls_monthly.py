"""Official BLS monthly table parser; strict date/time/summary identity."""
from html.parser import HTMLParser
from datetime import datetime,timedelta
from zoneinfo import ZoneInfo
from urllib.request import Request,build_opener,ProxyHandler,HTTPRedirectHandler
ET=ZoneInfo("America/New_York");KST=ZoneInfo("Asia/Seoul")
MAX=1_000_000
class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self,*a,**k):return None
class Rows(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True);self.rows=[];self.row=None;self.cell=None
    def handle_starttag(self,tag,attrs):
        if tag=="tr":self.row=[]
        elif tag in ("td","th") and self.row is not None:self.cell=[]
    def handle_data(self,x):
        if self.cell is not None:self.cell.append(x)
    def handle_endtag(self,tag):
        if tag in ("td","th") and self.cell is not None:
            self.row.append(" ".join("".join(self.cell).split()));self.cell=None
        elif tag=="tr" and self.row is not None:self.rows.append(self.row);self.row=None
def target(now):
    dt=now.astimezone(ET).date();n=dt+timedelta(days=7)
    return n.year,n.month
def url(y,m):return f"https://www.bls.gov/schedule/{y}/{m:02d}_sched_list.htm"
def parse(raw,y,m):
    if len(raw)>MAX:raise ValueError("TOO_LARGE")
    p=Rows();p.feed(raw.decode("utf-8-sig"));out=[];seen=set();header=False
    for row in p.rows:
        if row==["Date","Time","Release"]:header=True;continue
        if not header or len(row)!=3:continue
        a,b,c=row
        try:day=datetime.strptime(a,"%A, %B %d, %Y")
        except ValueError:continue
        if (day.year,day.month)!=(y,m):raise ValueError("WRONG_MONTH")
        if not b:continue # holidays without a release time
        try:stamp=datetime.strptime(b,"%I:%M %p")
        except ValueError:raise ValueError("BAD_TIME") from None
        dt=day.replace(hour=stamp.hour,minute=stamp.minute,tzinfo=ET)
        if not c or len(c)>300 or (dt,c) in seen:raise ValueError("BAD_EVENT")
        seen.add((dt,c));out.append({"at_kst":dt.astimezone(KST).isoformat(),"summary":c,"source":url(y,m)})
    if not header or not out or len(out)>100:raise ValueError("EMPTY_OR_BAD_TABLE")
    return sorted(out,key=lambda x:x["at_kst"])
def fetch(now):
    y,m=target(now);u=url(y,m);op=build_opener(ProxyHandler({}),NoRedirect())
    with op.open(Request(u,headers={"User-Agent":"QuanTrade/0.1 public calendar","Accept":"text/html"}),timeout=4) as r:
        if r.status!=200 or r.geturl()!=u:raise ValueError("BAD_RESPONSE")
        raw=r.read(MAX+1)
    return parse(raw,y,m),u
