"""One synthetic valuation dossier; no scheduler or institutional promotion.
Mandatory methods are fixed before any valuation, and failed methods never disappear.
"""
from dataclasses import dataclass,asdict,replace
from decimal import Decimal,localcontext
from method_gate import require,time,digest,ComparableMethod,compare
from fcff_wacc import Request as FCFFRequest,evaluate as fcff_eval,d as number
from peer_valuation import Request as PeerRequest,evaluate as peer_eval
from dcf_diagnostics import checked as fcfe_checked,diagnostics as fcfe_diagnostics
from quantrade.capabilities.cash_flow_valuation import CashFlowDCFInput
from quantrade.capabilities.valuation_crosscheck import ValuationMethodSnapshot,ValuationScenarioSnapshot

METHODS=("FCFE_DCF","FCFF_DCF","PE","EV_EBITDA")
@dataclass(frozen=True)
class ScenarioDefinition:
    id:str
    probability:float
    narrative:str
    assumption_ref:str
@dataclass(frozen=True)
class DossierInput:
    fcff:FCFFRequest
    fcfe:CashFlowDCFInput
    relative:PeerRequest  # one shared target and universe for both relative methods
    definitions:tuple[ScenarioDefinition,...]
    fcfe_input_refs:tuple[str,...]
    fcfe_base_scenario_id:str

def source(ref):
    require(isinstance(ref,str) and ref.startswith("synthetic:") and 10<len(ref)<=256,"SYNTHETIC_REF")
def align(r):
    require(isinstance(r,DossierInput) and isinstance(r.fcff,FCFFRequest) and isinstance(r.fcfe,CashFlowDCFInput) and isinstance(r.relative,PeerRequest),"DOSSIER_SCHEMA")
    f,c,p=r.fcff,r.fcfe,r.relative
    t=p.target
    require(p.method=="PE","CANONICAL_PE_REQUEST_REQUIRED")
    require(f.case_id==c.case_id==p.case_id and f.asset_id==c.asset_id==t.asset_id,"IDENTITY_MISMATCH")
    require(f.currency==c.currency==t.currency,"CURRENCY_MISMATCH")
    require(time(f.as_of)==time(c.as_of)==time(p.as_of) and time(f.quote_as_of)==time(t.quote_as_of),"TIME_MISMATCH")
    require(f.quote_ref==p.quote_ref and f.share_basis_ref==p.share_basis_ref and f.scenario_definition_ref==p.scenario_definition_ref,"REFERENCE_MISMATCH")
    require(number(f.current_price.value)==number(c.current_price)==number(t.price),"PRICE_MISMATCH")
    require(number(f.diluted_shares.value)==number(t.diluted_shares),"SHARE_COUNT_MISMATCH")
    for left,right in (("market_debt","debt"),("excess_cash","excess_cash"),("nonoperating_assets","nonoperating_assets"),("noncontrolling_interests","nci"),("preferred_claims","preferred"),("other_debt_like_claims","other_claims")):
        require(number(getattr(f,left).value)==number(getattr(t,right)),"CAPITAL_BRIDGE_MISMATCH:"+left)
    require(number(c.required_return_pct)==0,"PRESENT_VALUE_HURDLE_MISMATCH")
    require(isinstance(r.definitions,tuple) and 1<=len(r.definitions)<=10 and all(isinstance(x,ScenarioDefinition) for x in r.definitions),"DEFINITION_SCHEMA")
    ids=[x.id for x in r.definitions]
    require(len(set(ids))==len(ids),"DUPLICATE_DEFINITION")
    require(all(isinstance(x.id,str) and x.id.strip() and isinstance(x.narrative,str) and x.narrative.strip() and len(x.narrative)<=1000 and 0<=number(x.probability)<=1 for x in r.definitions),"DEFINITION")
    require(sum(number(x.probability) for x in r.definitions)==1,"DEFINITION_PROBABILITY")
    require(len({x.assumption_ref for x in r.definitions})==len(ids),"DEFINITION_REF_DUPLICATE")
    for x in r.definitions:source(x.assumption_ref)
    definition_ref="synthetic:scenario:"+digest([asdict(x) for x in r.definitions])
    require(f.scenario_definition_ref==definition_ref,"DEFINITION_DIGEST_MISMATCH")
    for scenarios,key in ((f.scenarios,"id"),(c.scenarios,"scenario_id"),(p.scenarios,"id")):
        require(len(scenarios)==len(ids) and {getattr(s,key) for s in scenarios}==set(ids),"SCENARIO_COVERAGE")
        lookup={getattr(s,key):s for s in scenarios}
        for x in r.definitions:
            s=lookup[x.id]
            require(number(s.probability)==number(x.probability),"SCENARIO_PROBABILITY")
            require(x.assumption_ref in s.assumption_refs,"SCENARIO_ASSUMPTION_BINDING")
    require(r.fcfe_base_scenario_id in ids,"FCFE_BASE_SCENARIO")
    require(isinstance(r.fcfe_input_refs,tuple) and 1<=len(r.fcfe_input_refs)<=64 and len(set(r.fcfe_input_refs))==len(r.fcfe_input_refs),"FCFE_SOURCE_REFS")
    for ref in r.fcfe_input_refs:source(ref)
    require(f.quote_ref in r.fcfe_input_refs and f.share_basis_ref in r.fcfe_input_refs,"FCFE_CONTEXT_REFS")

