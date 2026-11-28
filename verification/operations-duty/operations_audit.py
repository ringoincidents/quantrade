"""Read-only, separately invoked operations assurance for the public duty pilot.

Does not import the execution engine, source adapters or financial handlers.
Checks a bounded snapshot of local records; not independent source verification.
Never repairs, retries, approves, trades, or calls an external model.
"""
import argparse
import hashlib
import json
import os
import sqlite3
import time
from collections import Counter
from datetime import datetime,timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

KST=ZoneInfo("Asia/Seoul")
SCHEDULE={"UST_PAR":((7,5),(19,5)),"BLS_V1":((7,10),(19,10))}
OWNERS={"ASSURE":"Risk","COMPARE":"Macro Research","HANDOFF":"Operations"}
GRACE=7200
HEARTBEAT_LIMIT=900
STAGE_LIMIT=180
LOOKBACK=30*86400
SAMPLE_LIMIT=30
def canon(value):
    return json.dumps(value,sort_keys=True,separators=(",",":"),allow_nan=False)
def digest(value):
    return hashlib.sha256(canon(value).encode()).hexdigest()
def verified(body,sha):
    obj=json.loads(body)
    if not isinstance(obj,dict) or digest(obj)!=sha:raise ValueError("DIGEST")
    return obj
def open_readonly(path):
    p=Path(path).resolve(strict=True)
    db=sqlite3.connect(p.as_uri()+"?mode=ro",uri=True,timeout=5)
    db.row_factory=sqlite3.Row
    db.execute("PRAGMA query_only=ON")
    return db
def expected(start,end):
    day=datetime.fromtimestamp(start,KST).date()
    last=datetime.fromtimestamp(end,KST).date()
    while day<=last:
        for sop,slots in SCHEDULE.items():
            for h,m in slots:
                due=int(datetime(day.year,day.month,day.day,h,m,tzinfo=KST).timestamp())
                if start<due<=end:yield sop,due
        day+=timedelta(days=1)
