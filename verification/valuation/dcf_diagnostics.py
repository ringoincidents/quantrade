"""Research-only diagnostic wrapper around the original per-share DCF.
No FCFF/WACC conversion, live estimates, investment decisions or adopted policy.
"""
from dataclasses import replace,asdict
from datetime import datetime
from decimal import Decimal,localcontext,InvalidOperation
import hashlib,json,math
from quantrade.capabilities.cash_flow_valuation import CashFlowDCFInput,evaluate_cash_flow_dcf

def require(ok,reason):
    if not ok:raise ValueError(reason)
def number(x):
    require(type(x) in (int,float),"NUMERIC_TYPE")
    require(math.isfinite(x) and abs(x)<=1e12,"NUMERIC_BOUND")
    return Decimal(str(x))
def stamp(s):
    try:d=datetime.fromisoformat(s)
    except (ValueError,TypeError):raise ValueError("AS_OF")
    require(d.tzinfo is not None,"AS_OF_TIMEZONE")
    return d
def guard(request,*,cash_flow_basis,discount_basis):
    require(isinstance(request,CashFlowDCFInput),"INPUT")
    # Per-share equity cash flow is discounted at cost of equity, NOT WACC.
    require(cash_flow_basis=="FCFE_PER_SHARE" and discount_basis=="COST_OF_EQUITY","CASH_FLOW_DISCOUNT_MISMATCH")
    stamp(request.as_of)
    require(request.currency in {"KRW","USD"},"CURRENCY")
    require(number(request.current_price)>0 and number(request.owner_cash_flow_per_share)>0,"POSITIVE_PRICE_AND_CASH_FLOW")
    require(0<=number(request.required_return_pct)<=100,"HURDLE_BOUND")
    require(1<=len(request.scenarios)<=10,"SCENARIO_COUNT")
    require(sum(number(s.probability) for s in request.scenarios)==1,"PROBABILITY_SUM_EXACT")
    for s in request.scenarios:
        require(type(s.explicit_years) is int and 1<=s.explicit_years<=30,"HORIZON_BOUND")
        require(0<=number(s.probability)<=1,"PROBABILITY")
        require(0<number(s.starting_cash_flow_factor)<=10,"ANCHOR_FACTOR")
        require(-90<=number(s.explicit_growth_pct)<=100,"EXPLICIT_GROWTH_BOUND")
        require(-10<=number(s.terminal_growth_pct)<=10,"TERMINAL_GROWTH_BOUND")
        require(0<number(s.discount_rate_pct)<=50,"DISCOUNT_BOUND")
        require(number(s.discount_rate_pct)-number(s.terminal_growth_pct)>=1,"TERMINAL_SPREAD_MINIMUM")
        require(bool(s.assumption_refs) and all(isinstance(r,str) and r.strip() for r in s.assumption_refs),"ASSUMPTION_REFERENCE_REQUIRED")

def independent(anchor,s):
    """Independent decimal computation, not a second economic valuation model."""
    with localcontext() as c:
        c.prec=50
        f=number(anchor)*number(s.starting_cash_flow_factor)
        g=number(s.explicit_growth_pct)/100
        t=number(s.terminal_growth_pct)/100
        k=number(s.discount_rate_pct)/100
        explicit=sum(f*(1+g)**n/(1+k)**n for n in range(1,s.explicit_years+1))
        terminal=f*(1+g)**s.explicit_years*(1+t)/(k-t)/(1+k)**s.explicit_years
        total=explicit+terminal
        return total,terminal/total*100

def output(d):
    require(d.is_finite() and abs(d)<=Decimal("1e20"),"OUTPUT_BOUND")
    return str(d.quantize(Decimal("0.000001")))
def checked(request,*,cash_flow_basis,discount_basis):
    with localcontext() as c:
        c.prec=50
        guard(request,cash_flow_basis=cash_flow_basis,discount_basis=discount_basis)
        artifact=evaluate_cash_flow_dcf(request)
        values=[]
        for s,row in zip(request.scenarios,artifact.scenarios):
            v,t=independent(request.owner_cash_flow_per_share,s)
            raw=row["fair_value"]
            require(math.isfinite(raw),"NONFINITE_LEGACY_RESULT")
            require(abs(v-Decimal(str(raw)))<=max(Decimal("0.000001"),abs(v)*Decimal("1e-10")),"ARITHMETIC_MISMATCH")
            values.append((s,v,t))
        weighted=sum(number(s.probability)*v for s,v,t in values)
        require(abs(weighted-Decimal(str(artifact.metrics["weighted_fair_value"])))<=max(Decimal("0.000001"),abs(weighted)*Decimal("1e-10")),"WEIGHTED_ARITHMETIC_MISMATCH")
        return artifact,values,weighted

