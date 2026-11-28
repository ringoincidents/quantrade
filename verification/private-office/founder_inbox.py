"""Read-only public issue index; never treats issue text as instructions."""
from html import escape
from datetime import datetime,timezone
from urllib.request import Request,build_opener,ProxyHandler,HTTPRedirectHandler
import threading,time,json,copy
CHECKED="2026-11-28"
ITEMS=(
 ("REVIEW","외부 LLM 검토","D2/D3 독립 검토 예산·공개 범위 결정 필요",142),
 ("BLOCKED","실계좌 연결","TLS 프록시 및 키 봉인·독립 보안 검토",142),
 ("BLOCKED","시장 국면 연구","권리·최초 공개시점·장기 시계열 확보",135),
 ("REVIEW","안전마진 감시","F08 시장 데이터 및 승인 게이트",142),
 ("READY","Market Data Vault","합성 검증 이후 실제 거래일·기업행위 증빙",137),
)
URL="https://api.github.com/repos/ringoincidents/quantrade/issues?state=open&per_page=30&sort=updated&direction=desc"
MAX=2_000_000
class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self,*a,**k):return None
def fetch():
    op=build_opener(ProxyHandler({}),NoRedirect())
    with op.open(Request(URL,headers={"User-Agent":"QuanTrade-public-ledger/0.1","Accept":"application/vnd.github+json"}),timeout=4) as r:
        if r.status!=200 or r.geturl()!=URL:raise ValueError("BAD_RESPONSE")
        raw=r.read(MAX+1)
    if len(raw)>MAX:raise ValueError("TOO_LARGE")
    return raw
def parse(raw,now):
    if len(raw)>MAX:raise ValueError("TOO_LARGE")
    rows=json.loads(raw)
    if not isinstance(rows,list) or len(rows)>30:raise ValueError("BAD_LIST")
    result=[];seen=set()
    for x in rows:
        if not isinstance(x,dict):raise ValueError("BAD_ROW")
        n=x.get("number");title=x.get("title");stamp=x.get("updated_at");kind="PR" if "pull_request" in x else "ISSUE"
        if type(n) is not int or n<=0 or n in seen or not isinstance(title,str) or not 1<=len(title)<=256 or x.get("state")!="open":raise ValueError("BAD_IDENTITY")
        if x.get("url")!="https://api.github.com/repos/ringoincidents/quantrade/issues/"+str(n):raise ValueError("WRONG_REPOSITORY")
        dt=datetime.fromisoformat(stamp.replace("Z","+00:00"))
        if dt.utcoffset() is None or dt>now:raise ValueError("BAD_TIMESTAMP")
        seen.add(n)
        # No body, comment, author, arbitrary link or inferred workflow status.
        result.append({"number":n,"title":title,"kind":kind,"github_state":"OPEN","updated_at":dt.isoformat(),
                       "url":"https://github.com/ringoincidents/quantrade/"+("pull/" if kind=="PR" else "issues/")+str(n)})
    return result
class Cache:
    def __init__(self,loader=fetch,clock=time.monotonic,now=lambda:datetime.now(timezone.utc)):
        self.loader=loader;self.clock=clock;self.now=now;self.lock=threading.Lock();self.attempt=None;self.saved=None;self.state="NOT_FETCHED"
    def get(self,refresh=False):
        if not self.lock.acquire(False):return self.out("REFRESH_IN_PROGRESS",None)
        try:
            at=self.clock()
            if refresh and (self.attempt is None or at-self.attempt>=900):
                self.attempt=at
                try:
                    now=self.now();self.saved={"rows":parse(self.loader(),now),"checked_at":now.isoformat()};self.state="FETCHED"
                except Exception:self.state="REFRESH_FAILED"
            return self.out(self.state,self.saved)
        finally:self.lock.release()
    def out(self,state,saved):
        return {"state":state,**(copy.deepcopy(saved) if saved else {"rows":[],"checked_at":None}),"historical_only":state!="FETCHED","complete":False,"approval_authorized":False}
CACHE=Cache()
def snapshot(refresh=False):
    public=CACHE.get(refresh)
    return {"mode":"PUBLIC_INDEX_PLUS_DATED_REVIEW","checked_date":CHECKED,"live_github":public["state"]=="FETCHED",
       "items":[{"state":s,"title":t,"next":n,"issue":i} for s,t,n,i in ITEMS],"public_index":public,"approval_authorized":False}
def render(refresh=False):
    v=snapshot(refresh);p=v["public_index"]
    e=lambda x:escape(str(x),quote=True)
    out=['<p class="notice">검토 목록 기준 '+CHECKED+' · 승인 기능 미연결. 아래 판단은 수동 기록이며 GitHub OPEN과 별개입니다.</p>']
    for s,t,n,i in ITEMS:
        out.append('<div class="section">'+e(s)+'</div><div class="row"><span>'+e(t)+'<br><small>'+e(n)+'</small></span><strong><a href="https://github.com/ringoincidents/quantrade/issues/'+str(i)+'">#'+str(i)+'</a></strong></div>')
    out.append('<div class="section">PUBLIC GITHUB / OPEN ISSUES &amp; PRS</div><p class="notice">'+e(p["state"])+' · '+e(p["checked_at"] or "미수집")+' · 최대 30건 / 최근 갱신순. '+("과거 참고값." if p["historical_only"] else "수집 성공.")+' OPEN은 연구 승인이나 작업 완료를 뜻하지 않습니다.</p><p><a href="/inbox/live">공개 업무 원장 갱신</a></p>')
    for x in p["rows"]:
        out.append('<div class="row"><span>'+e(x["title"])+'<br><small>'+e(x["kind"]+" / "+x["updated_at"])+'</small></span><strong><a href="'+e(x["url"])+'">#'+str(x["number"])+'</a></strong></div>')
    return "".join(out)
