"""Synthetic capital review: reuse #119 opportunity and risk capabilities.
No actual portfolio, approved limits, target weights, capital authority or execution.
"""
from dataclasses import asdict
from html import escape
from quantrade.capabilities.investment_case import InvestmentCaseInput, ScenarioAssumption, evaluate_investment_case
from quantrade.capabilities.portfolio_opportunity import CapitalAlternative, PortfolioConstraintSnapshot, PortfolioOpportunityInput, assess_portfolio_opportunity
from quantrade.capabilities.risk_opinion import CandidateRiskProfile, RiskPolicySnapshot, RiskStateSnapshot, RiskOpinionInput, create_risk_opinion

REV="7db293770ae662dc07d2aa0a2f15a5277d6fa576"
AT="2026-11-28T08:00:00+09:00"
SCENARIOS={"baseline","strong-alternative","no-cash","correlation-veto","missing-risk","sector-limit","drawdown-veto"}

def scenario(name):
    if name not in SCENARIOS: raise ValueError("UNKNOWN_SCENARIO")
    # Separate fixed economics fixture. No assertion that it matches a DCF case.
    economics=evaluate_investment_case(InvestmentCaseInput("SYNTHETIC-PORTFOLIO-01","XNYS:DEMO_CAPITAL",AT,100.0,"USD",365,12.0,
        (ScenarioAssumption("bear","Bear",.25,60.0),ScenarioAssumption("base","Base",.5,125.0),ScenarioAssumption("bull","Bull",.25,170.0))))
    alternatives=(CapitalAlternative("CASH","CASH",3.0,0.0,("fixture:cash",)),
                  CapitalAlternative("CORE","CORE_BENCHMARK",8.0,-25.0,("fixture:core",)),
                  CapitalAlternative("HOLDING","CURRENT_HOLDING",30.0 if name=="strong-alternative" else 10.0,-30.0,("fixture:holding",)))
    constraints=PortfolioConstraintSnapshot("fixture:portfolio",AT,True,"fixture:mandate",4.0,12.0,
                      12.0 if name=="no-cash" else 20.0,12.0,2.0,("fixture:constraints",))
    assessment=assess_portfolio_opportunity(PortfolioOpportunityInput(economics,alternatives,constraints))
    risk=None
    if assessment.status=="ELIGIBLE_FOR_PORTFOLIO_REVIEW":
        candidate=CandidateRiskProfile("XNYS:DEMO_CAPITAL",economics.metrics["lowest_scenario_return_pct"],
           None if name=="missing-risk" else .95 if name=="correlation-veto" else .45,
           None if name=="missing-risk" else 2.0,False,("fixture:candidate",))
        policy=RiskPolicySnapshot("fixture:risk-policy",AT,10.0,1.0,-20.0,.80,5.0,False,True,True,("fixture:risk",))
        state=RiskStateSnapshot("fixture:risk-state",AT,4.0,-20.0 if name=="drawdown-veto" else -6.0,("fixture:state",))
        risk=create_risk_opinion(RiskOpinionInput(assessment,candidate,policy,state))
    # Separate illustrative sector exposure overlay, not a canonical risk policy.
    sector_current=30.0 if name=="sector-limit" else 24.0
    sector_limit=30.0
    sector_headroom=max(0.0,sector_limit-sector_current)
    arithmetic_ceiling=None
    if risk and risk.status in ("PASS","PASS_WITH_LIMITS"):
        arithmetic_ceiling=min(risk.limits["risk_position_ceiling_pct"],sector_headroom)
    return {"mode":"SYNTHETIC_ONLY","scenario":name,"capability_revision":REV,
            "economics":asdict(economics),"portfolio":asdict(assessment),"risk":asdict(risk) if risk else None,
            "sector_overlay":{"current_pct":sector_current,"limit_pct":sector_limit,"headroom_pct":sector_headroom,"qualification":"UNAPPROVED_FIXTURE_ONLY"},
            "illustrative_incremental_ceiling_pct":arithmetic_ceiling,"target_weight_pct":None,
            "actual_data_connected":False,"policy_approved":False,"decision_authorized":False,"order_authorized":False,
            "production_gaps":["NO_REAL_PORTFOLIO","NO_APPROVED_MANDATE","NO_VERIFIED_CORRELATION_OR_LIQUIDITY","NO_VALUATION_CROSSCHECK","NO_FOUNDER_DECISION"]}

def render(name):
    v=scenario(name);p=v["portfolio"];r=v["risk"]
    def row(k,x):
        return '<div class="row"><span>'+escape(str(k))+'</span><strong>'+escape(str(x))+'</strong></div>'
    def pct(x):
        return "—" if x is None else format(x,".2f")+"%"
    out=['<p class="notice"><strong>합성 포트폴리오 / 실제 운용 기준 아님</strong></p>',
         row("자본배분 검토",p["status"]),
         '<div class="section">01 / OPPORTUNITY COST</div>',
         row("후보 기대수익률 (가정)",pct(p["opportunity_cost"]["candidate_expected_return_pct"]))]
    for a in p["alternatives"]:
        out.append(row(a["alternative_id"]+" / 대안 기대수익률",pct(a["expected_return_pct"])))
    out.append(row("최선 대안 대비 차이",str(p["opportunity_cost"]["candidate_excess_vs_best_alternative_pct"])+"%p"))
    out.append('<div class="section">02 / CAPITAL HEADROOM · 추가 비중</div>')
    for k,label in (("concentration_headroom_pct","종목 집중도 여유"),("liquidity_headroom_pct","현금 유보 후 여유"),("risk_limited_headroom_pct","손실 예산 기준 여유"),("deterministic_upper_bound_pct","산술 상한")):
        out.append(row(label,pct(p["capital_headroom"][k])))
    out.append(row("섹터 한도 (별도 합성 예시)",pct(v["sector_overlay"]["headroom_pct"])))
    out.append('<div class="section">03 / INDEPENDENT RISK</div>')
    out.append(row("리스크 의견",r["status"] if r else "검토 진입 차단"))
    for why in (r["reasons"] if r else p["reasons"]):out.append(row("사유",why))
    out.append(row("추가 비중 산술 상한 (목표 비중 아님)",pct(v["illustrative_incremental_ceiling_pct"])))
    out.append(row("목표 비중 / 실제 주문","미설정 / 차단"))
    out.append('<div class="section">04 / FIXED SCENARIOS</div>')
    for k,label in (("baseline","기준 사례"),("strong-alternative","더 좋은 대안"),("no-cash","현금 유보 한도"),("correlation-veto","상관관계 거부"),("missing-risk","위험 정보 부족"),("sector-limit","섹터 한도 도달"),("drawdown-veto","낙폭 한도 도달")):
        out.append('<div class="row"><a href="/risk/demo/'+k+'">'+label+'</a>'+("<strong>선택</strong>" if k==name else "")+'</div>')
    out.append('<p class="notice">가상 기대수익과 한도, 별도 섹터 예시. 실제 위험 추정·교차 가치평가·승인 전. 투자 결정 및 주문 없음. 엔진 '+REV[:12]+'</p>')
    return "".join(out)
