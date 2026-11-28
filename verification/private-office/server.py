"""Single-owner authentication pilot. No actual account data or broker access."""
import hashlib
import hmac
import json
import os
import re
import secrets
import threading
import time
from collections import deque
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit
from link_transport import check_link
from calendar_refresh import CACHE as BLS_CACHE
from bls_direct import CACHE as BLS_DATA_CACHE, render as bls_data_render
from macro_view import CACHE as MACRO_CACHE, render as macro_render
from treasury_view import CACHE as TREASURY_CACHE, render as treasury_render
from lab_view import FRAMES,lab as lab_snapshot,render_lab,compare as strategy_snapshot,render_compare
from source_status import snapshot as source_snapshot,render as source_render
from founder_inbox import snapshot as inbox_snapshot,render as inbox_render
from market_room import snapshot as market_room_snapshot, render as market_room_render
from market_demo import SCENARIOS as MARKET_SCENARIOS, render as market_render, scenario as market_scenario
from risk_demo import SCENARIOS as RISK_SCENARIOS, render as risk_render, scenario as risk_scenario
from case_demo import SCENARIOS as CASE_SCENARIOS, render as case_render, scenario as case_scenario
from report_demo import SCENARIOS as REPORT_SCENARIOS, render as report_render, scenario as report_scenario
from performance_view import snapshot as performance_snapshot,render as performance_render
from portfolio_demo import SCENARIOS, render as demo_render, scenario as demo_scenario

COOKIE = "__Host-qt_session"
TTL = 1800
MAX_SESSIONS = 8
MAX_ATTEMPTS = 8
WINDOW = 60
TOKEN = re.compile(r"[A-Za-z0-9_-]{32,128}")
ACCESS_KEY = re.compile(r"[!-~]{32,128}")
ORIGIN = re.compile(r"https://[a-z0-9][a-z0-9.-]*\.up\.railway\.app")

def hash_token(value):
    return hashlib.sha256(value.encode("ascii")).digest()

class Auth:
    def __init__(self, token, origin, clock=time.monotonic):
        self.origin = origin if ORIGIN.fullmatch(origin or "") else None
        self.secret = hash_token(token) if ACCESS_KEY.fullmatch(token or "") else None
        self.configuration_reason = ("ORIGIN_INVALID" if self.origin is None else
                                     "ACCESS_KEY_MISSING" if not token else
                                     "ACCESS_KEY_FORMAT_INVALID" if self.secret is None else "READY")
        self.clock = clock
        self.lock = threading.Lock()
        self.sessions = {}
        self.attempts = deque()

    @property
    def ready(self):
        return self.secret is not None and self.origin is not None

    def prune(self, now):
        self.sessions = {k:v for k,v in self.sessions.items() if v > now}
        while self.attempts and self.attempts[0] <= now-WINDOW:
            self.attempts.popleft()

    def login(self, supplied):
        if not self.ready:
            return 503,None
        with self.lock:
            now=self.clock()
            self.prune(now)
            if len(self.attempts)>=MAX_ATTEMPTS:
                return 429,None
            self.attempts.append(now)
            candidate = hash_token(supplied) if ACCESS_KEY.fullmatch(supplied or "") else bytes(32)
            if not hmac.compare_digest(candidate,self.secret):
                return 401,None
            session=secrets.token_urlsafe(32)
            if len(self.sessions)>=MAX_SESSIONS:
                del self.sessions[min(self.sessions,key=self.sessions.get)]
            self.sessions[hash_token(session)]=now+TTL
            return 303,session

    def active(self, session):
        if not self.ready or not TOKEN.fullmatch(session or ""):
            return False
        with self.lock:
            self.prune(self.clock())
            return hash_token(session) in self.sessions

    def logout(self, session):
        if TOKEN.fullmatch(session or ""):
            with self.lock:
                self.sessions.pop(hash_token(session),None)

