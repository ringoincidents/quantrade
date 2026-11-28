"""Isolated public design review: existing synthetic engines and dated public facts only."""
import calendar, json, re, os
from decimal import Decimal
from datetime import datetime
from html import escape
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit,parse_qs,quote
from pathlib import Path
import server as legacy
import market_room, performance_view, portfolio_demo
from lab_view import FRAMES
from case_demo import SCENARIOS as CASES
from risk_demo import SCENARIOS as RISKS
from report_demo import SCENARIOS as REPORTS
from market_demo import SCENARIOS as MARKETS

AUTH="https://private-office-auth-verification.up.railway.app"
BASE={"/lab","/strategies","/performance","/reports/fundamental/005930"}
ALLOWED=BASE|{"/lab/"+x for x in FRAMES}|{"/assets/demo/"+x for x in portfolio_demo.SCENARIOS}|{"/cases/demo/"+x for x in CASES}|{"/risk/demo/"+x for x in RISKS}|{"/reports/demo/"+x for x in REPORTS}|{"/market/demo/"+x for x in MARKETS}
E=lambda x:escape(str(x),quote=True)
def detail(path,label,small=""):
    return '<a class="item" href="/view?path='+quote(path,safe="")+'"><span>'+E(label)+('<small>'+E(small)+'</small>' if small else '')+'</span><span aria-hidden="true">›</span></a>'
def private(path,label):
    return '<a class="item" href="'+AUTH+E(path)+'" rel="noreferrer"><span>'+E(label)+'<small>기존 인증 업무실에서 열기</small></span><span aria-hidden="true">↗</span></a>'
def section(title,body):
    return '<section class="block"><h2>'+E(title)+'</h2>'+body+'</section>'
def amount(x):return format(Decimal(x),",.0f")+"원"
def pct(x):return format(Decimal(x)*100,"+.2f")+"%"
def asset_chart(p):
    nav=[Decimal(m["nav_after_flow"]) for m in p["marks"]]
    cap=[];total=Decimal(p["opening_nav"])
    for m in p["marks"]:
        total+=Decimal(m["external_flow"]);cap.append(total)
    lo=min(nav+cap);hi=max(nav+cap);span=hi-lo or Decimal(1)
    def points(values):
        return " ".join(f"{10+i*280/(len(values)-1):.1f},{10+float((hi-v)/span)*100:.1f}" for i,v in enumerate(values))
    return '<svg viewBox="0 0 300 128" role="img" aria-label="성과 엔진 합성 순자산 및 투입원금 변화"><path d="M10 10H290 M10 60H290 M10 110H290" stroke="#ddd" fill="none"/><polyline points="'+points(nav)+'" stroke="#222" stroke-width="2" fill="none"/><polyline points="'+points(cap)+'" stroke="#999" stroke-dasharray="4 3" fill="none"/><text x="10" y="126" font-size="10">11/01</text><text x="290" y="126" text-anchor="end" font-size="10">11/22</text></svg><p class="muted">실선 순자산 · 점선 누적 투입원금</p>'
def calendar_html(s):
    month=s["calendar"]["month"];y,m=map(int,month.split("-"));by={}
    for x in s["calendar"]["events"]:by.setdefault(x["at_kst"][:10],[]).append(x)
    out=['<p class="muted">'+E(month)+' · 한국시간 · '+E(s["checked_date"])+' 확인</p><div class="cal">']
    out.extend('<span class="weekday">'+d+'</span>' for d in "월화수목금토일")
    for week in calendar.Calendar(0).monthdayscalendar(y,m):
        for d in week:
            if not d:out.append('<span></span>');continue
            key=f"{y:04d}-{m:02d}-{d:02d}";ev=by.get(key,[])
            out.append('<a class="'+('has' if ev else '')+'" href="/view?path='+quote("date:"+key,safe="")+'" aria-label="'+key+' 일정 '+str(len(ev))+'건">'+str(d)+('<small>'+E(ev[0]["event"] if len(ev)==1 else str(len(ev))+"건")+'</small>' if ev else '')+'</a>')
    return "".join(out)+"</div>"