def diagnostics(request,*,cash_flow_basis,discount_basis,scenario_id,discount_shifts=(-2,0,2),growth_shifts=(-2,0,2),margin_of_safety_pct=20):
    with localcontext() as c:
        c.prec=50
        kw=dict(cash_flow_basis=cash_flow_basis,discount_basis=discount_basis)
        artifact,values,weighted=checked(request,**kw)
        require(0<=number(margin_of_safety_pct)<100,"MARGIN_BOUND")
        require(len(discount_shifts)<=9 and len(growth_shifts)<=9 and len(discount_shifts)>0 and len(growth_shifts)>0,"GRID_BOUND")
        require(all(type(x) is int and -10<=x<=10 for x in (*discount_shifts,*growth_shifts)),"GRID_SHIFT_BOUND")
        require(len(set(discount_shifts))==len(discount_shifts) and len(set(growth_shifts))==len(growth_shifts),"GRID_DUPLICATE")
        matches=[s for s in request.scenarios if s.scenario_id==scenario_id]
        require(len(matches)==1,"SCENARIO_ID")
        base=matches[0];grid=[]
        for ds in discount_shifts:
            for gs in growth_shifts:
                s=replace(base,discount_rate_pct=base.discount_rate_pct+ds,explicit_growth_pct=base.explicit_growth_pct+gs)
                q=replace(request,scenarios=(replace(s,probability=1),))
                cell={"discount_rate_pct":s.discount_rate_pct,"explicit_growth_pct":s.explicit_growth_pct}
                try:guard(q,**kw)
                except ValueError as e:grid.append(dict(cell,state="BLOCKED",reason=str(e)));continue
                _,_,v=checked(q,**kw)
                grid.append(dict(cell,state="CALCULATED",fair_value=output(v)))
        # Implied explicit growth, other assumptions fixed; no extrapolation beyond bounds.
        lo=Decimal("-90");hi=Decimal("100");price=number(request.current_price)
        def value(g):return independent(request.owner_cash_flow_per_share,replace(base,explicit_growth_pct=float(g)))[0]
        if not value(lo)<=price<=value(hi):
            reverse={"state":"OUTSIDE_SEARCH_RANGE","growth_pct":None}
        else:
            for _ in range(70):
                mid=(lo+hi)/2
                if value(mid)<price:lo=mid
                else:hi=mid
            implied=(lo+hi)/2
            reverse={"state":"SOLVED_CONDITIONAL","growth_pct":output(implied),"price_residual":output(value(implied)-price),"scenario_id":scenario_id,"fixed_discount_rate_pct":base.discount_rate_pct,"fixed_terminal_growth_pct":base.terminal_growth_pct}
        return {"schema":"qt_dcf_diagnostics_research_v1","case_id":request.case_id,"input_sha256":hashlib.sha256(json.dumps(asdict(request),sort_keys=True,allow_nan=False).encode()).hexdigest(),
            "basis":{"cash_flow":cash_flow_basis,"discount_rate":discount_basis,"basis_verified":False},
            "weighted_fair_value":output(weighted),
            "valuation_gap_pct":output((weighted/price-1)*100),
            "margin_of_safety_pct":margin_of_safety_pct,
            "illustrative_entry_price":output(weighted*(1-number(margin_of_safety_pct)/100)),
            "scenarios":[{"id":s.scenario_id,"fair_value":output(v),"terminal_value_share_pct":output(t),"terminal_dominant":t>=70} for s,v,t in values],
            "sensitivity":{"scenario_id":scenario_id,"cells":grid,"scope":"EXPLICIT_GROWTH_AND_COST_OF_EQUITY"},
            "reverse_dcf":reverse,"arithmetic_crosscheck":"PASS","assumptions_validated":False,
            "valuation_gap_is_annualized_return":False,"research_only":True,"portfolio_authorized":False,"trade_authorized":False}
