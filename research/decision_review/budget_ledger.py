"""Offline cost-reservation ledger; uses existing review routing, no provider calls."""
import sqlite3
import re
from datetime import datetime, timezone, date
from research.decision_review.decision_review import call_plan, route

SCHEMA = """
CREATE TABLE IF NOT EXISTS gateway_budget(
 day TEXT PRIMARY KEY, max_calls INTEGER NOT NULL, max_micro_usd INTEGER NOT NULL,
 policy_ref TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS gateway_attempt(
 day TEXT NOT NULL REFERENCES gateway_budget(day), request_id TEXT PRIMARY KEY,
 case_id TEXT NOT NULL, provider TEXT NOT NULL, model TEXT NOT NULL, prompt_sha TEXT NOT NULL,
 max_input INTEGER NOT NULL, max_output INTEGER NOT NULL, reserved_micro_usd INTEGER NOT NULL,
 tariff_ref TEXT NOT NULL, author_provider TEXT NOT NULL, grade TEXT NOT NULL,
 state TEXT NOT NULL CHECK(state IN ('RESERVED','REPORTED','UNKNOWN')),
 actual_input INTEGER, actual_output INTEGER, reported_micro_usd INTEGER,
 receipt_sha TEXT
);
"""
PROVIDERS={"OPENAI","ANTHROPIC","GEMINI","XAI"}
def token(x):
    if not isinstance(x,str) or not re.fullmatch(r"[A-Za-z0-9_.:/-]{1,160}",x):
        raise ValueError("INVALID_IDENTIFIER")
    return x
def sha(x):
    if not isinstance(x,str) or not re.fullmatch(r"[0-9a-f]{64}",x):
        raise ValueError("INVALID_DIGEST")
    return x
def natural(x,maximum=10**12):
    if type(x) is not int or not 0<=x<=maximum:
        raise ValueError("INVALID_INTEGER")
    return x
def day_key(day):
    if date.fromisoformat(day).isoformat()!=day:
        raise ValueError("INVALID_DAY")
    return day

def init(db):
    db.execute("PRAGMA foreign_keys=ON")
    db.executescript(SCHEMA)

def configure_day(db,day,*,max_calls,max_micro_usd,policy_ref):
    day_key(day);natural(max_calls,10000);natural(max_micro_usd);token(policy_ref)
    with db:
        db.execute("INSERT INTO gateway_budget VALUES(?,?,?,?)",(day,max_calls,max_micro_usd,policy_ref))
def reserve(db,case,*,case_id,request_id,provider,model,prompt_sha,author_provider,
            scope="UNKNOWN",provider_approved=False,tariff_ref=None,max_input=0,max_output=0,
            input_micro_per_million=0,output_micro_per_million=0):
    # No model access granted. Reserve at configured ceiling; no reuse after failure.
    day=datetime.now(timezone.utc).date().isoformat()
    for x in (case_id,request_id,model,tariff_ref):token(x)
    sha(prompt_sha)
    if provider not in PROVIDERS or author_provider not in (PROVIDERS | {"DETERMINISTIC"}) or provider==author_provider:
        raise ValueError("INDEPENDENCE_NOT_ESTABLISHED")
    for x in (max_input,max_output,input_micro_per_million,output_micro_per_million):natural(x)
    if min(max_input,max_output,input_micro_per_million,output_micro_per_million)==0:
        raise ValueError("UNPRICED_OR_UNBOUNDED")
    cost=(max_input*input_micro_per_million+max_output*output_micro_per_million+999999)//1000000
    natural(cost)
    grade=route(case)["grade"]
    # SQLite writer lock keeps simultaneous reservations from overspending.
    db.execute("BEGIN IMMEDIATE")
    try:
        cfg=db.execute("SELECT max_calls,max_micro_usd FROM gateway_budget WHERE day=?",(day,)).fetchone()
        if cfg is None:
            raise ValueError("BUDGET_NOT_CONFIGURED")
        used,spent=db.execute("SELECT COUNT(*),COALESCE(SUM(reserved_micro_usd),0) FROM gateway_attempt WHERE day=?",(day,)).fetchone()
        required=route(case)["required_independent_reviews"]
        if db.execute("SELECT 1 FROM gateway_attempt WHERE day=? AND state=\'UNKNOWN\' LIMIT 1",(day,)).fetchone():
            raise ValueError("UNRECONCILED_USAGE")
        case_rows=db.execute("SELECT provider,grade,prompt_sha,author_provider FROM gateway_attempt WHERE case_id=?",(case_id,)).fetchall()
        if any((g,h,a)!=(grade,prompt_sha,author_provider) for _,g,h,a in case_rows) or provider in {p for p,_,_,_ in case_rows} or len(case_rows)>=required:
            raise ValueError("REVIEW_DUPLICATE_OR_SCOPE_CHANGED")
        remaining=required-len(case_rows)
        plan=call_plan(case,scope=scope,provider_approved=provider_approved,
                       max_calls_remaining=cfg[0]-used+len(case_rows),
                       budget_reserved=spent+cost<=cfg[1])
        if plan["call_plan_state"]!="CANDIDATE_PLAN_ONLY" or cfg[0]-used<remaining:
            raise ValueError("BLOCKED_"+plan["call_plan_state"])
        db.execute("""INSERT INTO gateway_attempt
            (day,request_id,case_id,provider,model,prompt_sha,max_input,max_output,reserved_micro_usd,tariff_ref,author_provider,grade,state)
            VALUES(?,?,?,?,?,?,?,?,?,?,?,?, 'RESERVED')""",
            (day,request_id,case_id,provider,model,prompt_sha,max_input,max_output,cost,tariff_ref,author_provider,grade))
        db.commit()
        return {"request_id":request_id,"reserved_micro_usd":cost,"state":"RESERVED","external_call_authorized":False}
    except BaseException:
        db.rollback()
        raise

def settle(db,request_id,*,actual_input=None,actual_output=None,reported_micro_usd=None,receipt_sha=None):
    token(request_id)
    db.execute("BEGIN IMMEDIATE")
    try:
        row=db.execute("SELECT state,max_input,max_output,reserved_micro_usd FROM gateway_attempt WHERE request_id=?",(request_id,)).fetchone()
        if row is None or row[0]!="RESERVED":
            raise ValueError("UNKNOWN_OR_FINAL_ATTEMPT")
        if actual_input is None or actual_output is None or reported_micro_usd is None:
            db.execute("UPDATE gateway_attempt SET state='UNKNOWN' WHERE request_id=?",(request_id,))
            state="UNKNOWN"
        else:
            natural(actual_input);natural(actual_output);natural(reported_micro_usd);sha(receipt_sha)
            state="REPORTED" if actual_input<=row[1] and actual_output<=row[2] and reported_micro_usd<=row[3] else "UNKNOWN"
            db.execute("UPDATE gateway_attempt SET state=?,actual_input=?,actual_output=?,reported_micro_usd=?,receipt_sha=? WHERE request_id=?",(state,actual_input,actual_output,reported_micro_usd,receipt_sha,request_id))
        db.commit()
        return state
    except BaseException:
        db.rollback()
        raise
