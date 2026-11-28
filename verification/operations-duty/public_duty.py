"""Public-data duty pilot. Fixed SOPs, private SQLite, no orders or model calls."""
import argparse
import hashlib
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo
import duty as core
import handoff

sys.path.insert(0,str(Path(__file__).resolve().parent/"pinned_sources"))
import treasury_view as treasury
import bls_direct as bls

KST=ZoneInfo("Asia/Seoul")
PLAN={"UST_PAR":((7,5),(19,5)), "BLS_V1":((7,10),(19,10))}
GRACE=7200
SCHEMA="""
CREATE TABLE IF NOT EXISTS public_jobs(
  sop TEXT NOT NULL, due INTEGER NOT NULL, state TEXT NOT NULL,
  attempted INTEGER, finished INTEGER, payload TEXT, digest TEXT,
  reason TEXT, PRIMARY KEY(sop,due));
CREATE TABLE IF NOT EXISTS public_reports(
  hour INTEGER PRIMARY KEY, payload TEXT NOT NULL, digest TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS public_meta(k TEXT PRIMARY KEY,v INTEGER NOT NULL);
"""
def init(db):
    db.executescript(SCHEMA)
def scheduled(day,sop):
    return [int(datetime(day.year,day.month,day.day,h,m,tzinfo=KST).timestamp()) for h,m in PLAN[sop]]
def plan(db,now):
    today=datetime.fromtimestamp(now,KST).date()
    row=db.execute("SELECT v FROM public_meta WHERE k='last_tick'").fetchone()
    if row and now<row[0]: raise ValueError("CLOCK_REGRESSION")
    # On first start only the last two hours; after restart enumerate missed
    # windows for <=30 days. Longer gaps flagged in report, not silently replayed.
    lower=row[0] if row else now-GRACE
    cutoff=now-30*86400
    with db:
        # Migration: old spools cannot prove their original activation time.
        db.execute("INSERT OR IGNORE INTO public_meta VALUES('coverage_start',?)",(lower if not row else now,))
        if lower<cutoff:
            db.execute("INSERT OR IGNORE INTO public_meta VALUES('history_gap',?)",(lower,))
            lower=cutoff
        day=datetime.fromtimestamp(lower,KST).date()
        while day<=today:
            for sop in PLAN:
                for due in scheduled(day,sop):
                    if lower<due<=now:
                        state="MISSED" if now-due>=GRACE else "READY"
                        db.execute("INSERT OR IGNORE INTO public_jobs(sop,due,state,reason) VALUES(?,?,?,?)",
                                   (sop,due,state,"WINDOW_EXPIRED" if state=="MISSED" else None))
            day+=timedelta(days=1)
        db.execute("INSERT OR REPLACE INTO public_meta VALUES('last_tick',?)",(now,))
def recover(db,now):
    with db:
        db.execute("UPDATE public_jobs SET state='BLOCKED',finished=?,reason='INTERRUPTED' WHERE state='RUNNING'",(now,))
        db.execute("UPDATE public_jobs SET state='MISSED',finished=?,reason='WINDOW_EXPIRED' WHERE state='READY' AND due<=?",(now,now-GRACE))
def collect(sop,now):
    # Use actual collection clock, not scheduled date, not a historical replay.
    at=datetime.fromtimestamp(now,timezone.utc)
    if sop=="UST_PAR":
        year=at.astimezone(treasury.ET).year
        raw,url=treasury.fetch(year)
        p=treasury.parse(raw,year,at)
        values={k:p[k] for k in ("observation_date","ust_par_2y_pct","ust_par_10y_pct","spread_10y_2y_bp","five_observation_change_10y_bp","age_calendar_days_et")}
        rows=[values]
    elif sop=="BLS_V1":
        raw=bls.fetch(at);url=bls.URL
        rows=[{k:r[k] for k in ("source_series_id","observation_date","value","unit","mom_pct","yoy_pct","monthly_change_people","footnotes")} for r in bls.parse(raw,at)]
        if len(rows)!=4 or any(r["value"] is None or r["observation_date"] is None for r in rows):
            raise ValueError("PARTIAL_BLS")
    else: raise ValueError("UNKNOWN_SOP")
    return {"mode":"OFFICIAL_PUBLIC_REFERENCE","source":url,"observed_at":at.isoformat(),
            "source_sha256":hashlib.sha256(raw).hexdigest(),"rows":rows,
            "latest_session_verified":False,"original_publication_time_verified":False,
            "decision_authorized":False,"trade_authorized":False}
