"""AI admission projection / synthetic budget verification. No provider transport.

Existing #147 router and reservation tables remain the single pilot ledger.
This layer adds a transactional month gate and operational exception triage.
No production policy or actual spend authority is created here.
"""
import sqlite3
import sys
from datetime import datetime,timezone
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from pinned_review import decision_review as review
from pinned_review import budget_ledger as ledger

SCHEMA="""
CREATE TABLE IF NOT EXISTS ai_pilot_month(
 month TEXT PRIMARY KEY, max_calls INTEGER NOT NULL CHECK(max_calls>=0),
 max_micro_usd INTEGER NOT NULL CHECK(max_micro_usd>=0),
 policy_ref TEXT NOT NULL, mode TEXT NOT NULL CHECK(mode='SYNTHETIC_TEST_ONLY'));
CREATE TABLE IF NOT EXISTS ai_pilot_switch(
 id INTEGER PRIMARY KEY CHECK(id=1), enabled INTEGER NOT NULL CHECK(enabled IN (0,1)));
INSERT OR IGNORE INTO ai_pilot_switch VALUES(1,0);
CREATE TRIGGER IF NOT EXISTS ai_pilot_month_admission
 BEFORE INSERT ON gateway_attempt BEGIN
 SELECT CASE WHEN COALESCE((SELECT enabled FROM ai_pilot_switch WHERE id=1),0)!=1
  THEN RAISE(ABORT,'PILOT_DISABLED') END;
 SELECT CASE WHEN NOT EXISTS(SELECT 1 FROM ai_pilot_month WHERE month=substr(NEW.day,1,7))
  THEN RAISE(ABORT,'MONTH_NOT_CONFIGURED') END;
 SELECT CASE WHEN EXISTS(SELECT 1 FROM gateway_attempt WHERE state='UNKNOWN'
   OR (state='RESERVED' AND day<NEW.day))
  THEN RAISE(ABORT,'UNRECONCILED_PRIOR_USAGE') END;
 SELECT CASE WHEN (SELECT count(*) FROM gateway_attempt WHERE substr(day,1,7)=substr(NEW.day,1,7))+1>
   (SELECT max_calls FROM ai_pilot_month WHERE month=substr(NEW.day,1,7))
  THEN RAISE(ABORT,'MONTH_CALL_LIMIT') END;
 SELECT CASE WHEN (SELECT COALESCE(sum(reserved_micro_usd),0) FROM gateway_attempt
   WHERE substr(day,1,7)=substr(NEW.day,1,7))+NEW.reserved_micro_usd>
   (SELECT max_micro_usd FROM ai_pilot_month WHERE month=substr(NEW.day,1,7))
  THEN RAISE(ABORT,'MONTH_COST_LIMIT') END;
END;
"""
def init(db):
    ledger.init(db);db.executescript(SCHEMA)
def triage(reason):
    # Source exceptions cannot be fixed by a model. Route to deterministic
    # validation or human governance first. Unknown reason fails closed.
    states={"INPUT_UNVERIFIED":"D0_REPAIR_REQUIRED","PRIOR_UNVERIFIED":"D0_REPAIR_REQUIRED",
            "REVISED":"D0_COMPARE_THEN_REVIEW","OLDER_OBSERVATION":"D0_REPAIR_REQUIRED"}
    return states.get(reason,"BLOCKED_UNCLASSIFIED")
def operational_projection(db):
    counts={}
    for row in db.execute("SELECT reason,count(*) FROM duty_reviews WHERE state='PENDING_GOVERNANCE' GROUP BY reason"):
        k=triage(row[0]);counts[k]=counts.get(k,0)+row[1]
    return {"pending_routes":counts,"mode":"NO_PROVIDER_TRANSPORT",
            "actual_call_authorized":False,"llm_calls":0}
def plan(case,*,scope="UNKNOWN",provider_approved=False,max_calls_remaining=0,budget_reserved=False):
    p=review.call_plan(case,scope=scope,provider_approved=provider_approved,
        max_calls_remaining=max_calls_remaining,budget_reserved=budget_reserved)
    return {**p,"actual_call_authorized":False,"provider_transport":"ABSENT"}
def configure_synthetic(db,day,*,daily_calls,daily_micro_usd,monthly_calls,monthly_micro_usd):
    # Only disposable in-memory verification databases are eligible.
    # File-backed production/pilot spools cannot enable this path.
    if any(r[2] for r in db.execute("PRAGMA database_list")):raise ValueError("TEST_DB_ONLY")
    ledger.day_key(day)
    for v in (daily_calls,daily_micro_usd,monthly_calls,monthly_micro_usd):ledger.natural(v)
    if daily_calls>monthly_calls or daily_micro_usd>monthly_micro_usd:raise ValueError("DAILY_EXCEEDS_MONTH")
    init(db)
    with db:
        db.execute("INSERT INTO ai_pilot_month VALUES(?,?,?,'synthetic.fixture','SYNTHETIC_TEST_ONLY')",
                   (day[:7],monthly_calls,monthly_micro_usd))
    ledger.configure_day(db,day,max_calls=daily_calls,max_micro_usd=daily_micro_usd,policy_ref="synthetic.fixture")
    with db:db.execute("UPDATE ai_pilot_switch SET enabled=1 WHERE id=1")
def reserve_synthetic(db,case,**kwargs):
    if any(r[2] for r in db.execute("PRAGMA database_list")):raise ValueError("TEST_DB_ONLY")
    if kwargs.get("scope")!="SYNTHETIC_APPROVED":raise ValueError("SYNTHETIC_SCOPE_ONLY")
    # Never invoke a provider. Existing ledger checks case, route, tariff,
    # provider separation, daily call/cost caps and records attempt.
    # Month trigger runs inside that same INSERT transaction.
    return ledger.reserve(db,case,**kwargs)
def settle_synthetic(db,request_id,**receipt):
    if any(r[2] for r in db.execute("PRAGMA database_list")):raise ValueError("TEST_DB_ONLY")
    return ledger.settle(db,request_id,**receipt)
def usage(db):
    day=datetime.now(timezone.utc).date().isoformat()
    rows=db.execute("SELECT state,count(*),COALESCE(sum(reserved_micro_usd),0) FROM gateway_attempt WHERE substr(day,1,7)=? GROUP BY state",(day[:7],))
    return {"month_utc":day[:7],"states":{r[0]:{"calls":r[1],"reserved_micro_usd":r[2]} for r in rows},
            "provider_billed_verified":False,"actual_call_authorized":False}