STYLE = """<style>
:root{color-scheme:light}*{box-sizing:border-box}body{margin:0;background:#929291;color:#111;font:14px/1.6 system-ui,sans-serif}.shell{display:flex;max-width:1100px;margin:20px auto;padding-right:18px;align-items:flex-start}.rail{width:48px;flex:none;padding-top:10px;position:sticky;top:10px}.rail a{display:block;text-align:center;color:#111;text-decoration:none;border-top:1px solid #555;padding:15px 2px;min-height:48px;font-size:12px}.rail a[aria-current=page]{background:#fff}.paper{flex:1;min-width:0;min-height:620px;padding:23px 26px 36px;background:#fff}.mast{display:flex;justify-content:space-between;font:10px monospace;color:#333;gap:8px}.title{font-size:30px;font-weight:400;letter-spacing:-1px;margin:28px 0 15px}.sub{font-size:12px;color:#555}.rule{border-top:1px solid #111;margin-top:24px}.row{display:flex;justify-content:space-between;gap:12px;border-bottom:1px solid #c9c9c9;padding:14px 0}.row strong{font-weight:400}.section{font:11px monospace;color:#555;margin-top:25px}input{font:inherit;padding:12px;border:1px solid #555;width:100%;max-width:420px;margin:10px 0;display:block}button{font:inherit;padding:10px 16px;border:1px solid #111;background:white;cursor:pointer;color:#111}a:focus-visible,button:focus-visible,input:focus-visible{outline:2px solid #111;outline-offset:3px}.login{max-width:520px;margin:25px auto;padding:30px;background:white;min-height:440px}.notice{color:#555;font-size:12px;line-height:1.7}.foot{margin-top:32px;color:#666;font:10px monospace}@media(max-width:799px){.shell{margin:0;padding:0}.paper{min-height:100dvh;padding:19px 17px}.rail{width:44px}.login{margin:0;min-height:100dvh;padding:24px 20px}}
.cal{display:grid;grid-template-columns:repeat(7,minmax(0,1fr));border-top:1px solid #bbb;border-left:1px solid #bbb;margin-top:12px}.calhead,.calday{border-right:1px solid #bbb;border-bottom:1px solid #bbb;padding:4px;min-width:0}.calhead{text-align:center;font-size:10px;background:#f5f5f3}.calday{min-height:54px;font:11px monospace}.calday small{display:block;font:10px/1.35 system-ui,sans-serif;overflow-wrap:anywhere;margin-top:4px}.calday.empty{background:#f5f5f3}.row small{font-size:11px;color:#555}.row a{color:#333;font-size:11px}.row strong{text-align:right;flex-shrink:0}
</style>"""

def document(body):
    return ('<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>QuanTrade / Private Office</title>'+STYLE+'<body>'+body+'</body></html>').encode()

def login_page(message="",ready=True):
    form = ('<form method="post" action="/login"><label for="token">접근 키</label>'
            '<input id="token" name="token" type="password" autocomplete="current-password" maxlength="128" required>'
            '<button type="submit">입장</button></form>') if ready else ""
    return document('<main class="login"><div class="mast"><span>QUANTRADE</span><span>PRIVATE / ACCESS</span></div>'
                    '<h1 class="title">투자 업무실</h1><p class="notice">'+message+'</p>'+form+
                    '<div class="rule"></div><p class="notice">개인 전용 인증 검증 환경. 실제 금융 정보는 아직 연결하지 않았습니다.</p></main>')

PAGES = {"/":("01 / REGISTER","투자 업무 대장",[("인증 세션","활성"),("안전마진 감시","운영 승인 대기"),("실계좌 원장","미연결")]),
         "/assets":("02 / ASSETS","자산 원장",[("평가 자산","—"),("보유 종목","미연결"),("토스 계좌","아직 연결하지 않음")]),
         "/reports":("03 / REPORTS","투자 보고서",[("안전마진 감시","검증 중"),("시장 데이터","미연결"),("실제 보고서","삼성전자 2025 연간 / 검증 1건")]),
         "/records":("04 / RECORDS","운영 기록",[("인증 범위","단일 소유자 검증"),("실제 주문","비활성"),("운영 승인","보류")])}

