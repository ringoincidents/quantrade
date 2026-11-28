"""Isolated D0 operations pilot. Synthetic inputs only; no broker, LLM or network.
Local execution ledger is a pilot spool, NOT a second Holdings authority.
Single Linux process lock; interrupted work fails closed for explicit review.
"""
import argparse
import contextlib
import hashlib
import json
import os
import sqlite3
import time
from pathlib import Path

PERIOD=300
REPORT_PERIOD=3600
MAX_CATCHUP=12
# Stable identifiers and approved *pilot* SOPs. No arbitrary commands or code.
PLAN={
    "collect": {"owner":"Data", "after":None, "period":PERIOD},
    "compare": {"owner":"Research", "after":"collect", "period":PERIOD},
    "assure": {"owner":"Risk", "after":"compare", "period":PERIOD},
}
SCHEMA="""
CREATE TABLE IF NOT EXISTS jobs(
  slot INTEGER NOT NULL, sop TEXT NOT NULL, state TEXT NOT NULL,
  result TEXT, digest TEXT, updated INTEGER NOT NULL,
  PRIMARY KEY(slot,sop));
CREATE TABLE IF NOT EXISTS events(
  id INTEGER PRIMARY KEY, at INTEGER NOT NULL, slot INTEGER,
  sop TEXT, kind TEXT NOT NULL, detail TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS reports(
  slot INTEGER PRIMARY KEY, body TEXT NOT NULL, digest TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS metadata(k TEXT PRIMARY KEY,v TEXT NOT NULL);
"""
def canonical(value):
    return json.dumps(value,sort_keys=True,separators=(",",":"),allow_nan=False)
def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()
def event(db, now, slot, sop, kind, detail):
    db.execute("INSERT INTO events(at,slot,sop,kind,detail) VALUES(?,?,?,?,?)",
               (now,slot,sop,kind,detail))
def open_db(path):
    # Caller must own directory and hold the process lock in production.
    db=sqlite3.connect(path, timeout=5)
    db.row_factory=sqlite3.Row
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("PRAGMA synchronous=FULL")
    db.executescript(SCHEMA)
    with db:
        db.execute("INSERT OR IGNORE INTO metadata VALUES('schema','1')")
        if db.execute("SELECT v FROM metadata WHERE k='schema'").fetchone()[0]!="1":
            raise RuntimeError("UNSUPPORTED_SCHEMA")
    return db
