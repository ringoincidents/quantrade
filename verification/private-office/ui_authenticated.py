"""Same-origin, authenticated three-space UI over the existing verification office.
No new data acquisition, authorization, trading or storage capabilities.
"""
import os,json,re
from http.server import ThreadingHTTPServer
from urllib.parse import urlsplit,parse_qs,quote
import server as legacy
import ui_functional_preview as ui

PROTECTED={"/","/assets","/cases","/risk","/market","/market/bls","/market/macro/D","/market/macro/M","/market/rates","/market/sources","/inbox","/inbox/live","/reports","/reports/fundamental/live/005930","/records"}
PATHS=ui.ALLOWED|PROTECTED
def detail(path,label,small=""):
    return '<a class="item" href="/workspace/detail?path='+quote(path,safe="")+'"><span>'+ui.E(label)+('<small>'+ui.E(small)+'</small>' if small else '')+'</span><span aria-hidden="true">›</span></a>'
def private(path,label):
    return detail(path,label)
ui.private=private

def home(space):
    h=ui.home(space).replace('href="/?space=', 'href="/workspace?space=').replace('href="/view?path=', 'href="/workspace/detail?path=').replace('src="/ui.js"', 'src="/workspace.js"').replace('공개·합성 검토','인증 업무실')
    # Keep provenance adjacent to the relevant data; only relocate generic settings.
    if space=="field":
        h=h.replace('<p class="muted">실시간 가격 및 위험 모델 미연결</p>', '<p class="muted">실시간 가격 및 위험 모델 미연결</p>'+detail("/market","시장 상황실 · 전체 지표"))
    if space=="office":
        h=h.replace('<h2>기관 운영</h2>','<h2>기관 운영</h2>'+detail("/","투자 업무 대장"))
    h=h.replace('</main>', '<section class="block"><details><summary>설정</summary><p class="notice">인증 세션 30분 · 주문 비활성 · 실계좌 미연결</p><p><a href="/legacy">기존 업무실 보기</a></p><form method="post" action="/logout"><button>잠금 / 로그아웃</button></form></details></section></main>')
    return h

def fragment(path):
    if path in PROTECTED:
        page=legacy.page(path).decode()
        title=re.search(r'<h1 class="title">(.*?)</h1>',page)
        start='<div class="rule"></div>';end='<p class="notice">개인 인증 검증용 화면.'
        if not title or page.count(start)!=1 or page.count(end)!=1:
            raise RuntimeError("UPSTREAM_MARKUP_CHANGED")
        return title.group(1),page.split(start,1)[1].split(end,1)[0]
    return ui.fragment(path)