def run_ready(db,now,loader=collect,clock=None):
    for row in db.execute("SELECT * FROM public_jobs WHERE state='READY' ORDER BY due,sop").fetchall():
        at=int(clock()) if clock else now
        if not row["due"]<=at<row["due"]+GRACE:
            with db:
                db.execute("UPDATE public_jobs SET state='MISSED',finished=?,reason='WINDOW_EXPIRED' WHERE sop=? AND due=?",(at,row["sop"],row["due"]))
            continue
        # Commit the attempt before any HTTP request, no automatic retry.
        with db:
            db.execute("UPDATE public_jobs SET state='RUNNING',attempted=? WHERE sop=? AND due=?",(at,row["sop"],row["due"]))
        try:
            value=loader(row["sop"],at)
            if value.get("mode")!="OFFICIAL_PUBLIC_REFERENCE" or value.get("decision_authorized") is not False or value.get("trade_authorized") is not False or not value.get("rows"):
                raise ValueError("CONTRACT")
            body=core.canonical(value);sha=core.digest(value)
            end=int(clock()) if clock else now
            if end<at:raise ValueError("CLOCK_REGRESSION")
            with db:
                db.execute("UPDATE public_jobs SET state='COLLECTED',finished=?,payload=?,digest=? WHERE sop=? AND due=?",(end,body,sha,row["sop"],row["due"]))
        except Exception as e:
            with db:
                db.execute("UPDATE public_jobs SET state='BLOCKED',finished=?,reason=? WHERE sop=? AND due=?",(int(clock()) if clock else now,type(e).__name__,row["sop"],row["due"]))
def report(db,now):
    hour=now//3600*3600
    existing=db.execute("SELECT payload,digest FROM public_reports WHERE hour=?",(hour,)).fetchone()
    if existing:
        p=json.loads(existing[0])
        if core.digest(p)!=existing[1]:raise ValueError("REPORT_CORRUPT")
        return p
    jobs=[]
    for sop in PLAN:
        latest=db.execute("SELECT * FROM public_jobs WHERE sop=? ORDER BY due DESC LIMIT 1",(sop,)).fetchone()
        success=db.execute("SELECT * FROM public_jobs WHERE sop=? AND state='COLLECTED' ORDER BY due DESC LIMIT 1",(sop,)).fetchone()
        item={"sop":sop,"latest_state":latest["state"] if latest else "NOT_RUN",
              "latest_due":latest["due"] if latest else None,"reason":latest["reason"] if latest else None,
              "last_success":None,"reference_only":True}
        if success:
            try:
                p=json.loads(success["payload"])
                if core.digest(p)!=success["digest"]:raise ValueError("CORRUPT")
                item["last_success"]={"due":success["due"],"digest":success["digest"],"observed_at":p["observed_at"],"rows":p["rows"],"source":p["source"],"historical_only":True}
            except Exception:item["latest_state"]="CORRUPT"
        jobs.append(item)
    missed=db.execute("SELECT count(*) FROM public_jobs WHERE state='MISSED' AND due>=?",(now-86400,)).fetchone()[0]
    gap=db.execute("SELECT v FROM public_meta WHERE k='history_gap'").fetchone()
    p={"mode":"PUBLIC_REFERENCE_PILOT","created_at":now,"hour":hour,"jobs":jobs,
       "missed_last_24h":missed,"history_gap":bool(gap),"llm_calls":0,
       "decision_requested":bool(missed or gap or any(x["latest_state"]!="COLLECTED" for x in jobs)),
       "trade_authorized":False}
    handoff.init(db)
    p["handoff"]=handoff.summary(db)
    from ai_control import operational_projection
    p["ai_control"]=operational_projection(db)
    p["decision_requested"]=p["decision_requested"] or p["handoff"]["pending_review_count"]>0
    with db:db.execute("INSERT INTO public_reports VALUES(?,?,?)",(hour,core.canonical(p),core.digest(p)))
    return p
def tick(db,now,loader=collect,clock=None):
    plan(db,now);recover(db,now);run_ready(db,now,loader,clock)
    finished=int(clock()) if clock else now
    handoff.tick(db,finished)
    return report(db,finished)
def main():
    import time
    p=argparse.ArgumentParser();p.add_argument("--db",required=True)
    p.add_argument("action",choices=("tick","probe"))
    a=p.parse_args();os.umask(0o077)
    path=Path(a.db);path.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
    with core.locked(path):
        db=core.open_db(path);init(db)
        try:
            now=int(time.time())
            if a.action=="probe":
                # Explicit disposable CI DB, one live request per source.
                if db.execute("SELECT 1 FROM public_jobs LIMIT 1").fetchone():raise ValueError("PROBE_REQUIRES_EMPTY_DB")
                with db:
                    for sop in PLAN:db.execute("INSERT INTO public_jobs(sop,due,state) VALUES(?,?,'READY')",(sop,now))
                run_ready(db,now,clock=time.time)
                finished=int(time.time())
                handoff.tick(db,finished)
                result=report(db,finished)
            else:result=tick(db,now,clock=time.time)
            # Public reference values only; no raw body, key, account or private state.
            print(core.canonical(result))
            if a.action=="probe" and (any(x["latest_state"]!="COLLECTED" for x in result["jobs"]) or result["handoff"]["stage_states"]!={"COMPLETED":6}):
                return 2
        finally:db.close()
    return 0
if __name__=="__main__":raise SystemExit(main())