FUNDAMENTAL_REPORT = json.loads("{\"state\":\"DATED_ACTUAL_PUBLIC_FILING_PILOT\",\"asset_id\":\"KRX:005930\",\"issuer\":\"삼성전자\",\"period\":\"2025-12-31\",\"filing_ref\":\"20260310002820\",\"filing_date\":\"2026-03-10\",\"verified_date\":\"2026-11-28\",\"metric_unit\":\"KRW_TRILLION\",\"metrics\":{\"assets\":\"566.942\",\"equity\":\"436.320\",\"liabilities\":\"130.622\",\"net_income\":\"45.207\",\"operating_income\":\"43.601\",\"revenue\":\"333.606\"},\"ratios\":{\"liabilities_to_equity_pct\":\"29.94\",\"net_margin_pct\":\"13.55\",\"operating_margin_pct\":\"13.07\"},\"accounting_identity_check\":\"PASS_WITHIN_1000_KRW\",\"independent_review\":\"PENDING\",\"capture_mode\":\"MANUAL_TRANSFER_FROM_ONE_SHOT_RAILWAY_LOG\",\"raw_retained\":false,\"automatic_refresh\":false,\"valuation_authority\":false,\"portfolio_authority\":false,\"trade_authority\":false,\"source\":\"https://dart.fss.or.kr/dsaf001/main.do?rcpNo=20260310002820\",\"code\":\"https://github.com/ringoincidents/quantrade/commit/1fe6c896b8a939b33acd500fbba4d4b549a2e17a\"}")

def fundamental_report_html():
    r=FUNDAMENTAL_REPORT
    return ('<p class="notice">실제 공식 공시 / 2025년 연간 연결 기준 / 2026-11-28 검증</p>'
            '<p>삼성전자 · 005930 · 독립 검토 대기</p><table>'
            '<tr><th>재무 항목</th><th>조 원</th></tr>'
            +''.join('<tr><td>'+label+'</td><td>'+r["metrics"][key]+'</td></tr>' for key,label in (("revenue","매출"),("operating_income","영업이익"),("net_income","당기순이익"),("assets","자산"),("liabilities","부채"),("equity","자본")))
            +'</table><table><tr><th>비율</th><th>%</th></tr>'
            +''.join('<tr><td>'+label+'</td><td>'+r["ratios"][key]+'</td></tr>' for key,label in (("operating_margin_pct","영업이익률"),("net_margin_pct","순이익률"),("liabilities_to_equity_pct","부채비율")))
            +'</table><p>회계 등식 검사 통과 (허용오차 1,000원). 자료 수집 시점과 공시일은 다릅니다.</p>'
            '<p><a href="'+r["source"]+'">DART 공시 원문</a> · <a href="'+r["code"]+'">검증 코드</a></p>'
            '<p class="notice">일회성 실행 결과를 수동 게시한 보고서입니다. 최신 분기·가격·가치평가·실계좌·자동 수집·독립 검토는 포함되지 않습니다. 매매 판단 권한 없음.</p>')

PAGES["/reports/fundamental/005930"]=("03 / FUNDAMENTAL","기업 재무 검증 보고서",[])
PAGES["/performance"]=("11 / PERFORMANCE","투자 성과·매매 복기",[])
PAGES["/cases"]=("05 / CASES","기업가치·운용 기준 원장",[("실제 종목","미연결"),("운용 기준","미승인")])
PAGES["/risk"]=("06 / RISK","포트폴리오·리스크 원장",[("실제 포트폴리오","미연결"),("실제 위험 한도","미승인")])
PAGES["/market"]=("07 / MARKET","시장 상황실",[("실제 장세","판정 불가"),("예측 모델","미검증"),("데이터 준비","G0 차단")])
PAGES["/market/bls"]=("07 / BLS","미국 물가·고용 / BLS",[])
PAGES["/market/macro/D"]=("07 / MACRO","거시경제 / 일별",[])
PAGES["/market/macro/M"]=("07 / MACRO","거시경제 / 월별",[])
PAGES["/market/rates"]=("07 / RATES","미 국채 금리",[])
PAGES["/lab"]=("08 / LAB","기술적 분석 Lab",[])
PAGES["/strategies"]=("09 / STRATEGIES","전략 비교",[])
PAGES["/market/sources"]=("07 / SOURCES","데이터 연결 검증",[])
PAGES["/inbox/live"]=("10 / INBOX","Founder Inbox / 공개 원장",[])
PAGES["/inbox"]=("10 / INBOX","Founder Inbox",[])
TABS = {"/":"업무","/assets":"자산","/cases":"종목","/risk":"위험","/market":"시장","/lab":"랩","/strategies":"전략","/inbox":"안건","/reports":"보고","/records":"기록"}

