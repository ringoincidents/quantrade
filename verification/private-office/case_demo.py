"""Fixed synthetic valuation case. No approval, persisted plan, or actual financial data."""
from dataclasses import asdict
from datetime import datetime
from decimal import Decimal
from html import escape
from quantrade.capabilities.cash_flow_valuation import CashFlowDCFInput,CashFlowDCFScenario,evaluate_cash_flow_dcf
from quantrade.capabilities.valuation_method_applicability import DomainCheck,ValuationMethodApplicabilityInput,evaluate_method_applicability
from quantrade.capabilities.thesis_contract import (ThesisContractInput,Observation,Assumption,ThesisClaim,CounterClaim,FalsificationCondition,compile_thesis_contract)
from quantrade.workbench.entry_monitor import entry_price
REV="7db293770ae662dc07d2aa0a2f15a5277d6fa576"
SCENARIOS={"baseline","missing","invalid-domain","counter-gap","expired"}
AT="2026-11-28T08:00:00+09:00"
REVIEW_UNTIL="2026-12-31T00:00:00+09:00"
def scenario(name):
    if name not in SCENARIOS: raise ValueError("UNKNOWN_SCENARIO")
    case="SYNTHETIC-CASE-01"
    gate=evaluate_method_applicability(ValuationMethodApplicabilityInput(case,"owner-cf-dcf",
        "MISSING" if name=="missing" else "READY","fixture:semantic",
        (DomainCheck("positive-cf",True,"CASH_FLOW_NONPOSITIVE",("fixture:cf",)),
         DomainCheck("discount-growth",name!="invalid-domain","DISCOUNT_NOT_ABOVE_GROWTH",("fixture:assumptions",)))))
    thesis=compile_thesis_contract(ThesisContractInput(case,AT,
        observations=(Observation("o1","가상 기업의 현금흐름 사례","fixture:cf","HUMAN_ANALYSIS",AT),),
        assumptions=(Assumption("a1","현금흐름의 지속 성장","가상 가정"),),
        thesis_claims=(ThesisClaim("t1","현금흐름 성장 가설",("o1","a1")),),
        counter_claims=() if name=="counter-gap" else (CounterClaim("c1","t1","마진 하락 위험",("a1",)),),
        falsification_conditions=(FalsificationCondition("f1","t1","두 분기 연속 현금흐름 악화 시 재검토","주당 현금흐름","다음 두 분기"),)))
    review_as_of="2027-01-01T00:00:00+09:00" if name=="expired" else AT
    current=datetime.fromisoformat(review_as_of)<datetime.fromisoformat(REVIEW_UNTIL)
    valuation=None
    thresholds=[]
    if gate.status=="READY":
        valuation=asdict(evaluate_cash_flow_dcf(CashFlowDCFInput(case,"XNYS:DEMO_VALUE",AT,80.0,"USD",7.0,10.0,
            (CashFlowDCFScenario("bear","Bear",.25,.85,1,1,12,5,("a1",)),
             CashFlowDCFScenario("base","Base",.5,1,5,2,10,5,("a1",)),
             CashFlowDCFScenario("bull","Bull",.25,1.1,8,3,9,5,("a1",))))))
        # The legacy engine uses float arithmetic. Quantized display candidates only.
        v=Decimal(str(valuation["metrics"]["weighted_fair_value"]))
        for m in ("0.15","0.20","0.30"):
            thresholds.append({"margin_fraction":m,"illustrative_entry":str(entry_price(v,Decimal(m))),"approved":False})
    return {"mode":"SYNTHETIC_ONLY","scenario":name,"case_id":case,"capability_revision":REV,
            "method_gate":asdict(gate),"thesis":asdict(thesis),"valuation":valuation,
            "illustrative_thresholds":thresholds,"review_as_of":review_as_of,"review_until":REVIEW_UNTIL,"review_window_current":current,"policy":{"status":"DRAFT_NOT_APPROVED",
            "entry":"검증된 가치·종가와 승인 필요","stop_loss":"미설정","take_profit":"미설정",
            "position_limit":"미설정","review":"실적 변경 또는 가설 반증 시 재검토"},
            "f08_handoff":"BLOCKED_NO_AUTHENTICATED_APPROVAL","review_gaps":["NO_REAL_EVIDENCE","NO_AUTHENTICATED_APPROVAL"]+([] if current else ["REVIEW_WINDOW_EXPIRED"]),"actual_data_connected":False,
            "decision_authorized":False,"order_authorized":False}
def render(name):
    v=scenario(name); val=v["valuation"]
    def row(a,b):
        return '<div class="row"><span>'+escape(str(a))+'</span><strong>'+escape(str(b))+'</strong></div>'
    out=['<p class="notice"><strong>합성 기업 / 실제 투자 기준 아님</strong></p>',
         row("사건",v["case_id"]),row("평가 방법","주당 소유자 현금흐름 DCF"),
         row("방법 적용",v["method_gate"]["status"]),row("평가 기준",AT),row("검토 유효기간",v["review_until"]),row("검토 상태","유효 (가상)" if v["review_window_current"] else "만료 · 이전 산출값 참고 전용")]
    if val:
        out.append('<div class="section">01 / VALUATION</div>')
        for x in val["scenarios"]:
            out.append(row(x["label"]+" · 가정 확률 "+format(x["probability"]*100,".0f")+"%", "$"+format(x["fair_value"],".2f")))
        out.append(row("확률가중 가치 (가정)","$"+format(val["metrics"]["weighted_fair_value"],".2f")))
        out.append(row("가정상 가격 하락 확률",format(val["metrics"]["probability_of_price_loss"]*100,".1f")+"%"))
        for x in v["illustrative_thresholds"]:
            out.append(row("안전마진 "+format(Decimal(x["margin_fraction"])*100,".0f")+"% · 미승인","$"+format(Decimal(x["illustrative_entry"]),".2f")))
    else:
        out.append(row("가치 계산","차단 · "+", ".join(v["method_gate"]["reasons"])))
    out.append('<div class="section">02 / THESIS & OPERATING RULES</div>')
    out.append(row("실제 증거","없음 · 가상 가정"))
    for k,title in [("thesis_claims","투자 논리"),("counter_claims","반대 논리"),("falsification_conditions","반증 조건")]:
        items=v["thesis"]["nodes"][k]
        out.append(row(title," / ".join(x["statement"] for x in items) if items else "미확보"))
    for k,title in [("entry","진입"),("stop_loss","손절"),("take_profit","익절"),("position_limit","종목 비중"),("review","재검토")]:
        out.append(row(title,v["policy"][k]))
    out.append(row("F08 전달","차단 · 실제 승인 없음"))
    out.append('<div class="section">03 / FIXED SCENARIOS</div>')
    for k,label in [("baseline","가치평가"),("missing","재무자료 부족"),("invalid-domain","할인율 조건 불충족"),("counter-gap","반대 논리 누락"),("expired","검토 유효기간 만료")]:
        out.append('<div class="row"><a href="/cases/demo/'+k+'">'+label+'</a>'+("<strong>선택</strong>" if name==k else "")+'</div>')
    out.append('<p class="notice">확률·현금흐름·할인율은 합성 가정이며 실측 예측이나 승인값이 아닙니다. 기존 평가 엔진 '+REV[:12]+' · 주문 및 승인 기능 없음.</p>')
    return "".join(out)
