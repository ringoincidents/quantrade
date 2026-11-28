"""Synthetic operating-company FCFF / WACC research diagnostic.
Inputs are explicit unverified assumptions, in one declared currency and full units.
No sector inference, live sources, approved valuation or trade authority.
"""
from dataclasses import dataclass,asdict
from decimal import Decimal,localcontext
from method_gate import require,nonempty,time,digest
from quantrade.capabilities.valuation_crosscheck import ValuationMethodSnapshot,ValuationScenarioSnapshot
from method_gate import ComparableMethod
import math

@dataclass(frozen=True)
class Amount:
    value:float
    unit:str
    source_ref:str
    observed_at:str
@dataclass(frozen=True)
class Year:
    ebit:float
    tax_pct:float
    depreciation:float
    capex:float
    increase_operating_nwc:float
@dataclass(frozen=True)
class Scenario:
    id:str
    probability:float
    years:tuple[Year,...]
    terminal_growth_pct:float
    terminal_roic_pct:float
    terminal_tax_pct:float
    risk_free_pct:float
    beta:float
    equity_risk_premium_pct:float
    pretax_debt_cost_pct:float
    marginal_tax_pct:float
    target_debt_weight_pct:float
    assumption_refs:tuple[str,...]
@dataclass(frozen=True)
class Request:
    case_id:str
    asset_id:str
    currency:str
    as_of:str
    quote_as_of:str
    quote_ref:str
    share_basis_ref:str
    scenario_definition_ref:str
    current_price:Amount
    market_equity:Amount
    market_debt:Amount
    excess_cash:Amount
    nonoperating_assets:Amount
    noncontrolling_interests:Amount
    preferred_claims:Amount
    other_debt_like_claims:Amount
    diluted_shares:Amount
    scenarios:tuple[Scenario,...]
    profile:str="OPERATING"
    basis:str="FCFF_WACC"
    unit_scale:str="FULL_UNITS"
    lease_policy:str="DEBT_INCLUDES_LEASES_FCFF_EXCLUDES_FINANCING"

def d(x):
    require(type(x) in (int,float) and math.isfinite(x) and abs(x)<=1e18,"NUMBER")
    return Decimal(str(x))
def pct(x,lo=0,hi=100):
    v=d(x);require(lo<=v<=hi,"PERCENT_BOUND");return v/100
def source(s):
    require(nonempty(s) and s.startswith("synthetic:"),"SYNTHETIC_SOURCE_REQUIRED")
def money(x,unit,cutoff):
    require(isinstance(x,Amount) and x.unit==unit,"UNIT_MISMATCH")
    source(x.source_ref);require(time(x.observed_at)<=cutoff,"FUTURE_SOURCE")
    v=d(x.value);require(v>=0,"NEGATIVE_CAPITAL_CLAIM");return v
def out(x):
    require(x.is_finite() and abs(x)<=Decimal("1e24"),"OUTPUT_BOUND")
    return str(x.quantize(Decimal("0.000001")))
def calc_wacc(s):
    rf=pct(s.risk_free_pct,0,30);beta=d(s.beta);require(0<=beta<=5,"BETA_BOUND")
    erp=pct(s.equity_risk_premium_pct,0,30)
    ke=rf+beta*erp
    kd=pct(s.pretax_debt_cost_pct,0,50)
    tax=pct(s.marginal_tax_pct,0,60);wd=pct(s.target_debt_weight_pct,0,95)
    require(0<ke<=Decimal(".8"),"COST_OF_EQUITY_BOUND")
    w=(1-wd)*ke+wd*kd*(1-tax)
    require(0<w<=Decimal(".8"),"WACC_BOUND")
    return ke,kd*(1-tax),w,wd