def page(path):
    demo = path.startswith("/assets/demo/")
    report_demo = path.startswith("/reports/demo/")
    case_demo = path.startswith("/cases/demo/")
    risk_demo=path.startswith("/risk/demo/")
    market_demo=path.startswith("/market/demo/")
    lab_demo=path.startswith("/lab/")
    number,title,rows=PAGES["/assets" if demo else "/reports" if report_demo else "/cases" if case_demo else "/risk" if risk_demo else "/market" if market_demo else "/lab" if lab_demo else path]
    nav="".join('<a href="'+link+'"'+(' aria-current="page"' if (path==link or demo and link=="/assets" or report_demo and link=="/reports" or case_demo and link=="/cases" or risk_demo and link=="/risk" or (market_demo or path=="/market/rates" or path.startswith("/market/macro/") or path in ("/market/bls","/market/sources")) and link=="/market" or lab_demo and link=="/lab" or path=="/inbox/live" and link=="/inbox" or path=="/performance" and link=="/records") else '')+'>'+name+'</a>' for link,name in TABS.items())
    content="".join('<div class="row"><span>'+a+'</span><strong>'+b+'</strong></div>' for a,b in rows)
    if demo:
        content=demo_render(path.rsplit("/",1)[1])
    elif market_demo:
        content=market_render(path.rsplit("/",1)[1])
    elif path=="/market":
        content='<p><a href="/market/sources">데이터 공급자 검증 현황</a></p>'+market_room_render(BLS_CACHE.get(),treasury_render(TREASURY_CACHE.get()),"".join(macro_render(MACRO_CACHE.get(g)) for g in ("D","M")))
    elif path=="/market/bls":
        content=bls_data_render(BLS_DATA_CACHE.get())
    elif path in ("/market/macro/D","/market/macro/M"):
        content=macro_render(MACRO_CACHE.get(path[-1],True),detail=True)
    elif path=="/market/rates":
        content=treasury_render(TREASURY_CACHE.get(True),detail=True)
    elif path=="/lab" or lab_demo:
        content=render_lab(path.rsplit("/",1)[1] if lab_demo else "D")
    elif path=="/strategies":
        content=render_compare()
    elif path in ("/inbox","/inbox/live"):
        content=inbox_render(path=="/inbox/live")
    elif path=="/market/sources":
        content=source_render()
    elif risk_demo:
        content=risk_render(path.rsplit("/",1)[1])
    elif path=="/risk":
        content+='<p><a href="/risk/demo/baseline">포트폴리오·위험 / 합성 사례</a></p>'
    elif case_demo:
        title="기업가치·운용 기준 원장"
        content=case_render(path.rsplit("/",1)[1])
    elif report_demo:
        content=report_render(path.rsplit("/",1)[1])
    elif path=="/cases":
        content+='<p><a href="/cases/demo/baseline">기업가치·운용 기준 / 합성 사례</a></p>'
    elif path=="/reports/fundamental/005930":
        content=fundamental_report_html()
    elif path=="/reports":
        content+='<p><a href="/reports/fundamental/005930">삼성전자 2025 연간 재무 / 실제 공시 검증</a></p>'
        content+='<p><a href="/reports/demo/baseline">안전마진 감시 / 합성 보고서 열기</a></p><p><a href="/cases/demo/baseline">기업가치·운용 기준 원장 / 합성 사례</a></p>'
    elif path=="/performance":
        content=performance_render()
    elif path=="/records":
        content+='<p><a href="/performance">투자 성과·매매 복기 / 합성 검증</a></p>'
    elif path=="/assets":
        content+='<p><a href="/assets/demo/initial">합성 원장 검증 화면 열기</a></p><p><a href="/api/link-check">내부 연결 검증 (상태)</a></p>'
    return document('<div class="shell"><nav class="rail" aria-label="책갈피">'+nav+'</nav><main class="paper">'
                    '<div class="mast"><span>QUANTRADE</span><span>'+number+'</span></div>'
                    '<h1 class="title">'+title+'</h1><div class="sub">PRIVATE AUTH PILOT / 실계좌·실시간 데이터 미연결</div>'
                    '<div class="rule"></div>'+content+
                    '<p class="notice">개인 인증 검증용 화면. 실제 잔고, 실시간 시세 및 매수 신호를 표시하지 않습니다.</p>'
                    '<form method="post" action="/logout"><button>잠금 / 로그아웃</button></form>'
                    '<div class="foot">SESSION / 30 MINUTES</div></main></div>')

