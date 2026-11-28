"""Durable D0 handoff after public-source collection; no external execution.
Local pilot spool only: does not create canonical Holdings Work or Evidence.
"""
import json
from datetime import date,datetime,timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo
import duty as core

KST=ZoneInfo("Asia/Seoul")
SOPS=("UST_PAR","BLS_V1")
SERIES={"CUSR0000SA0","CUSR0000SA0L1E","CES0000000001","LNS14000000"}
STAGES=("ASSURE","COMPARE","HANDOFF")
SCHEMA="""
CREATE TABLE IF NOT EXISTS duty_handoffs(
 sop TEXT NOT NULL,due INTEGER NOT NULL,stage TEXT NOT NULL,owner TEXT NOT NULL,
 state TEXT NOT NULL,at INTEGER NOT NULL,body TEXT,digest TEXT,reason TEXT,
 PRIMARY KEY(sop,due,stage));
CREATE TABLE IF NOT EXISTS duty_reviews(
 sop TEXT NOT NULL,due INTEGER NOT NULL,reason TEXT NOT NULL,at INTEGER NOT NULL,
 state TEXT NOT NULL,PRIMARY KEY(sop,due,reason));
CREATE TABLE IF NOT EXISTS duty_period_reports(
 kind TEXT NOT NULL,period_end INTEGER NOT NULL,created INTEGER NOT NULL,
 body TEXT NOT NULL,digest TEXT NOT NULL,PRIMARY KEY(kind,period_end));
CREATE TABLE IF NOT EXISTS duty_handoff_meta(k TEXT PRIMARY KEY,v INTEGER NOT NULL);
"""
OWNERS={"ASSURE":"Risk","COMPARE":"Macro Research","HANDOFF":"Operations"}
def init(db):db.executescript(SCHEMA)
def decode(row,key="body"):
    obj=json.loads(row[key])
    if core.digest(obj)!=row["digest"]:raise ValueError("DIGEST_MISMATCH")
    return obj
def numeric(x):
    if isinstance(x,bool):raise ValueError("NUMBER")
    d=Decimal(str(x))
    if not d.is_finite() or abs(d)>Decimal("1e9"):raise ValueError("NUMBER")
    return d
def checked_observation(p,sop):
    if (p.get("mode")!="OFFICIAL_PUBLIC_REFERENCE" or p.get("decision_authorized") is not False
        or p.get("trade_authorized") is not False or p.get("latest_session_verified") is not False
        or p.get("original_publication_time_verified") is not False):
        raise ValueError("AUTHORITY_OR_MODE")
    import re
    if not isinstance(p.get("source_sha256"),str) or not re.fullmatch("[0-9a-f]{64}",p["source_sha256"]):
        raise ValueError("SOURCE_HASH")
    at=datetime.fromisoformat(p["observed_at"])
    if at.tzinfo is None:raise ValueError("OBSERVED_AT")
    et=at.astimezone(ZoneInfo("America/New_York")).date()
    rows=p["rows"];src=p["source"];out={}
    if sop=="UST_PAR":
        prefix="https://home.treasury.gov/resource-center/data-chart-center/interest-rates/pages/xml?data=daily_treasury_yield_curve&field_tdr_date_value="
        if src!=prefix+str(et.year) or len(rows)!=1:raise ValueError("TREASURY_SOURCE")
        r=rows[0];day=date.fromisoformat(r["observation_date"]);a=numeric(r["ust_par_2y_pct"]);b=numeric(r["ust_par_10y_pct"])
        if day>et or day.year!=et.year or not 0<a<100 or not 0<b<100:raise ValueError("TREASURY_RANGE")
        if numeric(r["spread_10y_2y_bp"])!=(b-a)*100:raise ValueError("SPREAD_MISMATCH")
        out={"UST_PAR_2Y":{"date":day.isoformat(),"value":str(a.normalize())},
             "UST_PAR_10Y":{"date":day.isoformat(),"value":str(b.normalize())}}
    elif sop=="BLS_V1":
        if src!="https://api.bls.gov/publicAPI/v1/timeseries/data/" or len(rows)!=4:raise ValueError("BLS_SOURCE")
        for r in rows:
            k=r["source_series_id"];day=date.fromisoformat(r["observation_date"]);val=numeric(r["value"])
            if k not in SERIES or k in out or day>et or day.day!=1:raise ValueError("BLS_SERIES")
            if (k=="LNS14000000" and not 0<=val<=100) or (k!="LNS14000000" and val<=0):raise ValueError("BLS_RANGE")
            out[k]={"date":day.isoformat(),"value":str(val.normalize())}
        if set(out)!=SERIES:raise ValueError("BLS_SERIES")
    else:raise ValueError("SOP")
    return out
def save(db,sop,due,stage,state,now,body=None,reason=None):
    db.execute("INSERT INTO duty_handoffs VALUES(?,?,?,?,?,?,?,?,?)",
               (sop,due,stage,OWNERS[stage],state,now,core.canonical(body) if body is not None else None,core.digest(body) if body is not None else None,reason))
def request(db,sop,due,reason,now):
    db.execute("INSERT OR IGNORE INTO duty_reviews VALUES(?,?,?,?,'PENDING_GOVERNANCE')",(sop,due,reason,now))
