"""Read-only dated official-publication snapshot; no live feed or forecast.
Economic calendar selected events, not exhaustive; original ET converted to KST.
"""
from datetime import date,datetime,timedelta
from zoneinfo import ZoneInfo
from html import escape
import calendar
from quantrade.workbench.session_calendar import START,END,VERSION,us_scheduled_session
ET=ZoneInfo("America/New_York")
KST=ZoneInfo("Asia/Seoul")
CHECKED="2026-11-28"
BLS="https://www.bls.gov/schedule/2026/12_sched_list.htm"
FED="https://www.federalreserve.gov/newsevents/2026-December.htm"
BEA="https://www.bea.gov/news/2026/personal-income-and-outlays-october-2026"
CPI="https://www.bls.gov/news.release/cpi.htm"
JOBS="https://www.bls.gov/news.release/empsit.htm"
EVENTS=(
 ("2026-12-01T10:00:00","JOLTS","10월 구인·이직",BLS),
 ("2026-12-04T08:30:00","고용","11월 고용보고서",BLS),
 ("2026-12-09T14:00:00","FOMC","12월 8~9일 회의 결과",FED),
 ("2026-12-09T14:30:00","기자회견","FOMC 기자회견",FED),
 ("2026-12-10T08:30:00","CPI","11월 소비자물가",BLS),
 ("2026-12-15T08:30:00","PPI","11월 생산자물가",BLS),
 ("2026-12-23T08:30:00","PCE","11월 개인소득·지출",BEA),
)
OBS=(
 ("CPI_MOM","소비자물가 전월비","+0.4%","2026-10","2026-11-10",CPI),
 ("PAYROLLS","비농업 고용 증감","+165,000명","2026-10","2026-11-06",JOBS),
 ("PCE_YOY","PCE 물가 전년비","+3.8%","2026-10","2026-11-25",BEA),
 ("CORE_PCE_YOY","근원 PCE 전년비","+3.3%","2026-10","2026-11-25",BEA),
 ("CORE_PCE_MOM","근원 PCE 전월비","+0.3%","2026-10","2026-11-25",BEA),
)
MISSING=("VIX","HY OAS","달러 인덱스","유가","KOSPI / KOSDAQ","S&P 500 / NASDAQ")

def snapshot():
    events=[]
    for stamp,label,detail,source in EVENTS:
        et=datetime.fromisoformat(stamp).replace(tzinfo=ET)
        events.append({"event":label,"detail":detail,"at_et":et.isoformat(),"at_kst":et.astimezone(KST).isoformat(),"source":source,"state":"SCHEDULED_AS_OF_SNAPSHOT"})
    sessions=[]
    for i in range((END-START).days+1):
        day=START+timedelta(days=i)
        session=us_scheduled_session("XNYS",day)
        sessions.append({"date_et":day.isoformat(),"state":"CLOSED_SCHEDULED" if not session else "EARLY_CLOSE_SCHEDULED" if session.close_at.hour==13 else "REGULAR_SCHEDULED",
                         "close_et":session.close_at.isoformat() if session else None,
                         "close_kst":session.close_at.astimezone(KST).isoformat() if session else None})
    return {"schema":"market-room-snapshot-v1","mode":"DATED_OFFICIAL_REFERENCE","checked_date":CHECKED,"auto_refresh":False,"live_market_feed":False,
        "calendar":{"month":"2026-12","timezone":"Asia/Seoul","complete":False,"events":events},
        "exchange":{"coverage_start":START.isoformat(),"coverage_end":END.isoformat(),"reference_version":VERSION,"market":"XNYS","sessions":sessions,"actual_close_verified":False,
                    "source":"https://www.nyse.com/trade/hours-calendars"},
        "macro":[{"id":i,"label":label,"value":v,"period":p,"release_date":d,"source":u} for i,label,v,p,d,u in OBS],
        "unconnected_series":list(MISSING),"market_regime":None,"forecast":None,"decision_authorized":False,"order_authorized":False}