def audit(db,now):
    counts=Counter(); samples=[]; checked=Counter()
    def finding(code,sop=None,due=None):
        counts[code]+=1
        if len(samples)<SAMPLE_LIMIT:
            # Only fixed codes and validated local identifiers, never raw bodies.
            samples.append({"code":code,"sop":sop if sop in SCHEDULE else None,
                            "due":due if type(due) is int else None})
    def finish():
        return {"schema":"QT_OPERATIONS_AUDIT_V1","mode":"PUBLIC_REFERENCE_PILOT",
                "checked_at":now,"state":"EXCEPTION" if counts else "PASS",
                "finding_count":sum(counts.values()),"findings":dict(sorted(counts.items())),
                "samples":samples,"checked":dict(checked),"scope_days":30,
                "source_independently_verified":False,"execution_authorized":False,
                "llm_calls":0,"trade_authorized":False}
    required={"public_meta","public_jobs","public_reports","duty_handoffs","duty_reviews","duty_period_reports"}
    tables={r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    if not required<=tables:
        finding("SCHEMA_INCOMPLETE");return finish()
    if db.execute("PRAGMA quick_check(1)").fetchone()[0]!="ok":
        finding("SQLITE_INTEGRITY");return finish()
    meta=dict(db.execute("SELECT k,v FROM public_meta"))
    last=meta.get("last_tick");start=meta.get("coverage_start")
    if type(last) is not int or type(start) is not int or not 0<=start<=last<=now:
        finding("COVERAGE_UNVERIFIED");return finish()
    if now-last>HEARTBEAT_LIMIT:finding("SCHEDULER_STALE")
    if "history_gap" in meta:finding("HISTORY_GAP")
    lower=max(start,now-LOOKBACK)
    # Missing slots are checked against wall clock, not merely scheduler claims.
    rows=db.execute("SELECT * FROM public_jobs WHERE due>? AND due<=? ORDER BY due,sop",(lower,now)).fetchall()
    jobs={(r["sop"],r["due"]):r for r in rows}
    slots=set(expected(lower,now))
    for sop,due in sorted(slots,key=lambda x:(x[1],x[0])):
        checked["scheduled_slots"]+=1
        if (sop,due) not in jobs and now-due>HEARTBEAT_LIMIT:
            finding("SCHEDULE_MISSING",sop,due)
    for (sop,due),r in jobs.items():
        checked["source_jobs"]+=1
        if (sop,due) not in slots:finding("UNSCHEDULED_JOB",sop,due)
        state=r["state"]
        if state=="MISSED":finding("SOURCE_MISSED",sop,due)
        elif state=="BLOCKED":finding("SOURCE_BLOCKED",sop,due)
        elif state=="READY" and now-due>=GRACE:finding("READY_EXPIRED",sop,due)
        elif state=="RUNNING" and (r["attempted"] is None or now-r["attempted"]>STAGE_LIMIT):
            finding("RUNNING_STALE",sop,due)
        elif state not in {"READY","RUNNING","COLLECTED"}:finding("UNKNOWN_JOB_STATE",sop,due)
        if state=="COLLECTED":
            try:
                p=verified(r["payload"],r["digest"])
                if (p.get("mode")!="OFFICIAL_PUBLIC_REFERENCE" or p.get("trade_authorized") is not False
                    or p.get("decision_authorized") is not False or not p.get("rows")
                    or p.get("latest_session_verified") is not False
                    or p.get("original_publication_time_verified") is not False):
                    raise ValueError("CONTRACT")
                seen=int(datetime.fromisoformat(p["observed_at"]).timestamp())
                if not due<=r["attempted"]<=seen<=r["finished"]<=now:raise ValueError("TIME")
            except (ValueError,TypeError,KeyError,OverflowError):
                finding("SOURCE_ARTIFACT_INVALID",sop,due)
        stages={h["stage"]:h for h in db.execute("SELECT * FROM duty_handoffs WHERE sop=? AND due=?",(sop,due))}
        terminal=state in {"COLLECTED","MISSED","BLOCKED"}
        age=now-(r["finished"] if r["finished"] is not None else due)
        if terminal and age>STAGE_LIMIT and set(stages)!=set(OWNERS):
            finding("HANDOFF_INCOMPLETE",sop,due)
        if not terminal and stages:finding("PREMATURE_HANDOFF",sop,due)
        decoded={}
        for stage,h in stages.items():
            checked["handoff_stages"]+=1
            if stage not in OWNERS or h["owner"]!=OWNERS.get(stage) or not due<=h["at"]<=now:
                finding("STAGE_METADATA_INVALID",sop,due)
            if h["state"]=="COMPLETED":
                try:decoded[stage]=verified(h["body"],h["digest"])
                except (ValueError,TypeError,KeyError):finding("STAGE_ARTIFACT_INVALID",sop,due)
            elif h["state"]=="BLOCKED":
                finding("STAGE_BLOCKED",sop,due)
                if h["body"] is not None or h["digest"] is not None:finding("BLOCKED_STAGE_HAS_ARTIFACT",sop,due)
            else:finding("UNKNOWN_STAGE_STATE",sop,due)
        for stage in ("ASSURE","COMPARE"):
            if stage in decoded and decoded[stage].get("input_digest")!=r["digest"]:
                finding("SOURCE_STAGE_LINK_INVALID",sop,due)
        if "COMPARE" in decoded and "ASSURE" not in decoded:finding("DEPENDENCY_VIOLATION",sop,due)
        if "HANDOFF" in decoded:
            p=decoded["HANDOFF"]
            if ("COMPARE" not in decoded or p.get("comparison_digest")!=stages["COMPARE"]["digest"]
                or p.get("trade_authorized") is not False or p.get("llm_calls")!=0
                or state!="COLLECTED"):finding("HANDOFF_LINK_INVALID",sop,due)
        if state!="COLLECTED" and decoded:finding("COMPLETION_WITHOUT_SOURCE",sop,due)
    orphan=db.execute("""SELECT count(*) FROM duty_handoffs h LEFT JOIN public_jobs j
        ON h.sop=j.sop AND h.due=j.due WHERE j.sop IS NULL AND h.due>?""",(lower,)).fetchone()[0]
    for _ in range(min(orphan,1000)):finding("ORPHAN_STAGE")
    # Check hourly report presence only after the hour has had time to execute.
    first=(lower//3600+1)*3600
    hours={r["hour"]:r for r in db.execute("SELECT * FROM public_reports WHERE hour>=? ORDER BY hour",(first,))}
    for hour in range(first,now//3600*3600+1,3600):
        if now-hour>HEARTBEAT_LIMIT and hour not in hours:finding("HOURLY_REPORT_MISSING",due=hour)
    for hour,r in hours.items():
        checked["hourly_reports"]+=1
        try:
            p=verified(r["payload"],r["digest"])
            if p.get("hour")!=hour or not hour<=p["created_at"]<hour+3600 or p["created_at"]>now or p.get("trade_authorized") is not False or p.get("llm_calls")!=0:
                raise ValueError("REPORT_CONTRACT")
        except (ValueError,KeyError,TypeError):finding("HOURLY_REPORT_INVALID",due=hour)
    for r in db.execute("SELECT * FROM duty_period_reports WHERE period_end>=?",(lower,)):
        checked["period_reports"]+=1
        try:
            p=verified(r["body"],r["digest"])
            if p["kind"]!=r["kind"] or p["period_end"]!=r["period_end"] or p["created_at"]!=r["created"] or p["trade_authorized"] is not False or p["llm_calls"]!=0:
                raise ValueError("PERIOD_CONTRACT")
            if p["expected_source_jobs"]!=(p["period_end"]-p["period_start"])//86400*4:raise ValueError("EXPECTED")
            if p["all_completed"] and (not p["coverage_complete"] or p["source_states"].get("COLLECTED",0)!=p["expected_source_jobs"] or p["handoff_states"].get("COMPLETED",0)!=p["expected_source_jobs"]):
                raise ValueError("FALSE_COMPLETION")
        except (ValueError,KeyError,TypeError):finding("PERIOD_REPORT_INVALID",due=r["period_end"])
    pending=db.execute("SELECT count(*) FROM duty_reviews WHERE state='PENDING_GOVERNANCE'").fetchone()[0]
    checked["pending_reviews"]=pending
    if pending:finding("REVIEW_PENDING")
    if "hq_outbox" in tables:
        n=db.execute("SELECT count(*) FROM hq_outbox WHERE state='DELIVERY_UNKNOWN'").fetchone()[0]
        if n:finding("HQ_DELIVERY_UNCERTAIN")
    if "gateway_attempt" in tables and db.execute("SELECT count(*) FROM gateway_attempt").fetchone()[0]:
        finding("UNEXPECTED_AI_RESERVATION")
    return finish()
def save(path,result):
    # A separate audit ledger, not the source database. Preserve each minute.
    db=sqlite3.connect(path,timeout=5)
    try:
        db.execute("CREATE TABLE IF NOT EXISTS audits(at INTEGER PRIMARY KEY,body TEXT NOT NULL,digest TEXT NOT NULL)")
        with db:db.execute("INSERT OR IGNORE INTO audits VALUES(?,?,?)",(result["checked_at"],canon(result),digest(result)))
    finally:db.close()
def main():
    p=argparse.ArgumentParser();p.add_argument("--source-db",required=True);p.add_argument("--audit-db",required=True)
    a=p.parse_args();os.umask(0o077)
    src=Path(a.source_db).resolve();dst=Path(a.audit_db).resolve()
    if src==dst or (src.exists() and dst.exists() and os.path.samefile(src,dst)):raise ValueError("SEPARATE_LEDGER_REQUIRED")
    db=open_readonly(src)
    try:
        db.execute("BEGIN")
        result=audit(db,int(time.time()))
    finally:db.close()
    dst.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
    save(dst,result)
    print(canon(result))
    return 2 if result["state"]!="PASS" else 0
if __name__=="__main__":raise SystemExit(main())