def process(db,now):
    # Pure SQLite stages in one transaction per input; crash rolls them back.
    jobs=db.execute("""SELECT j.* FROM public_jobs j WHERE j.state IN ('COLLECTED','BLOCKED','MISSED')
       AND NOT EXISTS(SELECT 1 FROM duty_handoffs h WHERE h.sop=j.sop AND h.due=j.due AND h.stage='HANDOFF')
       ORDER BY j.due,j.sop""").fetchall()
    for j in jobs:
        sop,due=j["sop"],j["due"]
        if sop not in SOPS:raise ValueError("SOP")
        with db:
            try:
                if j["state"]!="COLLECTED":raise ValueError("SOURCE_"+j["state"])
                p=decode(j,"payload");values=checked_observation(p,sop)
                seen=int(datetime.fromisoformat(p["observed_at"]).timestamp())
                if j["attempted"] is None or j["finished"] is None or not j["attempted"]<=seen<=j["finished"]<=now:
                    raise ValueError("TIME_BINDING")
            except (ValueError,KeyError,TypeError,ArithmeticError,OverflowError):
                save(db,sop,due,"ASSURE","BLOCKED",now,reason="INPUT_UNVERIFIED")
                save(db,sop,due,"COMPARE","BLOCKED",now,reason="ASSURE_BLOCKED")
                save(db,sop,due,"HANDOFF","BLOCKED",now,reason="ASSURE_BLOCKED")
                request(db,sop,due,"INPUT_UNVERIFIED",now);continue
            save(db,sop,due,"ASSURE","COMPLETED",now,{"input_digest":j["digest"],"observations":values,"independent_review":False})
            previous=db.execute("""SELECT * FROM duty_handoffs WHERE sop=? AND stage='ASSURE' AND state='COMPLETED' AND due<? ORDER BY due DESC LIMIT 1""",(sop,due)).fetchone()
            try:
                old=decode(previous)["observations"] if previous else {}
                if previous and set(old)!=set(values):raise ValueError("SERIES_SET")
                changes={}
                for k,v in values.items():
                    prior=old.get(k)
                    changes[k]=("BASELINE" if prior is None else "OLDER_OBSERVATION" if v["date"]<prior["date"] else
                        "NEW_OBSERVATION" if v["date"]>prior["date"] else "REVISED" if numeric(v["value"])!=numeric(prior["value"]) else "UNCHANGED")
                body={"changes":changes,"previous_due":previous["due"] if previous else None,"input_digest":j["digest"]}
                save(db,sop,due,"COMPARE","COMPLETED",now,body)
            except (ValueError,KeyError,TypeError,ArithmeticError):
                save(db,sop,due,"COMPARE","BLOCKED",now,reason="PRIOR_UNVERIFIED")
                save(db,sop,due,"HANDOFF","BLOCKED",now,reason="COMPARE_BLOCKED")
                request(db,sop,due,"PRIOR_UNVERIFIED",now);continue
            reasons=sorted(set(changes.values())&{"REVISED","OLDER_OBSERVATION"})
            for reason in reasons:request(db,sop,due,reason,now)
            save(db,sop,due,"HANDOFF","COMPLETED",now,{"comparison_digest":core.digest(body),
                "review_required":bool(reasons),"llm_calls":0,"trade_authorized":False})
def midnight(day):return int(datetime(day.year,day.month,day.day,tzinfo=KST).timestamp())
def boundaries(now):
    day=datetime.fromtimestamp(now,KST).date()
    week=day-timedelta(days=day.weekday());month=day.replace(day=1)
    q=day.replace(month=((day.month-1)//3)*3+1,day=1)
    prevmonth=(month-timedelta(days=1)).replace(day=1)
    prevq=(q-timedelta(days=1));prevq=prevq.replace(month=((prevq.month-1)//3)*3+1,day=1)
    return {"DAILY":(midnight(day-timedelta(days=1)),midnight(day)),
            "WEEKLY":(midnight(week-timedelta(days=7)),midnight(week)),
            "MONTHLY":(midnight(prevmonth),midnight(month)),
            "QUARTERLY":(midnight(prevq),midnight(q))}
def close_periods(db,now):
    # Publish most recent closed period once; explicitly report missing coverage.
    for kind,(start,end) in boundaries(now).items():
        if db.execute("SELECT 1 FROM duty_period_reports WHERE kind=? AND period_end=?",(kind,end)).fetchone():continue
        expected=(end-start)//86400*4 # two fixed sources twice daily KST
        counts={r[0]:r[1] for r in db.execute("SELECT state,count(*) FROM public_jobs WHERE due>=? AND due<? GROUP BY state",(start,end))}
        handed={r[0]:r[1] for r in db.execute("SELECT state,count(*) FROM duty_handoffs WHERE stage='HANDOFF' AND due>=? AND due<? GROUP BY state",(start,end))}
        p={"kind":kind,"period_start":start,"period_end":end,"created_at":now,
            "expected_source_jobs":expected,"source_states":counts,"handoff_states":handed,
            "coverage_complete":sum(counts.values())==expected,
            "all_completed":counts.get("COLLECTED",0)==expected and handed.get("COMPLETED",0)==expected,
            "reference_only":True,"llm_calls":0,"trade_authorized":False}
        with db:db.execute("INSERT INTO duty_period_reports VALUES(?,?,?,?,?)",(kind,end,now,core.canonical(p),core.digest(p)))
def tick(db,now):
    init(db);process(db,now);close_periods(db,now)
def summary(db):
    stages={r[0]:r[1] for r in db.execute("SELECT state,count(*) FROM duty_handoffs GROUP BY state")}
    pending=db.execute("SELECT count(*) FROM duty_reviews WHERE state='PENDING_GOVERNANCE'").fetchone()[0]
    return {"stage_states":stages,"pending_review_count":pending,"reference_only":True,"llm_calls":0}
