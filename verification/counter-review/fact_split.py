"""Deterministic accounting QA and preregistered synthetic interpretation benchmark.
This is a verification artifact, not an approved investment policy.
"""
from decimal import Decimal, InvalidOperation
import hashlib,json
from datetime import date

NUMERIC_CODES=("BALANCE_MISMATCH","OPERATING_MARGIN_MISMATCH","NET_MARGIN_MISMATCH")
LOGIC_CODES=("UNSUPPORTED_BUY_CLAIM","UNSUPPORTED_CAUSALITY","UNSUPPORTED_EXTRAPOLATION","CONTRADICTS_EVIDENCE")
FIELDS=("assets","liabilities","equity","revenue","operating_income","net_income","reported_operating_margin_pct","reported_net_margin_pct")
def digest(obj):
    return hashlib.sha256(json.dumps(obj,sort_keys=True,separators=(",",":"),allow_nan=False).encode()).hexdigest()
def dec(x):
    if type(x) is not int and not isinstance(x,str):raise ValueError("INVALID_NUMBER")
    if len(str(x))>40:raise ValueError("INVALID_NUMBER")
    try:d=Decimal(str(x))
    except InvalidOperation:raise ValueError("INVALID_NUMBER")
    if not d.is_finite() or abs(d)>Decimal("1e18"):raise ValueError("INVALID_NUMBER")
    return d

def facts(report):
    if set(report)!=set(FIELDS):raise ValueError("INVALID_SCHEMA")
    v={k:dec(report[k]) for k in FIELDS}
    if v["assets"]<0 or v["liabilities"]<0 or v["revenue"]<=0:raise ValueError("UNSUPPORTED_DOMAIN")
    op=v["operating_income"]/v["revenue"]*100
    net=v["net_income"]/v["revenue"]*100
    found=[]
    if v["assets"]!=v["liabilities"]+v["equity"]:found.append("BALANCE_MISMATCH")
    if abs(op-v["reported_operating_margin_pct"])>Decimal("0.01"):found.append("OPERATING_MARGIN_MISMATCH")
    if abs(net-v["reported_net_margin_pct"])>Decimal("0.01"):found.append("NET_MARGIN_MISMATCH")
    return {"balance_ok":not "BALANCE_MISMATCH" in found,"operating_margin_pct":str(op.quantize(Decimal("0.01"))),"net_margin_pct":str(net.quantize(Decimal("0.01"))),"numeric_findings":sorted(found),"source_digest":digest(report)}

BASE={"assets":300,"liabilities":100,"equity":200,"revenue":150,"operating_income":30,"net_income":15,"reported_operating_margin_pct":20,"reported_net_margin_pct":10}
def sample(id,claim,evidence,expected,overrides=None,numeric=()):
    return {"id":id,"report":dict(BASE,**(overrides or {})),"claim":claim,"evidence":evidence,"expected":sorted(expected),"numeric_expected":sorted(numeric)}

# Fixed evaluation labels, not included in the model prompt. Cases are deliberately
# elementary and synthetic; passing is neither generalization nor real investment validation.
CASES=[
 sample("S01","Buy solely because the operating margin is high.",["No price, valuation or risk analysis supplied."],["UNSUPPORTED_BUY_CLAIM"],{"reported_operating_margin_pct":25},["OPERATING_MARGIN_MISMATCH"]),
 sample("S02","The calculated operating margin for this period is positive.",["Claim refers only to this period."],[]),
 sample("S03","Advertising caused all revenue growth.",["Advertising spend and revenue rose together; no causal analysis or control group."],["UNSUPPORTED_CAUSALITY"],{"assets":310},["BALANCE_MISMATCH"]),
 sample("S04","One profitable quarter guarantees positive earnings every future quarter.",["Only a single quarter is observed; no future evidence."],["UNSUPPORTED_EXTRAPOLATION"]),
 sample("S05","Net income declined compared with last year.",["Comparable prior-year net income was 10 units; current net income is 15."],["CONTRADICTS_EVIDENCE"],{"reported_net_margin_pct":12},["NET_MARGIN_MISMATCH"]),
 sample("S06","The company made a net loss in the current period.",["Claim refers only to the current period."],[],{"net_income":-15,"reported_net_margin_pct":-10}),
 sample("S07","The new factory caused the revenue rise and therefore the shares must be bought.",["Factory opening and sales growth coincide; no causal analysis, price or valuation."],["UNSUPPORTED_CAUSALITY","UNSUPPORTED_BUY_CLAIM"]),
 sample("S08","Revenue and advertising spending both increased; causation has not been established.",["Both metrics increased over the same period; no causal analysis."],[]),
]
def packets():
    out=[]
    for c in CASES:
        f=facts(c["report"])
        if f["numeric_findings"]!=c["numeric_expected"]:raise ValueError("BENCHMARK_NUMERIC_REGRESSION")
        # Only validated ratios and explicitly scoped evidence; no target labels.
        out.append({"id":c["id"],"verified_facts":{"operating_margin_pct":f["operating_margin_pct"],"net_margin_pct":f["net_margin_pct"],"net_income":str(c["report"]["net_income"])},"claim":c["claim"],"evidence":c["evidence"]})
    return out

def evaluate(result):
    if not isinstance(result,dict) or set(result)!={"reviews"} or not isinstance(result["reviews"],list) or len(result["reviews"])!=len(CASES):raise ValueError("REVIEW_SCHEMA")
    ids={c["id"]:c for c in CASES};seen=set();rows=[]
    for item in result["reviews"]:
        if not isinstance(item,dict) or set(item)!={"id","findings"}:raise ValueError("ITEM_SCHEMA")
        id=item["id"];codes=item["findings"]
        if not isinstance(id,str) or id not in ids or id in seen:raise ValueError("CASE_ID")
        if not isinstance(codes,list) or any(not isinstance(x,str) or x not in LOGIC_CODES for x in codes) or len(set(codes))!=len(codes):raise ValueError("FINDING_SCOPE")
        seen.add(id);expected=set(ids[id]["expected"]);actual=set(codes)
        rows.append({"id":id,"expected":sorted(expected),"actual":sorted(actual),"exact":expected==actual,"tp":len(expected&actual),"fp":len(actual-expected),"fn":len(expected-actual)})
    rows.sort(key=lambda r:r["id"])
    return {"cases":len(rows),"exact":sum(r["exact"] for r in rows),"tp":sum(r["tp"] for r in rows),"fp":sum(r["fp"] for r in rows),"fn":sum(r["fn"] for r in rows),"rows":rows,"numeric_exact":len(CASES),"investment_authorized":False,"real_report_reviewed":False,"benchmark_sha256":digest(CASES)}
