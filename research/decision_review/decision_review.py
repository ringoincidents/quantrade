"""Decision review routing prototype; no model calls or authority grants.
Uses the existing institutional ReviewGate. Fixed categories, not invented scores.
"""
from dataclasses import dataclass,asdict
from quantrade.capabilities.review_gate import ReviewEvent,evaluate_review_need

POLICY_VERSION="decision-review-draft.v0.1"
# Materiality values encode categories into the existing gate, not probabilities.
KINDS={
    "DOC_UI_ROUTINE":(0,.10),"LOCAL_BUG_FIX":(0,.10),
    "EXISTING_MODULE_EXTENSION":(1,.30),"REGRESSION_TEST":(1,.30),
    "NEW_HYPOTHESIS":(2,.60),"BACKTEST_DESIGN":(2,.60),"ALGORITHM_CHANGE":(2,.60),
    "STRATEGY_ADOPTION":(3,.90),"SECURITY_BOUNDARY":(3,.90),
    "CORE_ARCHITECTURE":(3,.90),"PRODUCTION_CUTOVER":(3,.90),
    "CAPITAL_AUTHORITY":(3,.90),"PRIVATE_DATA_DISCLOSURE":(3,.90),
    "COST_COMMITMENT":(3,.90),"IRREVERSIBLE_DATA_CHANGE":(3,.90),
}
CRITICAL={"RISK_POLICY_BREACH","CLIENT_MANDATE_CONFLICT","LIQUIDITY_CONSTRAINT_BREACH"}
EXTERNAL_SCOPES={"PUBLIC_APPROVED","SYNTHETIC_APPROVED"}

@dataclass(frozen=True)
class Case:
    kind:str
    security_impact:bool=False
    capital_impact:bool=False
    privacy_impact:bool=False
    production_impact:bool=False
    irreversible:bool=False
    extra_cost:bool=False
    unresolved_material_finding:bool=False
    uncertain_scope:bool=False

def route(case:Case):
    if not isinstance(case,Case):
        raise ValueError("INVALID_CASE")
    flags=asdict(case)
    if not isinstance(case.kind,str) or any(type(v) is not bool for k,v in flags.items() if k!="kind"):
        raise ValueError("INVALID_CASE")
    unknown=case.kind not in KINDS and case.kind not in CRITICAL
    grade,materiality=KINDS.get(case.kind,(3,.90))
    reasons=[]
    for key,value in flags.items():
        if key!="kind" and value:
            reasons.append(key.upper())
    if reasons or unknown:
        grade=3
        materiality=.90
    if unknown:reasons.append("UNCLASSIFIED_SCOPE")
    gate=evaluate_review_need((ReviewEvent(case.kind or "UNCLASSIFIED",materiality,"Chief of Staff",case.unresolved_material_finding),))
    n=2 if grade==3 else 1 if grade==2 else 0
    return {"schema":POLICY_VERSION,"grade":"D"+str(grade),"institutional_gate":gate.level,
        "reasons":reasons or [case.kind],"required_independent_reviews":n,
        "founder_approval_required":grade==3,"routine_evidence":"COMMIT_AND_TEST" if grade<2 else "REVIEW_RECORD",
        "exploration_allowed":True,"adoption_requires_review":grade>=2,
        "external_call_authorized":False,"decision_authorized":False,"order_authorized":False}

def call_plan(case:Case,*,scope="UNKNOWN",provider_approved=False,
              max_calls_remaining=0,budget_reserved=False):
    """Reservation flag is a declaration, not a financial authorization.
    Zero by default. Caller must enforce hard spend limits and verified scope.
    Never substitutes a cheaper unapproved model or downgrades required review.
    """
    policy=route(case);n=policy["required_independent_reviews"]
    if type(max_calls_remaining) is not int or max_calls_remaining<0 or type(provider_approved) is not bool or type(budget_reserved) is not bool:
        raise ValueError("INVALID_CALL_CONSTRAINT")
    if n==0:state="NO_EXTERNAL_REVIEW_NEEDED";count=0
    elif scope not in EXTERNAL_SCOPES:state="BLOCKED_DISCLOSURE_SCOPE";count=0
    elif not provider_approved:state="BLOCKED_PROVIDER_APPROVAL";count=0
    elif not budget_reserved or max_calls_remaining<n:state="BLOCKED_BUDGET";count=0
    else:state="CANDIDATE_PLAN_ONLY";count=n
    return {**policy,"call_plan_state":state,"planned_calls":count,
        "review_completed":False,"external_call_authorized":False}
