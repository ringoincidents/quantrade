"""Audit-to-HQ exception projection, using the existing bounded GitHub transport.

No network unless explicit exchange flag/identity/token. Never accepts commands.
The outbox is separate from both the audited source and auditor's ledger.
"""
import argparse,json,os,sqlite3,time
from pathlib import Path
import operations_audit as audit
import hq_bridge as hq
import command_contract as local
import duty as core

PREFIX="QT-HQ-AUDIT-V1 "
CODES=set("""SCHEMA_INCOMPLETE SQLITE_INTEGRITY COVERAGE_UNVERIFIED SCHEDULER_STALE HISTORY_GAP
SCHEDULE_MISSING UNSCHEDULED_JOB SOURCE_MISSED SOURCE_BLOCKED READY_EXPIRED RUNNING_STALE
UNKNOWN_JOB_STATE SOURCE_ARTIFACT_INVALID HANDOFF_INCOMPLETE PREMATURE_HANDOFF STAGE_METADATA_INVALID
STAGE_ARTIFACT_INVALID STAGE_BLOCKED BLOCKED_STAGE_HAS_ARTIFACT UNKNOWN_STAGE_STATE SOURCE_STAGE_LINK_INVALID
DEPENDENCY_VIOLATION HANDOFF_LINK_INVALID COMPLETION_WITHOUT_SOURCE ORPHAN_STAGE HOURLY_REPORT_MISSING
HOURLY_REPORT_INVALID PERIOD_REPORT_INVALID REVIEW_PENDING HQ_DELIVERY_UNCERTAIN UNEXPECTED_AI_RESERVATION""".split())
SCHEMA="""
CREATE TABLE IF NOT EXISTS audit_hq_outbox(
 at INTEGER PRIMARY KEY, fingerprint TEXT NOT NULL, body TEXT NOT NULL,
 state TEXT NOT NULL, comment_id INTEGER);
CREATE TABLE IF NOT EXISTS audit_hq_checkpoint(id INTEGER PRIMARY KEY CHECK(id=1),
 at INTEGER NOT NULL,fingerprint TEXT NOT NULL);
"""
def init(db):db.executescript(SCHEMA)
def project(p,now):
    if (p.get("schema")!="QT_OPERATIONS_AUDIT_V1" or p.get("mode")!="PUBLIC_REFERENCE_PILOT"
        or p.get("execution_authorized") is not False or p.get("trade_authorized") is not False
        or p.get("source_independently_verified") is not False or p.get("llm_calls")!=0):
        raise ValueError("AUDIT_CONTRACT")
    at=hq.bounded(p["checked_at"],max(0,now-1800),now)
    findings=p["findings"]
    if not isinstance(findings,dict) or not set(findings)<=CODES:raise ValueError("FINDING_CODES")
    for n in findings.values():hq.bounded(n,1,100000)
    state="EXCEPTION" if findings else "PASS"
    if p["state"]!=state or p["finding_count"]!=sum(findings.values()):raise ValueError("FINDING_COUNT")
    return {"schema":"QT_HQ_AUDIT_STATUS_V1","checked_at":at,"state":state,
            "findings":findings,"execution_authorized":False,"trade_authorized":False,"llm_calls":0}
def prepare(db,p,now):
    status=project(p,now);at=status["checked_at"]
    fp=core.digest({"state":status["state"],"findings":status["findings"]})
    row=db.execute("SELECT at,fingerprint FROM audit_hq_checkpoint WHERE id=1").fetchone()
    if row and at<row[0]:raise ValueError("AUDIT_CLOCK_REGRESSION")
    if row and at==row[0] and fp!=row[1]:raise ValueError("AUDIT_CONFLICT")
    with db:
        if (row is None and status["state"]=="PASS") or (row and fp==row[1]):
            # Initial healthy check or unchanged findings: no external post.
            db.execute("INSERT OR REPLACE INTO audit_hq_checkpoint VALUES(1,?,?)",(at,fp))
        else:
            body=PREFIX+core.canonical({"digest":core.digest(status),"status":status})
            db.execute("INSERT INTO audit_hq_outbox VALUES(?,?,?,'READY',NULL)",(at,fp,body))
            db.execute("INSERT OR REPLACE INTO audit_hq_checkpoint VALUES(1,?,?)",(at,fp))
    return db.execute("SELECT * FROM audit_hq_outbox WHERE state!='SENT' ORDER BY at LIMIT 1").fetchone()
def publish(db,api,expected_actor,now):
    if api.actor()!=expected_actor:raise ValueError("PUBLISHER_IDENTITY")
    row=db.execute("SELECT * FROM audit_hq_outbox WHERE state!='SENT' ORDER BY at LIMIT 1").fetchone()
    if not row:return "NO_CHANGE"
    # Reconcile uncertain delivery even if old. Do not post stale unsent records.
    matches=[c for c in api.comments() if hq.actor_id(c)==expected_actor and c.get("body")==row["body"]]
    if len(matches)>1:raise ValueError("DUPLICATE_REMOTE_AUDIT")
    if matches:
        cid=hq.bounded(matches[0]["id"],1)
    elif row["state"]=="DELIVERY_UNKNOWN":return "DELIVERY_UNKNOWN"
    elif not 0<=now-row["at"]<=1800:return "STALE_PENDING"
    else:
        with db:db.execute("UPDATE audit_hq_outbox SET state='DELIVERY_UNKNOWN' WHERE at=?",(row["at"],))
        c=api.post(row["body"])
        if hq.actor_id(c)!=expected_actor or c.get("body")!=row["body"]:raise ValueError("RECEIPT_MISMATCH")
        cid=hq.bounded(c["id"],1)
    with db:db.execute("UPDATE audit_hq_outbox SET state='SENT',comment_id=? WHERE at=?",(cid,row["at"]))
    return "SENT"
def main():
    p=argparse.ArgumentParser();p.add_argument("--audit-db",required=True);p.add_argument("--outbox-db",required=True)
    p.add_argument("action",choices=("prepare","exchange"));p.add_argument("--token-file");p.add_argument("--publisher-id",type=int)
    args=p.parse_args();os.umask(0o077)
    src=Path(args.audit_db).resolve(strict=True);dst=Path(args.outbox_db).resolve()
    if src==dst or (dst.exists() and os.path.samefile(src,dst)):raise ValueError("SEPARATE_LEDGER_REQUIRED")
    reader=audit.open_readonly(src)
    try:
        r=reader.execute("SELECT body,digest FROM audits ORDER BY at DESC LIMIT 1").fetchone()
        if not r:raise ValueError("NO_AUDIT")
        payload=audit.verified(r[0],r[1])
    finally:reader.close()
    dst.parent.mkdir(mode=0o700,parents=True,exist_ok=True)
    with core.locked(dst):
        db=sqlite3.connect(dst);db.row_factory=sqlite3.Row
        try:
            init(db);now=int(time.time());row=prepare(db,payload,now)
            if args.action=="prepare":
                print(row["body"] if row else '{"state":"NO_CHANGE"}');return
            if os.getenv("QT_HQ_EXCHANGE_ENABLED")!="1" or not args.token_file or not args.publisher_id:
                raise ValueError("EXCHANGE_DISABLED")
            print(core.canonical({"delivery":publish(db,hq.GitHub(local.read_key(args.token_file).decode("ascii")),args.publisher_id,now),
                "execution_authorized":False}))
        finally:db.close()
if __name__=="__main__":main()