def render(refresh=None,treasury_html=""):
    v=snapshot()
    def e(x):return escape(str(x),quote=True)
    def row(k,x):return '<div class="row"><span>'+e(k)+'</span><strong>'+e(x)+'</strong></div>'
    def src(url):return '<a href="'+e(url)+'" rel="noreferrer">공식 출처</a>'
    out=['<p class="notice"><strong>공식 발표·예정 일정 스냅샷</strong> · 확인일 '+CHECKED+' · 고정 거시 발표값 자동 갱신 미연결. 일정 변경 가능. 실시간 시세 아님.</p>',
         '<div class="section">01 / DECEMBER 2026 · KST</div>',
         '<div class="cal" role="table" aria-label="12월 주요 경제 발표 한국시간">']
    for label in ("월","화","수","목","금","토","일"):out.append('<div class="calhead">'+label+'</div>')
    by={}
    for item in v["calendar"]["events"]:by.setdefault(item["at_kst"][:10],[]).append(item)
    for week in calendar.Calendar(0).monthdayscalendar(2026,12):
        for day in week:
            if not day:out.append('<div class="calday empty"></div>');continue
            key=f"2026-12-{day:02d}"
            out.append('<div class="calday"><span>'+str(day)+'</span>'+''.join('<small>'+e(x["event"])+'</small>' for x in by.get(key,[]))+'</div>')
    out.append('</div><p class="notice">선택한 주요 일정만 표시. 미국 현지 발표일과 한국 날짜가 다를 수 있음.</p>')
    for x in v["calendar"]["events"]:
        local=datetime.fromisoformat(x["at_kst"])
        out.append('<div class="row"><span>'+e(local.strftime("%m/%d %H:%M"))+' KST<br>'+e(x["event"]+" · "+x["detail"])+'</span><strong>'+src(x["source"])+'</strong></div>')
    out.append('<div class="section">02 / MACRO · OFFICIAL RELEASES</div>')
    for x in v["macro"]:
        out.append('<div class="row"><span>'+e(x["label"])+'<br><small>'+e(x["period"])+' 기준 · '+e(x["release_date"])+' 발표 · '+src(x["source"])+'</small></span><strong>'+e(x["value"])+'</strong></div>')
    if treasury_html:out.append(treasury_html)
    out.append('<div class="section">03 / NYSE · SCHEDULED SESSIONS (ET)</div>')
    for x in v["exchange"]["sessions"]:
        state={"REGULAR_SCHEDULED":"정규 일정","EARLY_CLOSE_SCHEDULED":"조기 폐장 일정","CLOSED_SCHEDULED":"휴장 일정"}[x["state"]]
        close="—" if not x["close_kst"] else datetime.fromisoformat(x["close_kst"]).strftime("%m/%d %H:%M")+" KST"
        out.append(row(x["date_et"]+" · "+state,close))
    out.append('<p class="notice">거래소 참조 일정 11/23~12/04. 실제 폐장·데이터 확정 여부는 미검증. '+src(v["exchange"]["source"])+'</p>')
    out.append('<div class="section">04 / DATA COVERAGE</div>')
    for x in MISSING:out.append(row(x,"미연결"))
    out.append(row("한국 거래소 캘린더","미연결"))
    out.append(row("장세 종합 판정 / 예측","보류"))
    out.append('<p><a href="/market/demo/baseline">시장 국면 연구 · 합성 사례</a></p><p class="notice">연구 G0 차단 유지. 공식 발표값은 투자 신호가 아니며 합성 연구와 혼용하지 않습니다.</p>')
    if refresh is not None:
        out.append('<div class="section">05 / BLS CALENDAR · ON ACCESS</div>')
        out.append(row("공식 BLS 피드",refresh.get("state","UNKNOWN")))
        out.append(row("최종 성공 확인",refresh.get("checked_at") or "없음"))
        out.append('<p class="notice">화면 접속 시 최대 1시간 간격으로 공식 피드 갱신 시도. 실패 시 기존 일정은 참고용이며 자동 백그라운드 실행 아님. <a href="https://www.bls.gov/schedule/news_release/bls.ics">공식 구독 피드</a></p>')
        for x in refresh.get("events",[]):
            out.append(row(x["at_kst"][:16].replace("T"," "),x["summary"]))
    return "".join(out)