def field():
    s=market_room.snapshot()
    macro="".join('<div class="row"><span>'+E(x["label"])+'<small>'+E(x["period"])+' · '+E(x["release_date"])+' 발표</small></span><strong>'+E(x["value"])+'</strong></div>' for x in s["macro"])
    return section("시장 국면",'<div class="metric">미판정</div><div class="gauge" aria-label="검증된 시장 위험 판정 없음"><i></i><i></i><i></i><i></i></div><p class="muted">실시간 가격 및 위험 모델 미연결</p>'+detail("/market/demo/baseline","시장 국면 실험","합성 검증"))+section("경제 일정",calendar_html(s))+section("거시경제",macro+private("/market/rates","미 국채 금리")+private("/market/bls","미국 물가·고용")+private("/market/macro/D","일별 거시 지표")+private("/market/macro/M","월별 거시 지표")+private("/market/sources","데이터 공급자 검증"))+section("종목 및 운용",detail("/reports/demo/baseline","안전마진 감시","기존 합성 엔진")+detail("/cases/demo/baseline","기업 가치·운용 기준","합성 검증")+detail("/risk/demo/baseline","포트폴리오 위험","합성 검증")+private("/market","거래소 일정·실제 출처 상태"))
def lab():
    projects=[("장기 이동평균선 기반 투자법",143),("시장 국면 복합지수",135),("인간 심리 역지표",139),("BNF 25일 이격도 전략",133)]
    return section("연구 계획","".join(detail("research:"+str(n),name,"검증 진척 미연결") for name,n in projects))+section("연구 도구",detail("/lab","기술적 분석 실험","일봉·주봉·월봉·년봉 / 기존 합성 차트")+detail("/strategies","전략 비교 실험","기존 계산 엔진 / 실제 백테스트 아님")+detail("/reports/fundamental/005930","삼성전자 재무 보고서","2025 연간 공식 공시 · 독립 검토 대기")+private("/reports/fundamental/live/005930","자동 연구 보고서"))
def office():
    p=performance_view.snapshot()["performance"];o=portfolio_demo.scenario("initial")["last_observation"]
    return section("자산 현황",'<p class="muted">합성 성과 엔진 · 실제 순자산 미확인</p><div class="metric">'+amount(p["closing_nav"])+'</div><p>투자 손익 '+amount(p["investment_pnl"])+'</p>'+asset_chart(p)+ '<div class="grid"><div>시간가중수익률<b>'+pct(p["twr_fraction"])+'</b></div><div>표본 최대낙폭<b>'+pct(p["sampled_max_drawdown_fraction"])+'</b></div></div>'+detail("/performance","성과·매매 복기")+detail("/assets/demo/initial","보유증권 원장","별도 합성 사례 · "+amount(o["securities_value_krw"])))+section("기관 운영",private("/inbox","안건 및 업무 지시")+private("/inbox/live","공개 업무 원장 조회")+private("/reports","투자 보고서")+private("/records","운영 기록")+private("/assets","실계좌 연결 상태"))
