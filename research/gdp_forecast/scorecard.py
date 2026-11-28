"""Matched-cohort research scorecard; no model promotion."""
import math
from forecast_ledger import read
from observation_validator import instant

def compare(db, evaluation_ids, baseline):
    groups={}
    for eid in evaluation_ids:
        e=read(db,eid,"evaluation")
        f=read(db,e["forecast_id"],"forecast")
        r=read(db,e["realization_id"],"realization")
        model=(f["model"],f["version"])
        key=(f["period"],instant(f["issued_at"]),e["realization_id"],instant(e["asof"]))
        cohort=groups.setdefault(model,{})
        if key in cohort: raise ValueError("Duplicate evaluation")
        if f["period"]!=r["period"]: raise ValueError("Period mismatch")
        cohort[key]=f["value"]-r["value"]
    if baseline not in groups: raise ValueError("Missing baseline")
    keys=set(groups[baseline])
    if not keys or any(set(g)!=keys for g in groups.values()):
        raise ValueError("Unmatched evaluation cohorts")
    result=[]
    base=math.fsum(abs(v) for v in groups[baseline].values())/len(keys)
    for (name,version),g in sorted(groups.items()):
        errors=list(g.values()); n=len(errors)
        mae=math.fsum(map(abs,errors))/n
        result.append(dict(model=name,version=version,n=n,mae=mae,rmse=math.sqrt(math.fsum(v*v for v in errors)/n),bias=math.fsum(errors)/n,skill=None if base==0 else 1-mae/base))
    return {"status":"RESEARCH_ONLY","models":result}