JS=r"""
const d=document.getElementById('sheet'),body=document.getElementById('sheet-body'),title=document.getElementById('sheet-title');let opener=null,scroll=0,serial=0;
const known=new Set(['/', '/assets','/cases','/risk','/market','/market/bls','/market/macro/D','/market/macro/M','/market/rates','/market/sources','/inbox','/inbox/live','/reports','/reports/fundamental/live/005930','/reports/fundamental/005930','/records','/lab','/strategies','/performance']);
function safePath(p){return known.has(p)||/^\/(?:lab\/[DWMY]|(?:assets|cases|risk|reports|market)\/demo\/[a-z0-9_-]+)$/.test(p)}
function link(p){return '/workspace/detail?path='+encodeURIComponent(p)}
async function show(path,a){const current=++serial;if(!d.open){opener=a;scroll=window.scrollY;document.body.classList.add('modal');d.showModal();d.querySelector('.close').focus()}title.textContent='상세';body.textContent='불러오는 중';
try{const r=await fetch(link(path),{cache:'no-store',credentials:'same-origin'});if(current!==serial||!d.open)return;if(r.status===401){title.textContent='세션 만료';body.textContent='다시 로그인하세요.';const a=document.createElement('a');a.href='/login';a.textContent='로그인';body.append(a);return}if(!r.ok)throw Error();const v=await r.json();if(current!==serial||!d.open)return;
title.textContent=v.title;const parsed=new DOMParser().parseFromString(v.html,'text/html');parsed.querySelectorAll('script,style,form,iframe,object,embed,link,meta,base,input,button,foreignObject').forEach(n=>n.remove());
for(const el of parsed.body.querySelectorAll('*')){for(const at of [...el.attributes])if(/^on/i.test(at.name)||['src','srcset','action','formaction','xlink:href'].includes(at.name.toLowerCase()))el.removeAttribute(at.name);if(el.tagName==='A'){const raw=el.getAttribute('href')||'';if(raw.startsWith('/workspace/detail?path=')){}else if(raw.startsWith('/view?path='))el.href=link(new URL(raw,location.origin).searchParams.get('path'));else if(safePath(raw))el.href=link(raw);else if(raw.startsWith('/')&&!raw.startsWith('//')&&!raw.includes('\\')){}else if(!raw.startsWith('https://'))el.removeAttribute('href');el.rel='noreferrer'}}
body.replaceChildren(...parsed.body.childNodes);d.scrollTop=0;}catch{if(current===serial&&d.open)body.textContent='상세 정보를 불러올 수 없습니다.'}}
document.addEventListener('click',e=>{const a=e.target.closest('a');if(!a)return;const u=new URL(a.href,location.href);if(u.origin===location.origin&&u.pathname==='/workspace/detail'){e.preventDefault();show(u.searchParams.get('path'),a)}});
d.querySelector('.close').onclick=()=>d.close();d.addEventListener('click',e=>{if(e.target===d)d.close()});d.addEventListener('close',()=>{serial++;document.body.classList.remove('modal');body.replaceChildren();opener?.focus({preventScroll:true});window.scrollTo(0,scroll)});
"""
class Handler(legacy.Handler):
    def workspace_send(self,status,body,kind):
        raw=body.encode("utf-8")
        self.send_response(status)
        for k,v in (("Content-Type",kind),("Content-Length",str(len(raw))),("Cache-Control","no-store, private"),("Pragma","no-cache"),("Vary","Cookie"),("X-Content-Type-Options","nosniff"),("X-Frame-Options","DENY"),("Referrer-Policy","same-origin"),("Strict-Transport-Security","max-age=31536000"),("Content-Security-Policy","default-src 'none'; script-src 'self'; connect-src 'self'; style-src 'unsafe-inline'; form-action 'self'; base-uri 'none'; frame-ancestors 'none'")):
            self.send_header(k,v)
        self.end_headers()
        if raw:self.wfile.write(raw)
    def do_GET(self):
        u=urlsplit(self.path)
        if u.path not in ("/","/workspace","/workspace/detail","/workspace.js","/legacy"):
            return super().do_GET()
        if not self.preflight():return
        if not self.auth.active(self.session()):
            if u.path in ("/workspace/detail","/workspace.js"):
                return self.send(401,b'{"error":"UNAUTHORIZED"}',"application/json")
            return self.send(303,location="/login")
        q=parse_qs(u.query)
        try:
            if u.path=="/legacy":return self.send(200,legacy.page("/"))
            if u.path=="/workspace.js":return self.workspace_send(200,JS,"application/javascript")
            if u.path in ("/","/workspace"):
                space=q.get("space",["field"])[0]
                if space not in {"field","lab","office"}:raise ValueError()
                return self.workspace_send(200,home(space),"text/html; charset=utf-8")
            path=q.get("path",[""])[0]
            if path not in PATHS and not path.startswith(("date:","research:")):raise ValueError()
            t,h=fragment(path)
            return self.workspace_send(200,json.dumps({"title":t,"html":h},ensure_ascii=False),"application/json")
        except (ValueError,KeyError):self.send(404,b"Not found","text/plain")
        except Exception:self.send(503,b"Preview unavailable","text/plain")

class Server(ThreadingHTTPServer):
    daemon_threads=True
    def __init__(self,address,auth):
        super().__init__(address,Handler);self.auth=auth
if __name__=="__main__":
    auth=legacy.Auth(os.environ.get("OFFICE_ACCESS_TOKEN",""),os.environ.get("OFFICE_ORIGIN",""))
    print(json.dumps({"mode":"AUTH_PILOT_UI","configuration":"READY" if auth.ready else "LOCKED","configuration_reason":auth.configuration_reason,"private_data":"DISCONNECTED"}),flush=True)
    if auth.ready:
        result=legacy.check_link(os.environ.get("OFFICE_BROKER_LINK_KEY",""))
        print(json.dumps({"internal_link":result["state"],"real_data":False}),flush=True)
        print(json.dumps({"research_link":legacy.research_report()["state"]}),flush=True)
    Server(("0.0.0.0",int(os.environ.get("PORT","8080"))),auth).serve_forever()
