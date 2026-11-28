"""Research-only PIT experiment display; fixed artificial observations.
No composite score, forecast, actual market state, investment signal or data fetch.
"""
from datetime import datetime, timezone, timedelta
from html import escape
from asof_engine import Close, Release, asof_panel, vix_crosses, hy_turns, combine_events
REV="ea5b7c07a4d0940fb1d76d5343f7be0f3d2c05e4"
SCENARIOS={"baseline","late-release","credit-missing","baa-proxy"}
START=datetime(2020,1,1,tzinfo=timezone.utc)
def stamp(i,hour=21):
    return START+timedelta(days=i,hours=hour)
def scenario(name):
    if name not in SCENARIOS:raise ValueError("UNKNOWN_SCENARIO")
    # Artificial sequential days (not exchange sessions).
    # No future outcomes computed or reported.
    prices=[Close("D"+str(i),100.0,stamp(i)) for i in range(275)]
    credit_id="BAA10Y" if name=="baa-proxy" else "BAMLH0A0HYM2"
    vix=[Release("VIXCLS","D"+str(i),35.0 if i>=260 else 20.0,stamp(i,22 if name=="late-release" and i==260 else 20)) for i in range(275)]
    credit=[] if name=="credit-missing" else [Release(credit_id,"D"+str(i),1.0+.001*i if i<260 else 2.6-(i-260)*.06,stamp(i,20)) for i in range(275)]
    va=asof_panel(prices,vix,"VIXCLS")
    ca=asof_panel(prices,credit,credit_id)
    ve=vix_crosses(va)
    ce=hy_turns(ca,credit_id) if credit else []
    combined=combine_events(ve,ce) if credit else None
    def obs(x):
        return None if x is None else {"value":x.value,"series_id":x.series_id,"reference_day":x.observation_date,"first_public_at":x.first_public_at_utc.isoformat()}
    return {"mode":"SYNTHETIC_RESEARCH_ONLY","scenario":name,"source_revision":REV,"g0":"BLOCKED","g1":"NOT_RUN_REAL_DATA",
            "market_regime":None,"composite_index":None,"forecast":None,"actual_data_connected":False,
            "decision_authorized":False,"order_authorized":False,
            "credit_series":credit_id,"credit_kind":"INVESTMENT_GRADE_PROXY_NOT_HY" if name=="baa-proxy" else "DIRECT_HY_OAS",
            "fixture_day_260":{"close_at":prices[260].close_at_utc.isoformat(),"vix_known":obs(va[260]),"credit_known":obs(ca[260])},
            "synthetic_events":{"vix":ve,"credit":ce if credit else None,"combined":combined},
            "coverage":{"vix":sum(x is not None for x in va),"credit":sum(x is not None for x in ca),"fixture_days":len(prices)},
            "blockers":["SOURCE_RIGHTS_UNVERIFIED","VERIFIED_FIRST_PUBLICATION_HISTORY_MISSING","LONG_HY_HISTORY_MISSING","ADJUSTED_PRICE_HISTORY_MISSING","OUT_OF_SAMPLE_VALIDATION_NOT_RUN"],
            "research_gates":[["G0","데이터 권리·시점·가격 이력","BLOCKED"],["G1","단일 지표·선행성 실증","NOT_RUN"],["G2","복합지수·중복 제거","NOT_RUN"],["G3","조건부 예측 및 확률 보정","NOT_RUN"]]}
def render(name):
    v=scenario(name)
    def row(k,x):return '<div class="row"><span>'+escape(str(k))+'</span><strong>'+escape(str(x))+'</strong></div>'
    out=['<p class="notice"><strong>합성 연구 / 실제 장세 판정 아님</strong> · 예측 모델 및 매매 신호 미승인</p>',row("현재 시장 국면","판정 불가"),row("시장 복합지수 / 미래 예측선","미검증 · 표시하지 않음"),
         '<div class="section">01 / RESEARCH GATES</div>']
    for key,label,status in v["research_gates"]:out.append(row(key+" / "+label,status))
    out.append('<div class="section">02 / AS-OF SYNTHETIC EXPERIMENT</div>')
    out.append(row("신용지표",v["credit_series"]))
    out.append(row("지표 구분",v["credit_kind"]))
    out.append(row("합성 D260 기준 시각",v["fixture_day_260"]["close_at"]))
    for k,label in (("vix_known","VIX"),("credit_known","신용 스프레드")):
        x=v["fixture_day_260"][k]
        out.append(row(label+" 당시 알려진 값","미확인" if x is None else format(x["value"],".3f")))
        if x:out.append(row(label+" 최초 공개 시각 (가상)",x["first_public_at"]))
    for k,label in (("vix","VIX 상향 교차"),("credit","신용 축소 후보"),("combined","결합 사건")):
        x=v["synthetic_events"][k]
        out.append(row(label+" / 합성 사건 수","판정 불가" if x is None else str(len(x))))
    out.append('<p class="notice">가상 날짜는 거래소 세션이 아닙니다. 사건 수는 단위 테스트 설명이며 실제 적중률이나 수익률이 아닙니다.</p>')
    out.append('<div class="section">03 / BLOCKERS</div>')
    for b in v["blockers"]:out.append(row("미완료",b))
    out.append('<div class="section">04 / FIXED SCENARIOS</div>')
    for k,label in (("baseline","기준 합성 사례"),("late-release","종가 이후 발표"),("credit-missing","신용 데이터 없음"),("baa-proxy","Baa 별도 대리지표")):
        out.append('<div class="row"><a href="/market/demo/'+k+'">'+label+'</a>'+("<strong>선택</strong>" if k==name else "")+'</div>')
    out.append('<p class="notice">QT-MRI #135 / PR #136 · 기존 as-of 엔진 '+REV[:12]+' 재사용 · 실제 시계열 백테스트 미실시.</p>')
    return "".join(out)