def plan_due(db, now):
    slot=now//PERIOD*PERIOD
    with db:
        row=db.execute("SELECT v FROM metadata WHERE k='last_slot'").fetchone()
        if row and slot<int(row[0]):
            event(db,now,slot,None,"CLOCK_REGRESSION","No new scheduled work")
            return
        start=int(row[0])+PERIOD if row else slot
        earliest=slot-(MAX_CATCHUP-1)*PERIOD
        if start<earliest:
            event(db,now,slot,None,"MISSED_WINDOW",str((earliest-start)//PERIOD))
            start=earliest
        for at in range(start,slot+1,PERIOD):
            for sop in PLAN:
                db.execute("INSERT OR IGNORE INTO jobs VALUES(?,?,'PLANNED',NULL,NULL,?)",(at,sop,now))
        db.execute("INSERT OR REPLACE INTO metadata VALUES('last_slot',?)",(str(slot),))
def recover(db, now):
    with db:
        rows=db.execute("SELECT slot,sop FROM jobs WHERE state='RUNNING'").fetchall()
        for r in rows:
            db.execute("UPDATE jobs SET state='BLOCKED',updated=? WHERE slot=? AND sop=?",(now,r["slot"],r["sop"]))
            event(db,now,r["slot"],r["sop"],"INTERRUPTED","No blind replay")
def read_result(row):
    if row is None or row["state"]!="COMPLETED":
        raise ValueError("DEPENDENCY_NOT_READY")
    data=json.loads(row["result"])
    if digest(data)!=row["digest"]:
        raise ValueError("RESULT_DIGEST_MISMATCH")
    return data
def handler(sop, slot, prior, db):
    if sop=="collect":
        return {"mode":"SYNTHETIC","slot":slot,"price_cents":8000,"target_cents":10000,
                "source":"fixed offline fixture","trade_authority":False}
    if sop=="compare":
        if prior.get("mode")!="SYNTHETIC" or prior.get("slot")!=slot:
            raise ValueError("INVALID_FIXTURE")
        p,t=prior["price_cents"],prior["target_cents"]
        if type(p) is not int or type(t) is not int or min(p,t)<=0:
            raise ValueError("INVALID_PRICE")
        return {"mode":"SYNTHETIC","slot":slot,"status":"REVIEW" if p<=t else "WAIT",
                "gap_cents":t-p,"trade_authority":False}
    if sop=="assure":
        raw=read_result(db.execute("SELECT * FROM jobs WHERE slot=? AND sop='collect'",(slot,)).fetchone())
        expected="WAIT" if raw["price_cents"]>raw["target_cents"] else "REVIEW"
        if (prior.get("mode")!="SYNTHETIC" or prior.get("slot")!=slot or
            prior.get("status")!=expected or prior.get("gap_cents")+raw["price_cents"]!=raw["target_cents"] or
            prior.get("trade_authority") is not False):
            raise ValueError("DETERMINISTIC_CHECK_FAILED")
        return {"mode":"SYNTHETIC","slot":slot,"check":"PASS","status":expected,
                "independent_review":False,"trade_authority":False}
    raise ValueError("UNKNOWN_SOP")
def run_ready(db, now):
    slots=db.execute("SELECT DISTINCT slot FROM jobs WHERE state='PLANNED' ORDER BY slot").fetchall()
    for row in slots:
        slot=row[0]
        for sop, spec in PLAN.items():
            job=db.execute("SELECT * FROM jobs WHERE slot=? AND sop=?",(slot,sop)).fetchone()
            if job is None or job["state"]!="PLANNED": continue
            dep=spec["after"]
            prior=None
            if dep:
                dependency=db.execute("SELECT * FROM jobs WHERE slot=? AND sop=?",(slot,dep)).fetchone()
                if dependency is None or dependency["state"]!="COMPLETED":
                    if dependency is None or dependency["state"]=="BLOCKED":
                        with db:
                            db.execute("UPDATE jobs SET state='BLOCKED',updated=? WHERE slot=? AND sop=?",(now,slot,sop))
                            event(db,now,slot,sop,"DEPENDENCY_BLOCKED","No partial execution")
                    continue
            with db:
                db.execute("UPDATE jobs SET state='RUNNING',updated=? WHERE slot=? AND sop=?",(now,slot,sop))
                event(db,now,slot,sop,"STARTED",spec["owner"])
            try:
                if dep: prior=read_result(dependency)
                result=handler(sop,slot,prior,db)
                with db:
                    db.execute("UPDATE jobs SET state='COMPLETED',result=?,digest=?,updated=? WHERE slot=? AND sop=?",
                               (canonical(result),digest(result),now,slot,sop))
                    event(db,now,slot,sop,"COMPLETED","D0 pilot")
            except Exception as exc:
                with db:
                    db.execute("UPDATE jobs SET state='BLOCKED',updated=? WHERE slot=? AND sop=?",(now,slot,sop))
                    event(db,now,slot,sop,"BLOCKED",type(exc).__name__)
def report(db, now):
    slot=now//REPORT_PERIOD*REPORT_PERIOD
    # Immutable hourly report; partial first hour explicitly identified.
    start=slot-REPORT_PERIOD
    states={r[0]:r[1] for r in db.execute("SELECT state,COUNT(*) FROM jobs WHERE slot>=? AND slot<? GROUP BY state",(start,slot))}
    issues=[dict(r) for r in db.execute("SELECT slot,sop,state FROM jobs WHERE state='BLOCKED' ORDER BY slot DESC LIMIT 20")]
    anomalies=[dict(r) for r in db.execute("SELECT at,kind,detail FROM events WHERE at>=? AND kind IN ('CLOCK_REGRESSION','MISSED_WINDOW','INTERRUPTED') ORDER BY id DESC LIMIT 20",(start,))]
    bad=[]
    for row in db.execute("SELECT * FROM jobs WHERE state='COMPLETED' AND slot>=? AND slot<?",(start,slot)):
        try: read_result(row)
        except Exception: bad.append([row["slot"],row["sop"]])
    body={"mode":"SYNTHETIC_PILOT","window_start":start,"window_end":slot,"created_at":now,
          "expected_jobs":36,"states":states,"coverage_complete":sum(states.values())==36,
          "blocked_sample":issues,"anomalies":anomalies,"digest_failures":bad,
          "llm_calls":0,"llm_enabled":False,"trade_authority":False,
          "decision_requested":bool(issues or anomalies or bad or sum(states.values())!=36)}
    with db:
        db.execute("INSERT OR IGNORE INTO reports VALUES(?,?,?)",(slot,canonical(body),digest(body)))
    return body
def tick(db, now):
    plan_due(db,now)
    run_ready(db,now)
    return report(db,now)
def latest_report(db):
    r=db.execute("SELECT * FROM reports ORDER BY slot DESC LIMIT 1").fetchone()
    if r is None: return {"state":"NO_REPORT"}
    body=json.loads(r["body"])
    if digest(body)!=r["digest"]: raise ValueError("REPORT_DIGEST_MISMATCH")
    return body
@contextlib.contextmanager
def locked(path):
    import fcntl
    fd=os.open(str(path)+".lock",os.O_CREAT|os.O_RDWR,0o600)
    try:
        fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
        yield
    finally: os.close(fd)
def main():
    p=argparse.ArgumentParser()
    p.add_argument("--db",required=True)
    p.add_argument("action",choices=("tick","serve","report"))
    args=p.parse_args()
    os.umask(0o077)
    path=Path(args.db)
    path.parent.mkdir(mode=0o700,parents=True,exist_ok=True)
    with locked(path):
        db=open_db(path)
        try:
            if args.action=="report": print(canonical(latest_report(db))); return
            recover(db,int(time.time()))
            while True:
                tick(db,int(time.time()))
                if args.action=="tick": break
                time.sleep(max(1,60-int(time.time())%60))
        finally: db.close()
if __name__=="__main__": main()
