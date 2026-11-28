"""Research-only method screen and comparable equity valuation diagnostic.
Reuses canonical applicability/crosscheck. Declared provenance is not verified.
"""
from dataclasses import dataclass,asdict
from datetime import datetime,timezone
from decimal import Decimal,localcontext
import math,hashlib,json
from quantrade.capabilities.valuation_method_applicability import (
    DomainCheck,ValuationMethodApplicabilityInput,evaluate_method_applicability,
)
from quantrade.capabilities.valuation_crosscheck import (
    ValuationMethodSnapshot,ValuationCrossCheckInput,evaluate_valuation_crosscheck,
)

# Candidate rules, not investment policy or universally applicable sector rules.
RULES={
 "OPERATING":("FCFE_DCF","FCFF_DCF","PE","EV_EBITDA","PB","DDM"),
 "FINANCIAL":("FCFE_DCF","PE","PB","DDM"),
 "REIT":("NAV","P_AFFO","DDM"),
 "PRE_PROFIT":("FCFF_DCF","NAV"),
}
REQUIRED={
 "FCFE_DCF":("FCFE_PER_SHARE","COST_OF_EQUITY"),
 "FCFF_DCF":("FCFF","WACC","NET_DEBT","DILUTED_SHARES"),
 "PE":("NORMALIZED_EPS","COMPARABLE_PE"),
 "PB":("BOOK_PER_SHARE","COMPARABLE_PB"),
 "EV_EBITDA":("NORMALIZED_EBITDA","COMPARABLE_EV_EBITDA","NET_DEBT","DILUTED_SHARES"),
 "DDM":("SUSTAINABLE_DPS","COST_OF_EQUITY","DIVIDEND_GROWTH"),
 "NAV":("NET_ASSET_VALUE","DILUTED_SHARES"),
 "P_AFFO":("AFFO_PER_SHARE","COMPARABLE_P_AFFO"),
}
POSITIVE={"FCFE_PER_SHARE","COST_OF_EQUITY","WACC","DILUTED_SHARES","NORMALIZED_EPS","COMPARABLE_PE","BOOK_PER_SHARE","COMPARABLE_PB","NORMALIZED_EBITDA","COMPARABLE_EV_EBITDA","SUSTAINABLE_DPS","NET_ASSET_VALUE","AFFO_PER_SHARE","COMPARABLE_P_AFFO"}
FAMILY={"FCFE_DCF":"DCF","FCFF_DCF":"DCF","PE":"MARKET_MULTIPLE","PB":"MARKET_MULTIPLE","EV_EBITDA":"MARKET_MULTIPLE","P_AFFO":"MARKET_MULTIPLE","DDM":"DIVIDEND","NAV":"ASSET"}
def require(ok,msg):
    if not ok:raise ValueError(msg)
def nonempty(s):return isinstance(s,str) and bool(s.strip()) and len(s)<=256
def time(s):
    require(nonempty(s),"TIMESTAMP")
    try:d=datetime.fromisoformat(s.replace("Z","+00:00"))
    except ValueError:raise ValueError("TIMESTAMP")
    require(d.tzinfo is not None,"TIMEZONE")
    return d.astimezone(timezone.utc)
def num(n):
    require(type(n) in (int,float) and math.isfinite(n) and abs(n)<=1e12,"NUMBER")
    return Decimal(str(n))
def refs(xs):
    require(isinstance(xs,tuple) and 0<len(xs)<=64 and all(nonempty(x) for x in xs) and len(set(xs))==len(xs),"REFERENCES")
    return set(xs)
def digest(x):return hashlib.sha256(json.dumps(x,sort_keys=True,separators=(",",":"),allow_nan=False).encode()).hexdigest()
@dataclass(frozen=True)
class Metric:
    value:float
    source_ref:str
    observed_at:str
    unit:str
