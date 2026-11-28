"""Offline retrospective research replay, never a live forecast."""
import hashlib
import json
from observation_validator import validate, instant
from experiment import evaluate, score
import forecast_ledger as ledger
from scorecard import compare

def replay(db, rows, asof):
    cutoff=instant(asof)
    data=validate(rows)
    if any(instant(r["actual_public_at"])>cutoff for r in rows):
        raise ValueError("Replay contains future realization")
    predictions=evaluate(**data)
    manifest=hashlib.sha256(json.dumps(rows,sort_keys=True,allow_nan=False).encode()).hexdigest()
    ids=[]
    with db:
        for p in predictions:
            r=rows[p["index"]]
            rid=ledger.realization(db,r["period"],r["actual_public_at"],r["vintage"],r["actual"])
            for model,value in p["predictions"].items():
                fid=ledger.forecast(db,r["period"],r["issued_at"],"REPLAY:"+model,"research-v1",value,manifest)
                ids.append(ledger.evaluate(db,fid,rid,asof))
        matched=compare(db,ids,("REPLAY:Persistence","research-v1"))
    return {"scorecard":matched,"status":"RETROSPECTIVE_UNVERIFIED","manifest":manifest,"n":len(predictions),"scores":score(predictions),"evaluation_ids":ids}
