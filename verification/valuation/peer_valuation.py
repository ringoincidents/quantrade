"""Synthetic relative-valuation diagnostic; not an approved peer universe or fair value."""
from dataclasses import dataclass,asdict
from datetime import date
from decimal import Decimal,localcontext
import math
from method_gate import require,nonempty,time,digest,ComparableMethod
from quantrade.capabilities.valuation_crosscheck import ValuationMethodSnapshot,ValuationScenarioSnapshot

@dataclass(frozen=True)
class Adjustment:
    id:str
    category:str
    reported_income_effect:float  # signed, AFTER tax, attributable to common shareholders
    reported_ebitda_effect:float  # signed, BEFORE tax, only if included in EBITDA
    source_ref:str
@dataclass(frozen=True)
class Firm:
    asset_id:str
    business_group:str
    geography:str
    accounting_basis:str
    currency:str
    period_start:str
    period_end:str
    published_at:str
    quote_as_of:str
    price:float
    diluted_shares:float  # current fully diluted share basis, supplied
    common_income:float
    ebitda:float
    debt:float
    preferred:float
    nci:float
    other_claims:float
    excess_cash:float
    nonoperating_assets:float
    revenue:float
    revenue_growth_pct:float
    operating_margin_pct:float
    adjustments:tuple[Adjustment,...]
    source_refs:tuple[str,...]
@dataclass(frozen=True)
class Scenario:
    id:str
    probability:float
    normalized_income_factor:float
    normalized_ebitda_factor:float
    peer_quantile_pct:int
    assumption_refs:tuple[str,...]
@dataclass(frozen=True)
class Request:
    case_id:str
    as_of:str
    quote_ref:str
    share_basis_ref:str
    scenario_definition_ref:str
    universe_ref:str
    target:Firm
    peers:tuple[Firm,...]
    scenarios:tuple[Scenario,...]
    method:str
    min_peers:int=3
    max_growth_gap_pp:float=15
    max_margin_gap_pp:float=10
    max_size_ratio:float=10

ALLOWED_ADJUSTMENTS={"DISPOSAL_GAIN_LOSS","LITIGATION_SETTLEMENT","DISASTER_LOSS"}
def d(x):
    require(type(x) in (int,float) and math.isfinite(x) and abs(x)<=1e18,"NUMBER")
    return Decimal(str(x))
def source(s):
    require(nonempty(s) and s.startswith("synthetic:"),"SYNTHETIC_SOURCE_REQUIRED")
def source_list(xs):
    require(isinstance(xs,tuple) and 0<len(xs)<=64 and len(set(xs))==len(xs),"SOURCE_REFS")
    for x in xs:source(x)
def out(x):
    require(x.is_finite() and abs(x)<=Decimal("1e24"),"OUTPUT_BOUND")
    return str(x.quantize(Decimal("0.000001")))
def normalized(f,cutoff):
    require(isinstance(f,Firm),"FIRM_SCHEMA")
    for s in (f.asset_id,f.business_group,f.geography,f.accounting_basis):require(nonempty(s),"FIRM_IDENTITY")
    require(f.currency in {"USD","KRW"},"CURRENCY")
    source_list(f.source_refs)
    start=date.fromisoformat(f.period_start);end=date.fromisoformat(f.period_end)
    require(350<=(end-start).days<=380,"PERIOD_LENGTH")
    pub=time(f.published_at);quote=time(f.quote_as_of)
    require(end<=pub.date() and pub<=quote<=cutoff,"PIT_OR_QUOTE")
    p,shares,revenue=d(f.price),d(f.diluted_shares),d(f.revenue)
    require(p>0 and shares>0 and revenue>0,"CAPITAL_OR_REVENUE")
    income,ebitda=d(f.common_income),d(f.ebitda)
    require(isinstance(f.adjustments,tuple) and len(f.adjustments)<=32,"ADJUSTMENT_COUNT")
    ids=set()
    for a in f.adjustments:
        require(isinstance(a,Adjustment) and nonempty(a.id) and a.id not in ids,"ADJUSTMENT_ID")
        ids.add(a.id);source(a.source_ref)
        require(a.category in ALLOWED_ADJUSTMENTS,"ADJUSTMENT_CATEGORY")
        income-=d(a.reported_income_effect);ebitda-=d(a.reported_ebitda_effect)
    claims=tuple(d(getattr(f,k)) for k in ("debt","preferred","nci","other_claims","excess_cash","nonoperating_assets"))
    require(all(x>=0 for x in claims),"NEGATIVE_CLAIM")
    debt,pref,nci,other,cash,assets=claims
    bridge=debt+pref+nci+other-cash-assets
    market_cap=p*shares;ev=market_cap+bridge
    growth,margin=d(f.revenue_growth_pct),d(f.operating_margin_pct)
    require(-100<=growth<=1000 and -1000<=margin<=100,"METRIC_DOMAIN")
    return {"income":income,"ebitda":ebitda,"shares":shares,"price":p,"revenue":revenue,"growth":growth,"margin":margin,"bridge":bridge,"market_cap":market_cap,"ev":ev}