class Handler(BaseHTTPRequestHandler):
    def setup(self):
        super().setup()
        self.connection.settimeout(10)

    def log_message(self,*args):
        # Never log request paths, headers, token or response data.
        pass

    @property
    def auth(self):
        return self.server.auth

    def send(self,status,body=b"",kind="text/html; charset=utf-8",location=None,cookie=None):
        self.send_response(status)
        self.send_header("Content-Type",kind)
        self.send_header("Content-Length",str(len(body)))
        self.send_header("Cache-Control","no-store, private")
        self.send_header("Pragma","no-cache")
        self.send_header("Vary","Cookie")
        self.send_header("X-Content-Type-Options","nosniff")
        self.send_header("X-Frame-Options","DENY")
        # no-referrer can force a same-origin HTML form POST Origin to null.
        # same-origin retains the origin for our POST and suppresses cross-origin referrers.
        self.send_header("Referrer-Policy","same-origin")
        self.send_header("Strict-Transport-Security","max-age=31536000")
        self.send_header("Content-Security-Policy","default-src 'none'; style-src 'unsafe-inline'; form-action 'self'; base-uri 'none'; frame-ancestors 'none'")
        if location:
            self.send_header("Location",location)
        if cookie is not None:
            self.send_header("Set-Cookie",cookie)
        if status==429:
            self.send_header("Retry-After",str(WINDOW))
        self.end_headers()
        if body:
            self.wfile.write(body)

    def valid_host(self):
        return self.auth.origin and self.headers.get_all("Host")==[urlsplit(self.auth.origin).netloc]

    def session(self):
        try:
            headers=self.headers.get_all("Cookie") or []
            if len(headers)!=1 or len(headers[0])>4096:
                return ""
            c=SimpleCookie()
            c.load(headers[0])
            # Reject ambiguous duplicates rather than picking one.
            if sum(x.strip().startswith(COOKIE+"=") for x in headers[0].split(";"))!=1:
                return ""
            return c[COOKIE].value if COOKIE in c else ""
        except Exception:
            return ""

    def cookie(self,value,max_age):
        return COOKIE+"="+value+"; Path=/; Secure; HttpOnly; SameSite=Strict; Max-Age="+str(max_age)

    def preflight(self):
        if not self.auth.ready:
            self.send(503,login_page("접근 키 설정 전 — 잠금 상태",ready=False))
            return False
        if not self.valid_host():
            self.send(403,b"Forbidden","text/plain")
            return False
        return True

    def do_GET(self):
        if self.path=="/health":
            self.send(200,b"ok","text/plain")
            return
        if not self.preflight():
            return
        active=self.auth.active(self.session())
        if self.path=="/login":
            self.send(303,location="/") if active else self.send(200,login_page("개인 접근 키를 입력하세요."))
            return
        if not active:
            if self.path.startswith("/api/"):
                self.send(401,b'{"error":"UNAUTHORIZED"}',"application/json")
            else:
                self.send(303,location="/login")
            return
        if self.path in PAGES:
            self.send(200,page(self.path))
        elif self.path.startswith("/assets/demo/") and self.path.rsplit("/",1)[1] in SCENARIOS and self.path.count("/")==3:
            self.send(200,page(self.path))
        elif self.path.startswith("/api/demo/portfolio/") and self.path.rsplit("/",1)[1] in SCENARIOS and self.path.count("/")==4:
            self.send(200,json.dumps(demo_scenario(self.path.rsplit("/",1)[1]),ensure_ascii=False).encode(),"application/json")
        elif self.path.startswith("/reports/demo/") and self.path.rsplit("/",1)[1] in REPORT_SCENARIOS and self.path.count("/")==3:
            self.send(200,page(self.path))
        elif self.path.startswith("/api/demo/report/") and self.path.rsplit("/",1)[1] in REPORT_SCENARIOS and self.path.count("/")==4:
            self.send(200,json.dumps(report_scenario(self.path.rsplit("/",1)[1]),ensure_ascii=False).encode(),"application/json")
        elif self.path.startswith("/cases/demo/") and self.path.rsplit("/",1)[1] in CASE_SCENARIOS and self.path.count("/")==3:
            self.send(200,page(self.path))
        elif self.path.startswith("/api/demo/case/") and self.path.rsplit("/",1)[1] in CASE_SCENARIOS and self.path.count("/")==4:
            self.send(200,json.dumps(case_scenario(self.path.rsplit("/",1)[1]),ensure_ascii=False,allow_nan=False).encode(),"application/json")
        elif self.path=="/api/cases":
            self.send(503,b'{"state":"NOT_CONNECTED","actual_data_connected":false}',"application/json")
        elif self.path=="/api/report":
            self.send(503,b'{"state":"NOT_CONNECTED","actual_data_connected":false}',"application/json")
        elif self.path.startswith("/risk/demo/") and self.path.rsplit("/",1)[1] in RISK_SCENARIOS and self.path.count("/")==3:
            self.send(200,page(self.path))
        elif self.path.startswith("/api/demo/risk/") and self.path.rsplit("/",1)[1] in RISK_SCENARIOS and self.path.count("/")==4:
            self.send(200,json.dumps(risk_scenario(self.path.rsplit("/",1)[1]),ensure_ascii=False,allow_nan=False).encode(),"application/json")
        elif self.path=="/api/risk":
            self.send(503,b'{"state":"NOT_CONNECTED","actual_data_connected":false}',"application/json")
        elif self.path.startswith("/market/demo/") and self.path.rsplit("/",1)[1] in MARKET_SCENARIOS and self.path.count("/")==3:
            self.send(200,page(self.path))
        elif self.path.startswith("/api/demo/market/") and self.path.rsplit("/",1)[1] in MARKET_SCENARIOS and self.path.count("/")==4:
            self.send(200,json.dumps(market_scenario(self.path.rsplit("/",1)[1]),ensure_ascii=False,allow_nan=False).encode(),"application/json")
        elif self.path.startswith("/lab/") and self.path.rsplit("/",1)[1] in FRAMES and self.path.count("/")==2:
            self.send(200,page(self.path))
        elif self.path.startswith("/api/demo/lab/") and self.path.rsplit("/",1)[1] in FRAMES and self.path.count("/")==4:
            self.send(200,json.dumps(lab_snapshot(self.path.rsplit("/",1)[1]),allow_nan=False).encode(),"application/json")
        elif self.path=="/api/demo/strategies":
            self.send(200,json.dumps(strategy_snapshot(),ensure_ascii=False,allow_nan=False).encode(),"application/json")
        elif self.path=="/api/reports/fundamental/005930":
            self.send(200,json.dumps(FUNDAMENTAL_REPORT,ensure_ascii=False,allow_nan=False).encode(),"application/json")
        elif self.path=="/api/demo/performance":
            self.send(200,json.dumps(performance_snapshot(),ensure_ascii=False,allow_nan=False).encode(),"application/json")
        elif self.path=="/api/performance":
            self.send(503,b'{"state":"NOT_CONNECTED","actual_account_connected":false}',"application/json")
        elif self.path=="/api/inbox/live":
            self.send(200,json.dumps(inbox_snapshot(True),ensure_ascii=False,allow_nan=False).encode(),"application/json")
        elif self.path=="/api/sources":
            self.send(200,json.dumps(source_snapshot(),ensure_ascii=False).encode(),"application/json")
        elif self.path=="/api/inbox":
            self.send(200,json.dumps(inbox_snapshot(),ensure_ascii=False).encode(),"application/json")
        elif self.path=="/api/calendar-refresh":
            self.send(200,json.dumps(BLS_CACHE.get(),ensure_ascii=False).encode(),"application/json")
        elif self.path=="/api/bls":
            self.send(200,json.dumps(BLS_DATA_CACHE.get(),ensure_ascii=False,allow_nan=False).encode(),"application/json")
        elif self.path in ("/api/macro/D","/api/macro/M"):
            self.send(200,json.dumps(MACRO_CACHE.get(self.path[-1],True),ensure_ascii=False,allow_nan=False).encode(),"application/json")
        elif self.path=="/api/treasury":
            self.send(200,json.dumps(TREASURY_CACHE.get(True),ensure_ascii=False,allow_nan=False).encode(),"application/json")
        elif self.path=="/api/market-room":
            self.send(200,json.dumps(market_room_snapshot(),ensure_ascii=False,allow_nan=False).encode(),"application/json")
        elif self.path=="/api/market":
            self.send(503,b'{"state":"RESEARCH_G0_BLOCKED","actual_data_connected":false}',"application/json")
        elif self.path=="/api/link-check":
            self.send(200,json.dumps(check_link(os.environ.get("OFFICE_BROKER_LINK_KEY",""))).encode(),"application/json")
        elif self.path=="/api/portfolio":
            self.send(503,b'{"state":"NOT_CONNECTED","actual_account_connected":false}',"application/json")
        elif self.path=="/api/status":
            self.send(200,json.dumps({"mode":"AUTH_PILOT","portfolio":"NOT_CONNECTED","orders":"DISABLED","report":"NOT_CONNECTED"}).encode(),"application/json")
        else:
            self.send(404,b"Not found","text/plain")

    def do_POST(self):
        if not self.preflight():
            return
        if self.headers.get_all("Origin")!=[self.auth.origin]:
            # Fixed diagnostic only; never emit actual headers, URLs or credentials.
            print(json.dumps({"auth_post":"ORIGIN_REJECTED"}),flush=True)
            self.send(403,login_page("브라우저 출처 검증 실패. Safari에서 직접 열고 로그인 화면을 새로고침하세요."))
            return
        if self.path=="/logout":
            if not self.auth.active(self.session()):
                self.send(401,b"Unauthorized","text/plain")
                return
            self.auth.logout(self.session())
            self.send(303,location="/login",cookie=self.cookie("",0))
            return
        if self.path!="/login":
            self.send(405,b"Method not allowed","text/plain")
            return
        try:
            lengths=self.headers.get_all("Content-Length") or []
            if len(lengths)!=1 or not re.fullmatch(r"[0-9]{1,4}",lengths[0]) or self.headers.get("Transfer-Encoding"):
                raise ValueError()
            size=int(lengths[0])
            if not 1<=size<=512 or self.headers.get_content_type()!="application/x-www-form-urlencoded":
                raise ValueError()
            raw=self.rfile.read(size)
            if len(raw)!=size:
                raise ValueError()
            fields=parse_qs(raw.decode("ascii"),strict_parsing=True,keep_blank_values=True,max_num_fields=2)
            if set(fields)!={"token"} or len(fields["token"])!=1:
                raise ValueError()
        except (ValueError,UnicodeError,OSError):
            self.send(400,b"Invalid request","text/plain")
            return
        status,session=self.auth.login(fields["token"][0])
        if status==303:
            self.send(303,location="/",cookie=self.cookie(session,TTL))
        else:
            self.send(status,login_page("접근 실패. 잠시 후 다시 시도하세요."))

class Server(ThreadingHTTPServer):
    daemon_threads=True
    def __init__(self,address,auth):
        super().__init__(address,Handler)
        self.auth=auth

if __name__=="__main__":
    auth=Auth(os.environ.get("OFFICE_ACCESS_TOKEN",""),os.environ.get("OFFICE_ORIGIN",""))
    print(json.dumps({"mode":"AUTH_PILOT","configuration":"READY" if auth.ready else "LOCKED","configuration_reason":auth.configuration_reason,"private_data":"DISCONNECTED"}),flush=True)
    # Bounded synthetic-only smoke; never contacts a broker or logs credentials.
    if auth.ready:
        result=check_link(os.environ.get("OFFICE_BROKER_LINK_KEY",""))
        print(json.dumps({"internal_link":result["state"],"real_data":False}),flush=True)
    Server(("0.0.0.0",int(os.environ.get("PORT","8080"))),auth).serve_forever()