def year_fcff(y):
    require(isinstance(y,Year),"YEAR_SCHEMA")
    ebit=d(y.ebit);tax=pct(y.tax_pct,0,60)
    dep=d(y.depreciation);capex=d(y.capex);nwc=d(y.increase_operating_nwc)
    require(dep>=0 and capex>=0,"NEGATIVE_DEPRECIATION_OR_CAPEX")
    # No invented tax shield on operating losses: actual loss carryforward schedule
    # would require a separate model.
    nopat=ebit-max(ebit,Decimal(0))*tax
    return nopat,nopat+dep-capex-nwc
def scenario(s):
    require(isinstance(s,Scenario) and nonempty(s.id),"SCENARIO")
    require(isinstance(s.years,tuple) and 1<=len(s.years)<=30,"HORIZON")
    require(isinstance(s.assumption_refs,tuple) and 0<len(s.assumption_refs)<=64 and len(set(s.assumption_refs))==len(s.assumption_refs),"ASSUMPTIONS")
    for ref in s.assumption_refs:source(ref)
    prob=d(s.probability)
    require(0<=prob<=1,"PROBABILITY")
    ke,kda,w,wd=calc_wacc(s)
    growth=pct(s.terminal_growth_pct,-5,10)
    roic=pct(s.terminal_roic_pct,1,100)
    require(w-growth>=Decimal(".01"),"TERMINAL_SPREAD")
    require(0<=growth/roic<=1,"TERMINAL_REINVESTMENT_DOMAIN")
    tt=pct(s.terminal_tax_pct,0,60)
    rows=[];pv=Decimal(0)
    for n,y in enumerate(s.years,1):
        nopat,fcff=year_fcff(y);df=(1+w)**n
        pv+=fcff/df
        rows.append({"year":n,"nopat":out(nopat),"fcff":out(fcff),"present_value":out(fcff/df)})
    terminal_ebit=d(s.years[-1].ebit)*(1+growth)
    require(terminal_ebit>0,"TERMINAL_OPERATING_PROFIT_REQUIRED")
    terminal_nopat=terminal_ebit*(1-tt)
    reinvest=terminal_nopat*growth/roic
    terminal_fcff=terminal_nopat-reinvest
    require(terminal_fcff>0,"TERMINAL_FCFF_REQUIRED")
    terminal_pv=terminal_fcff/(w-growth)/(1+w)**len(s.years)
    enterprise=pv+terminal_pv
    require(enterprise>0,"NONPOSITIVE_ENTERPRISE")
    return enterprise,{"id":s.id,"probability":s.probability,"cost_of_equity_pct":out(ke*100),"after_tax_debt_cost_pct":out(kda*100),"wacc_pct":out(w*100),"target_debt_weight_pct":out(wd*100),"years":rows,"terminal_nopat":out(terminal_nopat),"terminal_reinvestment":out(reinvest),"terminal_fcff":out(terminal_fcff),"terminal_pv":out(terminal_pv),"terminal_share_pct":out(terminal_pv/enterprise*100),"enterprise_value":out(enterprise)}