def quantile(values,q):
    require(bool(values) and q in (25,50,75),"QUANTILE")
    ordered=sorted(values);pos=Decimal(len(ordered)-1)*Decimal(q)/100
    i=int(pos);j=min(i+1,len(ordered)-1)
    return ordered[i]+(ordered[j]-ordered[i])*(pos-i)
def evaluate(r,*,scope):
    require(scope=="SYNTHETIC_ONLY","LIVE_SCOPE_BLOCKED")
    require(isinstance(r,Request) and r.method in {"PE","EV_EBITDA"},"METHOD")
    require(nonempty(r.case_id),"CASE")
    for ref in (r.quote_ref,r.share_basis_ref,r.scenario_definition_ref,r.universe_ref):source(ref)
    cutoff=time(r.as_of)
    require(isinstance(r.peers,tuple) and 1<=len(r.peers)<=50 and all(isinstance(f,Firm) for f in r.peers),"PEER_COUNT")
    require(len({f.asset_id for f in r.peers})==len(r.peers),"DUPLICATE_PEER")
    require(type(r.min_peers) is int and 3<=r.min_peers<=50,"MIN_PEERS")
    require(0<=d(r.max_growth_gap_pp)<=100 and 0<=d(r.max_margin_gap_pp)<=100 and 1<=d(r.max_size_ratio)<=100,"SCREEN_BOUND")
    with localcontext() as ctx:
        ctx.prec=60
        t=normalized(r.target,cutoff)
        require(r.quote_ref in r.target.source_refs and r.share_basis_ref in r.target.source_refs,"TARGET_CONTEXT_REFS")
        target_metric=t["income"] if r.method=="PE" else t["ebitda"]
        require(target_metric>0,"TARGET_DENOMINATOR_NONPOSITIVE")
        require(r.method!="EV_EBITDA" or t["ev"]>0,"TARGET_EV_NONPOSITIVE")
        excluded=[];included=[];multiples=[];eligible_firms=[]
        for f in r.peers:
            reason=[]
            if f.asset_id==r.target.asset_id:reason.append("SELF")
            for k in ("business_group","geography","accounting_basis","currency","period_start","period_end"):
                if getattr(f,k)!=getattr(r.target,k):reason.append("MISMATCH_"+k.upper())
            try:
                p=normalized(f,cutoff)
                if time(f.quote_as_of)!=time(r.target.quote_as_of):reason.append("MISMATCH_QUOTE")
                if abs(p["growth"]-t["growth"])>d(r.max_growth_gap_pp):reason.append("GROWTH_GAP")
                if abs(p["margin"]-t["margin"])>d(r.max_margin_gap_pp):reason.append("MARGIN_GAP")
                if max(p["revenue"]/t["revenue"],t["revenue"]/p["revenue"])>d(r.max_size_ratio):reason.append("SIZE_GAP")
                denominator=p["income"] if r.method=="PE" else p["ebitda"]
                numerator=p["market_cap"] if r.method=="PE" else p["ev"]
                if min(denominator,numerator)<=0:reason.append("NONPOSITIVE_MULTIPLE_COMPONENT")
            except ValueError as e:reason.append("INVALID_INPUT:"+str(e))
            if reason:
                excluded.append({"asset_id":f.asset_id,"reasons":reason});continue
            mult=numerator/denominator;multiples.append(mult);eligible_firms.append(f)
            included.append({"asset_id":f.asset_id,"normalized_income":out(p["income"]),"normalized_ebitda":out(p["ebitda"]),"multiple":out(mult)})
        base={"schema":"qt_relative_valuation_research_v1","input_sha256":digest(asdict(r)),"case_id":r.case_id,"method":r.method,"included":included,"excluded":excluded,"universe_complete_verified":False,"source_verified":False,"adjustments_verified":False,"thresholds_adopted":False,"portfolio_authorized":False,"trade_authorized":False}
        if len(multiples)<r.min_peers:return dict(base,state="BLOCKED_INSUFFICIENT_PEERS"),None
        q={i:quantile(multiples,i) for i in (25,50,75)}
        # No removal of extreme multiples based on the output; show full range.
        require(isinstance(r.scenarios,tuple) and 1<=len(r.scenarios)<=10 and all(isinstance(s,Scenario) for s in r.scenarios),"SCENARIOS")
        require(len({s.id for s in r.scenarios})==len(r.scenarios),"DUPLICATE_SCENARIO")
        require(sum(d(s.probability) for s in r.scenarios)==1,"PROBABILITY_SUM")
        rows=[];weighted=Decimal(0);snap=[]
        for s in r.scenarios:
            require(nonempty(s.id) and 0<=d(s.probability)<=1,"SCENARIO")
            source_list(s.assumption_refs)
            require(type(s.peer_quantile_pct) is int and s.peer_quantile_pct in q,"QUANTILE")
            fi,fe=d(s.normalized_income_factor),d(s.normalized_ebitda_factor)
            require(0<fi<=10 and 0<fe<=10,"SCENARIO_FACTOR")
            equity=(t["income"]*fi*q[s.peer_quantile_pct]) if r.method=="PE" else (t["ebitda"]*fe*q[s.peer_quantile_pct]-t["bridge"])
            require(equity>0,"NONPOSITIVE_RESIDUAL_EQUITY")
            per=equity/t["shares"];weighted+=d(s.probability)*per
            rows.append({"id":s.id,"probability":s.probability,"multiple":out(q[s.peer_quantile_pct]),"fair_value_per_share":out(per)})
            snap.append(ValuationScenarioSnapshot(s.id,s.probability,float(per)))
        ir=tuple(sorted({ref for f in (r.target,*eligible_firms) for ref in (*f.source_refs,*(a.source_ref for a in f.adjustments)) if isinstance(ref,str) and ref.startswith("synthetic:")}))
        # Input references must be compact; refuse instead of truncating evidence.
        require(len(ir)<=64,"INPUT_REF_BOUND")
        ar=tuple(sorted({r.universe_ref,*[ref for s in r.scenarios for ref in s.assumption_refs]}))
        require(len(ar)<=64,"ASSUMPTION_REF_BOUND")
        h=base["input_sha256"]
        sm=ValuationMethodSnapshot("relative-"+h[:16],r.method,base["schema"],float(t["price"]),0,tuple(snap),("synthetic:relative:"+h,))
        cm=ComparableMethod(sm,r.case_id,r.target.asset_id,r.target.currency,r.as_of,r.target.quote_as_of,r.quote_ref,r.share_basis_ref,r.scenario_definition_ref,"PRESENT_EQUITY_PER_DILUTED_SHARE",0,ir,ar)
        return dict(base,state="REVIEW_REQUIRED",target_normalized_income=out(t["income"]),target_normalized_eps=out(t["income"]/t["shares"]),target_normalized_ebitda=out(t["ebitda"]),target_ev_equity_bridge=out(t["bridge"]),multiple_distribution={"min":out(min(multiples)),"p25":out(q[25]),"median":out(q[50]),"p75":out(q[75]),"max":out(max(multiples))},scenarios=rows,weighted_fair_value_per_share=out(weighted),valuation_gap_pct=out((weighted/t["price"]-1)*100),valuation_gap_is_annualized_return=False),cm
