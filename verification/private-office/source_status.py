"""Dated source compatibility ledger. Probe environment != office runtime."""
from html import escape
CHECKED="2026-11-28"
SOURCES=[
 ("UST_PAR","미국 재무부 금리","PASS_SCHEMA","2026-11-27 · 2Y/10Y","/market/rates"),
 ("BLS_V1","BLS 물가·고용","PASS_SCHEMA","2026-10 · 4개 시계열","/market/bls"),
 ("BLS_ICS","BLS 경제 일정 ICS","BLOCKED","HTTPError","/market"),
 ("BLS_MONTHLY","BLS 경제 일정 HTML","BLOCKED","HTTPError","/market"),
 ("FRED_D","FRED 일별 CSV","BLOCKED","TimeoutError","/market/macro/D"),
 ("FRED_M","FRED 월별 CSV","BLOCKED","TimeoutError","/market/macro/M"),
 ("BEA","PCE 자동 갱신","NOT_VERIFIED","승인된 API 경로 필요","/market/macro/M"),
 ("PRICES","실제 주식 차트","BLOCKED","시세 이용 조건·검증 캘린더","/lab"),
 ("ICE_VIX","HY OAS / VIX","BLOCKED","시리즈별 이용 권리","/market/macro/D"),
 ("BROKER","실계좌","BLOCKED","보안·실계좌 승인","/assets"),
 ("STORAGE","영속 저장","BLOCKED","저장소·백업 운영 승인","/records"),
]
def snapshot():
    return {"mode":"DATED_COMPATIBILITY_EVIDENCE","checked_date":CHECKED,"probe_environment":"GITHUB_ACTIONS","runtime_verified":False,
            "probe_url":"https://github.com/ringoincidents/quantrade/actions/runs/46134296416",
            "sources":[{"id":i,"label":l,"probe_state":s,"detail":d,"page":p} for i,l,s,d,p in SOURCES],
            "decision_authorized":False,"order_authorized":False}
def render():
    v=snapshot();e=lambda x:escape(str(x),quote=True)
    out=['<p class="notice">2026-11-28 GitHub 수집 시험 기록. Railway 실시간 연결 상태 아님. 성공은 응답 형식 확인이며 역사적 공개 시점이나 데이터 권리 승인 아님.</p>']
    for x in v["sources"]:
        out.append('<div class="row"><span><a href="'+e(x["page"])+'">'+e(x["label"])+'</a><br><small>'+e(x["detail"])+'</small></span><strong>'+e(x["probe_state"])+'</strong></div>')
    out.append('<p><a href="'+e(v["probe_url"])+'">실제 수집 시험 기록</a></p>')
    return "".join(out)