def evaluate(r,*,scope):
    require(scope=="SYNTHETIC_ONLY","LIVE_SCOPE_BLOCKED")
    require(isinstance(r,Request) and r.profile=="OPERATING" and r.basis=="FCFF_WACC","PROFILE_OR_BASIS")
    require(r.unit_scale=="FULL_UNITS" and r.lease_policy=="DEBT_INCLUDES_LEASES_FCFF_EXCLUDES_FINANCING","ACCOUNTING_BASIS")
    require(nonempty(r.case_id) and nonempty(r.asset_id) and r.currency in {"KRW","USD"},"CONTEXT")
    cutoff=time(r.as_of);qt=time(r.quote_as_of);require(qt<=cutoff,"FUTURE_QUOTE")
    for ref in (r.quote_ref,r.share_basis_ref,r.scenario_definition_ref):source(ref)
    with localcontext() as ctx:
        ctx.prec=60
        price=money(r.current_price,r.currency+"_PER_SHARE",cutoff)
        require(time(r.current_price.observed_at)==qt and r.current_price.source_ref==r.quote_ref,"QUOTE_BINDING")
        shares=money(r.diluted_shares,"SHARES",cutoff);require(r.diluted_shares.source_ref==r.share_basis_ref,"SHARE_BINDING")
        e=money(r.market_equity,r.currency,cutoff);debt=money(r.market_debt,r.currency,cutoff)
        require(price>0 and shares>0 and e>0,"CAPITAL_BASE")
        require(time(r.market_equity.observed_at)==qt,"MARKET_EQUITY_AS_OF")
        cash=money(r.excess_cash,r.currency,cutoff);assets=money(r.nonoperating_assets,r.currency,cutoff)
        nci=money(r.noncontrolling_interests,r.currency,cutoff);pref=money(r.preferred_claims,r.currency,cutoff);other=money(r.other_debt_like_claims,r.currency,cutoff)
        # Each amount is separately declared; equal refs may legitimately originate in
        # one filing, but economic overlap cannot be verified by this prototype.
        require(isinstance(r.scenarios,tuple) and 1<=len(r.scenarios)<=10 and all(isinstance(s,Scenario) for s in r.scenarios),"SCENARIO_COUNT")
        require(len({s.id for s in r.scenarios})==len(r.scenarios),"DUPLICATE_SCENARIO")
        require(sum(d(s.probability) for s in r.scenarios)==1,"PROBABILITY_SUM")
        current_wd=debt/(debt+e)*100
        adjustments=cash+assets-debt-nci-pref-other
        rows=[];weighted=Decimal(0);snapshots=[]
        for s in r.scenarios:
            ev,row=scenario(s)
            equity=ev+adjustments
            # Negative residual is not a negative traded share price or a usable
            # cross-method value. Refuse the scenario rather than clipping it.
            require(equity>0,"NONPOSITIVE_RESIDUAL_EQUITY")
            per=equity/shares;weighted+=d(s.probability)*per
            rows.append(dict(row,common_equity_value=out(equity),fair_value_per_share=out(per),target_minus_current_debt_weight_pp=out(d(s.target_debt_weight_pct)-current_wd)))
            snapshots.append(ValuationScenarioSnapshot(s.id,s.probability,float(per)))
        h=digest(asdict(r))
        sr=tuple(sorted({getattr(r,k).source_ref for k in ("current_price","market_equity","market_debt","excess_cash","nonoperating_assets","noncontrolling_interests","preferred_claims","other_debt_like_claims","diluted_shares")}))
        ar=tuple(sorted({ref for s in r.scenarios for ref in s.assumption_refs}))
        snapshot=ValuationMethodSnapshot("fcff-"+h[:16],"FCFF_DCF","qt_fcff_wacc_research_v1",float(price),0,tuple(snapshots),("synthetic:fcff:"+h,))
        comparable=ComparableMethod(snapshot,r.case_id,r.asset_id,r.currency,r.as_of,r.quote_as_of,r.quote_ref,r.share_basis_ref,r.scenario_definition_ref,"PRESENT_EQUITY_PER_DILUTED_SHARE",0,sr,ar)
        return {"schema":"qt_fcff_wacc_research_v1","input_sha256":h,"case_id":r.case_id,"currency":r.currency,"current_market_debt_weight_pct":out(current_wd),"equity_bridge":{"excess_cash":out(cash),"nonoperating_assets":out(assets),"market_debt":out(debt),"noncontrolling_interests":out(nci),"preferred_claims":out(pref),"other_debt_like_claims":out(other),"net_adjustment":out(adjustments),"diluted_shares":out(shares)},"scenarios":rows,"weighted_fair_value_per_share":out(weighted),"valuation_gap_pct":out((weighted/price-1)*100),"state":"REVIEW_REQUIRED","synthetic_only":True,"source_verified":False,"assumptions_validated":False,"economic_overlap_verified":False,"valuation_gap_is_annualized_return":False,"portfolio_authorized":False,"trade_authorized":False},comparable