def run_fcfe(r):
    f,c=r.fcff,r.fcfe
    kw={"cash_flow_basis":"FCFE_PER_SHARE","discount_basis":"COST_OF_EQUITY"}
    _,values,_=fcfe_checked(c,**kw)
    report=fcfe_diagnostics(c,scenario_id=r.fcfe_base_scenario_id,**kw)
    h=digest(asdict(c))
    ar=tuple(sorted({ref for s in c.scenarios for ref in s.assumption_refs}))
    for ref in ar:source(ref)
    require(len(ar)<=64,"FCFE_ASSUMPTION_REFS")
    snapshot=ValuationMethodSnapshot("fcfe-"+h[:16],"FCFE_DCF",report["schema"],c.current_price,0,tuple(ValuationScenarioSnapshot(s.scenario_id,s.probability,float(v)) for s,v,_ in values),("synthetic:fcfe:"+h,))
    cm=ComparableMethod(snapshot,f.case_id,f.asset_id,f.currency,f.as_of,f.quote_as_of,f.quote_ref,f.share_basis_ref,f.scenario_definition_ref,"PRESENT_EQUITY_PER_DILUTED_SHARE",0,r.fcfe_input_refs,ar)
    return report,cm

def evaluate(r,*,scope):
    require(scope=="SYNTHETIC_ONLY","LIVE_SCOPE_BLOCKED")
    with localcontext() as ctx:
        ctx.prec=60
        align(r)
        # The FCFE and FCFF forecasts share scenario references but are not
        # economically reconciled. Explicitly preserve that limitation.
        runners=(lambda:run_fcfe(r),lambda:fcff_eval(r.fcff,scope=scope),lambda:peer_eval(r.relative,scope=scope),lambda:peer_eval(replace(r.relative,method="EV_EBITDA"),scope=scope))
        results=[];snapshots=[]
        for mid,run in zip(METHODS,runners):
            try:
                report,cm=run()
            except ValueError as e:
                results.append({"method":mid,"state":"BLOCKED_INPUT_OR_DOMAIN","reason":str(e),"report":None});continue
            if cm is None:
                results.append({"method":mid,"state":report["state"],"report":report});continue
            require(cm.snapshot.method_type==mid,"METHOD_OUTPUT_MISMATCH")
            results.append({"method":mid,"state":"CALCULATED_RESEARCH_ONLY","report":report})
            snapshots.append(cm)
        cross=None;cross_error=None
        if len(snapshots)==len(METHODS):
            try:cross=compare(tuple(snapshots),scope=scope)
            except ValueError as e:cross_error=str(e)
        else:cross_error="MANDATORY_METHOD_BLOCKED"
        values=[x["report"].get("weighted_fair_value_per_share",x["report"].get("weighted_fair_value")) for x in results if x["state"]=="CALCULATED_RESEARCH_ONLY"]
        summary={"calculated_count":len(values),"required_count":len(METHODS),"min_method_value":str(min(map(Decimal,values))) if values else None,"max_method_value":str(max(map(Decimal,values))) if values else None}
        body={"schema":"qt_valuation_dossier_research_v1","input_sha256":digest(asdict(r)),"case_id":r.fcff.case_id,"asset_id":r.fcff.asset_id,"as_of":r.fcff.as_of,"currency":r.fcff.currency,"price":r.fcff.current_price.value,"scope":scope,"mandatory_methods":list(METHODS),"methods":results,"summary":summary,"crosscheck":cross,"crosscheck_block_reason":cross_error,"state":"REVIEW_REQUIRED" if cross is not None else "BLOCKED_INCOMPLETE_VALUATION","scenario_economics_reconciled":False,"fcfe_fcff_reconciled":False,"source_verified":False,"assumptions_validated":False,"valuation_target_approved":False,"portfolio_authorized":False,"trade_authorized":False}
        return {"dossier":body,"dossier_sha256":digest(body)}