METRIC_UNITS={
 "FCFE_PER_SHARE":"CCY_PER_SHARE","COST_OF_EQUITY":"PERCENT","FCFF":"CCY","WACC":"PERCENT","NET_DEBT":"CCY","DILUTED_SHARES":"SHARES",
 "NORMALIZED_EPS":"CCY_PER_SHARE","COMPARABLE_PE":"MULTIPLE","BOOK_PER_SHARE":"CCY_PER_SHARE","COMPARABLE_PB":"MULTIPLE","NORMALIZED_EBITDA":"CCY","COMPARABLE_EV_EBITDA":"MULTIPLE",
 "SUSTAINABLE_DPS":"CCY_PER_SHARE","DIVIDEND_GROWTH":"PERCENT","NET_ASSET_VALUE":"CCY","AFFO_PER_SHARE":"CCY_PER_SHARE","COMPARABLE_P_AFFO":"MULTIPLE",
}
def screen(*,case_id,profile,as_of,metrics,scope):
    require(scope=="SYNTHETIC_ONLY","LIVE_SCOPE_BLOCKED")
    require(nonempty(case_id),"CASE")
    cutoff=time(as_of)
    require(isinstance(metrics,dict) and set(metrics)<=set(METRIC_UNITS),"METRIC_KEYS")
    for k,m in metrics.items():
        require(isinstance(m,Metric) and nonempty(m.source_ref) and m.source_ref.startswith("synthetic:"),"SOURCE")
        require(m.unit==METRIC_UNITS[k],"UNIT_MISMATCH")
        require(time(m.observed_at)<=cutoff,"FUTURE_METRIC")
        num(m.value)
    if profile not in RULES:return {"profile":profile,"state":"PROFILE_REVIEW_REQUIRED","methods":[],"policy_adopted":False,"source_verified":False}
    rows=[]
    for method,keys in REQUIRED.items():
        missing=tuple(k for k in keys if k not in metrics)
        checks=[DomainCheck("PROFILE",method in RULES[profile],"PROFILE_NOT_IN_CANDIDATE_RULES",("synthetic:profile",))]
        for k in keys:
            if k in metrics and k in POSITIVE:
                checks.append(DomainCheck(k,num(metrics[k].value)>0,"NONPOSITIVE_"+k,(metrics[k].source_ref,)))
        if method=="DDM" and not missing:
            checks.append(DomainCheck("SPREAD",num(metrics["COST_OF_EQUITY"].value)>num(metrics["DIVIDEND_GROWTH"].value),"DIVIDEND_GROWTH_NOT_BELOW_DISCOUNT",tuple(metrics[k].source_ref for k in ("COST_OF_EQUITY","DIVIDEND_GROWTH"))))
        artifact=evaluate_method_applicability(ValuationMethodApplicabilityInput(case_id,method,"MISSING" if missing else "READY","synthetic:metric-screen",tuple(checks)))
        rows.append({"method_id":method,"family":FAMILY[method],"status":"CANDIDATE_INPUTS_PRESENT" if artifact.status=="READY" else "BLOCKED","missing":missing,"reasons":artifact.reasons})
    return {"profile":profile,"state":"RESEARCH_SCREEN_ONLY","methods":rows,"policy_adopted":False,"source_verified":False,"automatic_method_selected":False}

@dataclass(frozen=True)
class ComparableMethod:
    snapshot:ValuationMethodSnapshot
    case_id:str
    asset_id:str
    currency:str
    as_of:str
    quote_as_of:str
    quote_ref:str
    share_basis_ref:str
    scenario_definition_ref:str
    value_basis:str
    valuation_horizon_days:int
    input_refs:tuple[str,...]
    assumption_refs:tuple[str,...]