CSS="""
*{box-sizing:border-box}body{margin:0;background:#929291;color:#111;font:14px/1.6 system-ui,sans-serif;font-variant-numeric:tabular-nums}a{color:inherit}button{font:inherit;color:inherit;background:white;border:1px solid #111;cursor:pointer}a:focus-visible,button:focus-visible{outline:2px solid #111;outline-offset:2px}.shell{display:flex;max-width:1100px;margin:0 auto;align-items:flex-start}.rail{width:48px;flex:none;position:sticky;top:10px;padding-top:20px}.rail a{display:block;text-align:center;text-decoration:none;border-top:1px solid #555;padding:15px 0;min-height:48px;font-size:12px}.rail a:last-child{border-bottom:1px solid #555}.rail a[aria-current=page]{background:white;border-color:white}.paper{background:white;flex:1;min-width:0;min-height:100dvh;padding:23px 26px 36px}.mast{display:flex;justify-content:space-between;font-size:11px;color:#555;gap:8px}.title{font-size:30px;font-weight:400;letter-spacing:-1px;margin:28px 0 18px}.block{border-top:1px solid #bbb;padding:20px 0}.block:first-of-type{border-color:#111}h2{font-size:17px;margin:0 0 12px;font-weight:550}.metric{font-size:30px;line-height:1.2;letter-spacing:-1px}.muted,small,.notice{font-size:12px;color:#666;line-height:1.6}small{display:block}p{margin:8px 0}.item,.row{display:flex;align-items:center;justify-content:space-between;gap:10px;padding:12px 0;border-bottom:1px solid #c9c9c9;overflow-wrap:anywhere}.item{text-decoration:none}.item>span:first-child,.row>span:first-child{min-width:0}.item>span:last-child{flex:none}.row strong{font-weight:500;text-align:right;min-width:0}.section{color:#666;font-size:12px;margin-top:24px}.grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px}.grid b{display:block;font-size:22px;font-weight:500}.cal{display:grid;grid-template-columns:repeat(7,minmax(0,1fr));border-top:1px solid #bbb;border-left:1px solid #bbb}.cal>*{border-right:1px solid #bbb;border-bottom:1px solid #bbb;min-width:0;text-align:center;padding:5px 1px;min-height:43px;font-size:12px;text-decoration:none}.cal .weekday{min-height:auto;color:#666;font-size:10px}.cal .has{background:#eee}.cal small{font-size:9px;overflow-wrap:anywhere}.gauge{display:flex;gap:3px;margin:15px 0}.gauge i{height:6px;background:#d4d4d4;flex:1}svg{max-width:100%;height:auto}table{width:100%;border-collapse:collapse;overflow-wrap:anywhere;font-size:12px}td,th{padding:7px 2px;border-bottom:1px solid #ccc;text-align:left}dialog{margin:auto 0 0 auto;width:min(100%,520px);max-width:none;max-height:88dvh;padding:22px;border:1px solid #aaa;overflow:auto;background:white;color:#111}dialog::backdrop{background:#0005}.sheethead{display:flex;justify-content:space-between;align-items:center;border-bottom:1px solid #111;padding-bottom:12px;margin-bottom:15px;gap:10px}.sheethead h2{margin:0;font-size:21px}.close{width:40px;height:40px;font-size:24px;flex:none}.modal{overflow:hidden}.calday,.calhead{border:1px solid #bbb;min-width:0;overflow-wrap:anywhere}.calday small{font-size:10px}.sheetbody{overflow-wrap:anywhere}.sheetbody a{color:#333}.sheetbody input{max-width:100%}@media(max-width:799px){.paper{padding:19px 17px}.rail{width:44px}}@media(min-width:800px){dialog{height:100dvh;max-height:100dvh;margin:0 0 0 auto}.paper{padding:30px 45px}}"""
def home(space):
    views={"field":("필드",field),"lab":("랩",lab),"office":("오피스",office)}
    title,render=views[space]
    nav="".join('<a href="/?space='+k+'"'+(' aria-current="page"' if k==space else '')+'>'+v[0]+'</a>' for k,v in views.items())
    return '<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>QuanTrade</title><style>'+CSS+'</style><body><div class="shell"><nav class="rail" aria-label="책갈피">'+nav+'</nav><main class="paper"><div class="mast"><span>QUANTRADE</span><span>공개·합성 검토</span></div><h1 class="title">'+title+'</h1>'+render()+'</main></div><dialog id="sheet" aria-labelledby="sheet-title"><div class="sheethead"><h2 id="sheet-title">상세</h2><button class="close" aria-label="닫기">×</button></div><div class="sheetbody" id="sheet-body"></div></dialog><script src="/ui.js" defer></script></body></html>'
def fragment(path):
    if path.startswith("date:"):
        day=path[5:];s=market_room.snapshot()
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}",day) or day[:7]!=s["calendar"]["month"]:raise ValueError()
        datetime.fromisoformat(day)
        ev=[x for x in s["calendar"]["events"] if x["at_kst"].startswith(day)]
        return day,"".join('<div class="row"><span>'+E(x["at_kst"][11:16])+' KST · '+E(x["event"])+'<small>'+E(x["detail"])+'</small></span><a href="'+E(x["source"])+'">출처</a></div>' for x in ev)+('<p>등록된 주요 일정 없음</p>' if not ev else "")+'<p class="notice">선택된 공식 일정 스냅샷 · '+E(s["checked_date"])+' 확인 · 전체 일정 아님.</p>'
    if path.startswith("research:"):
        n=path[9:];names={"143":"장기 이동평균선 기반 투자법","135":"시장 국면 복합지수","139":"인간 심리 역지표","133":"BNF 25일 이격도 전략"}
        if n not in names:raise ValueError()
        return names[n],'<p>실제 연구 승인·검증 진척은 원장 연결 전입니다.</p><p><a href="https://github.com/ringoincidents/quantrade/issues/'+n+'">연구 원장 #'+n+'</a></p>'+detail("/lab","기술적 분석 실험")+detail("/strategies","전략 비교 실험")
    if path not in ALLOWED:raise ValueError()
    # Only fixed public filing and synthetic renderer paths above; never private API or live source.
    page=legacy.page(path).decode()
    title=re.search(r'<h1 class="title">(.*?)</h1>',page)
    start='<div class="rule"></div>';end='<p class="notice">개인 인증 검증용 화면.'
    if not title or page.count(start)!=1 or page.count(end)!=1:raise RuntimeError("UPSTREAM_MARKUP_CHANGED")
    content=page.split(start,1)[1].split(end,1)[0]
    return title.group(1),content

