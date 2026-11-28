"""Dated curated work ledger reference, not a live GitHub mirror."""
from html import escape
CHECKED="2026-11-28"
ITEMS=(
 ("REVIEW","외부 LLM 검토","D2/D3 독립 검토 예산·공개 범위 결정 필요",142),
 ("BLOCKED","실계좌 연결","TLS 프록시 및 키 봉인·독립 보안 검토",142),
 ("BLOCKED","시장 국면 연구","권리·최초 공개시점·장기 시계열 확보",135),
 ("REVIEW","안전마진 감시","F08 시장 데이터 및 승인 게이트",142),
 ("READY","Market Data Vault","합성 검증 이후 실제 거래일·기업행위 증빙",137),
)
def snapshot():
    return {"mode":"DATED_LEDGER_REFERENCE","checked_date":CHECKED,"live_github":False,
       "items":[{"state":s,"title":t,"next":n,"issue":i} for s,t,n,i in ITEMS],"approval_authorized":False}
def render():
    out=['<p class="notice">업무 원장 기준 '+CHECKED+' · 고정 검토 목록 · 실시간 GitHub 동기화 및 승인 기능 미연결</p>']
    for s,t,n,i in ITEMS:
        out.append('<div class="section">'+escape(s)+'</div><div class="row"><span>'+escape(t)+'<br><small>'+escape(n)+'</small></span><strong><a href="https://github.com/ringoincidents/quantrade/issues/'+str(i)+'">#'+str(i)+'</a></strong></div>')
    return "".join(out)