def compare(methods,*,scope):
    require(scope=="SYNTHETIC_ONLY","LIVE_SCOPE_BLOCKED")
    require(isinstance(methods,tuple) and 2<=len(methods)<=8,"METHOD_COUNT")
    require(all(isinstance(m,ComparableMethod) and isinstance(m.snapshot,ValuationMethodSnapshot) for m in methods),"METHOD_SCHEMA")
    first=methods[0]
    common=("case_id","asset_id","currency","quote_ref","share_basis_ref","scenario_definition_ref","value_basis","valuation_horizon_days")
    for m in methods:
        require(all(getattr(m,k)==getattr(first,k) for k in common),"CONTEXT_MISMATCH")
        require(all(nonempty(getattr(m,k)) for k in common if k!="valuation_horizon_days"),"CONTEXT_REQUIRED")
        require(m.currency in {"USD","KRW"} and m.value_basis=="PRESENT_EQUITY_PER_DILUTED_SHARE" and type(m.valuation_horizon_days) is int and m.valuation_horizon_days==0,"VALUE_BASIS_MISMATCH")
        require(time(m.as_of)==time(first.as_of) and time(m.quote_as_of)==time(first.quote_as_of),"AS_OF_MISMATCH")
        require(time(m.quote_as_of)<=time(m.as_of),"FUTURE_QUOTE")
        require(m.snapshot.method_type in FAMILY,"METHOD_TYPE")
        require(num(m.snapshot.current_price)>0 and num(m.snapshot.current_price)==num(first.snapshot.current_price),"PRICE_MISMATCH")
        require(num(m.snapshot.required_return_pct)==num(first.snapshot.required_return_pct)==0,"HURDLE_NOT_APPLICABLE_TO_PRESENT_VALUE")
        require(1<=len(m.snapshot.scenarios)<=10,"SCENARIO_COUNT")
        require(sum(num(s.probability) for s in m.snapshot.scenarios)==1,"PROBABILITY_SUM")
        require(all(0<=num(s.probability)<=1 and num(s.fair_value)>0 for s in m.snapshot.scenarios),"SCENARIO_NUMBER")
        require({s.scenario_id:num(s.probability) for s in m.snapshot.scenarios}=={s.scenario_id:num(s.probability) for s in first.snapshot.scenarios},"SCENARIO_MISMATCH")
        allrefs=refs(m.input_refs)|refs(m.assumption_refs)|refs(m.snapshot.source_refs)|{m.quote_ref,m.share_basis_ref,m.scenario_definition_ref}
        require(all(r.startswith("synthetic:") for r in allrefs),"SYNTHETIC_REFERENCE_ONLY")
    require(len({m.snapshot.method_type for m in methods})==len(methods),"DUPLICATE_METHOD_TYPE")
    result=evaluate_valuation_crosscheck(ValuationCrossCheckInput(first.case_id,tuple(m.snapshot for m in methods)))
    overlaps=[]
    for i,a in enumerate(methods):
        for b in methods[i+1:]:
            shared=sorted((set(a.input_refs)|set(a.assumption_refs))&(set(b.input_refs)|set(b.assumption_refs)))
            overlaps.append({"a":a.snapshot.method_id,"b":b.snapshot.method_id,"shared_refs":shared,"same_family":FAMILY[a.snapshot.method_type]==FAMILY[b.snapshot.method_type]})
    # Independent of legacy rounding for the conservative per-scenario result.
    with localcontext() as c:
        c.prec=50
        values=[{s.scenario_id:num(s.fair_value) for s in m.snapshot.scenarios} for m in methods]
        conservative=sum(num(s.probability)*min(v[s.scenario_id] for v in values) for s in first.snapshot.scenarios)
        require(abs(conservative-Decimal(str(result.robust_metrics["weighted_fair_value"])))<=max(Decimal("0.000002"),abs(conservative)*Decimal("1e-10")),"ROBUST_ARITHMETIC_MISMATCH")
        robust=str(conservative.quantize(Decimal("0.000001")))
        gap=str(((conservative/num(first.snapshot.current_price)-1)*100).quantize(Decimal("0.000001")))
    return {"schema":"qt_comparable_valuation_research_v1","context_sha256":digest([asdict(m) for m in methods]),
       "case_id":first.case_id,"asset_id":first.asset_id,"currency":first.currency,
       "method_count":len(methods),"distinct_families":len({FAMILY[m.snapshot.method_type] for m in methods}),
       "method_weighted_values":[{"id":x["method_id"],"weighted_fair_value":x["weighted_fair_value"]} for x in result.method_summaries],
       "conservative_fair_value":robust,"conservative_valuation_gap_pct":gap,
       "method_dependency_diagnostics":overlaps,"method_independence_established":False,
       "economic_scenario_alignment_verified":False,"source_verified":False,"valuation_gap_is_annualized_return":False,
       "state":"REVIEW_REQUIRED","research_only":True,"portfolio_authorized":False,"trade_authorized":False}