JS=r"""
const d=document.getElementById('sheet'),body=document.getElementById('sheet-body'),title=document.getElementById('sheet-title');let opener=null,scroll=0,serial=0;
const legacy='https://private-office-auth-verification.up.railway.app';
function safePath(p){return /^\/(?:lab(?:\/[DWMY])?|strategies|performance|reports\/fundamental\/005930|(?:assets|cases|risk|reports|market)\/demo\/[a-z0-9_-]+)$/.test(p)}
async function show(path,a){const current=++serial;if(!d.open){opener=a;scroll=window.scrollY;document.body.classList.add('modal');d.showModal();d.querySelector('.close').focus()}title.textContent='상세';body.textContent='불러오는 중';
try{const r=await fetch('/view?path='+encodeURIComponent(path),{cache:'no-store'});if(!r.ok)throw Error();const v=await r.json();if(current!==serial||!d.open)return;
title.textContent=v.title;const parsed=new DOMParser().parseFromString(v.html,'text/html');parsed.querySelectorAll('script,style,form,iframe,object,embed,link,meta,base,input,button,foreignObject').forEach(n=>n.remove());
for(const el of parsed.body.querySelectorAll('*')){for(const at of [...el.attributes])if(/^on/i.test(at.name)||['src','srcset','action','formaction','xlink:href'].includes(at.name.toLowerCase()))el.removeAttribute(at.name);if(el.tagName==='A'){const raw=el.getAttribute('href')||'';if(raw.startsWith('/view?path=')){}else if(safePath(raw))el.href='/view?path='+encodeURIComponent(raw);else if(raw.startsWith('/')&&!raw.startsWith('//'))el.href=legacy+raw;else if(!raw.startsWith('https://'))el.removeAttribute('href');el.rel='noreferrer'}}
body.replaceChildren(...parsed.body.childNodes);d.scrollTop=0;}catch{if(current===serial&&d.open)body.textContent='상세 정보를 불러올 수 없습니다.'}}
document.addEventListener('click',e=>{const a=e.target.closest('a');if(!a)return;const u=new URL(a.href,location.href);if(u.origin===location.origin&&u.pathname==='/view'){e.preventDefault();show(u.searchParams.get('path'),a)}});
d.querySelector('.close').onclick=()=>d.close();d.addEventListener('click',e=>{if(e.target===d)d.close()});d.addEventListener('close',()=>{serial++;document.body.classList.remove('modal');opener?.focus({preventScroll:true});window.scrollTo(0,scroll)});
"""
class Handler(BaseHTTPRequestHandler):
    def log_message(self,*args):pass
    def send(self,status,body,kind):
        raw=body.encode();self.send_response(status);self.send_header("Content-Type",kind);self.send_header("Content-Length",str(len(raw)));self.send_header("Cache-Control","no-store");self.send_header("X-Content-Type-Options","nosniff");self.send_header("X-Frame-Options","DENY");self.send_header("Referrer-Policy","no-referrer");self.send_header("Content-Security-Policy","default-src 'none'; script-src 'self'; style-src 'unsafe-inline'; connect-src 'self'; base-uri 'none'; frame-ancestors 'none'; form-action 'none'");self.end_headers();self.wfile.write(raw)
    def do_GET(self):
        u=urlsplit(self.path);q=parse_qs(u.query)
        try:
            if u.path=="/health":return self.send(200,"ok","text/plain")
            if u.path=="/ui.js":return self.send(200,JS,"application/javascript")
            if u.path=="/":
                space=q.get("space",["field"])[0]
                if space not in {"field","lab","office"}:raise ValueError()
                return self.send(200,home(space),"text/html; charset=utf-8")
            if u.path=="/view":
                path=q.get("path",[""])[0];t,h=fragment(path)
                return self.send(200,json.dumps({"title":t,"html":h},ensure_ascii=False),"application/json")
            raise ValueError()
        except (ValueError,KeyError):self.send(404,"Not found","text/plain")
        except Exception:self.send(503,"Preview unavailable","text/plain")
if __name__=="__main__":
    ThreadingHTTPServer(("0.0.0.0",int(os.environ.get("PORT","8080"))),Handler).serve_forever()
