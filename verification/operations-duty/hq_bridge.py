"""Public-safe HQ bridge pilot, NOT a production command authority.

Only typed status metadata leaves the local public-reference spool. No data values,
private holdings, raw errors, arbitrary instructions or keys. GitHub identity
proves account, not human/ChatGPT identity. Commands are review proposals only.
"""
import argparse
import json
import os
import re
import time
from datetime import datetime,timezone
from pathlib import Path
from urllib.request import Request,build_opener,ProxyHandler,HTTPRedirectHandler
import duty as core
import public_duty as public
import command_contract as local

ROOT="https://api.github.com"
PATH="/repos/ringoincidents/quantrade/issues/150/comments"
REPORT_PREFIX="QT-HQ-REPORT-V1 "
COMMAND_PREFIX="QT-HQ-PROPOSAL-V1 "
STATES={"NOT_RUN","READY","RUNNING","COLLECTED","BLOCKED","MISSED","CORRUPT"}
SCHEMA="""
CREATE TABLE IF NOT EXISTS hq_outbox(
 digest TEXT PRIMARY KEY, hour INTEGER UNIQUE NOT NULL, body TEXT NOT NULL,
 state TEXT NOT NULL, comment_id INTEGER, attempted INTEGER);
CREATE TABLE IF NOT EXISTS hq_proposals(
 comment_id INTEGER PRIMARY KEY, actor_id INTEGER NOT NULL, report_digest TEXT NOT NULL,
 sop TEXT NOT NULL, created INTEGER NOT NULL, state TEXT NOT NULL);
"""
def init(db):db.executescript(SCHEMA)
def bounded(n,minimum=0,maximum=2**53-1):
    if type(n) is not int or not minimum<=n<=maximum:raise ValueError("INTEGER")
    return n
def strict_bool(v):
    if type(v) is not bool:raise ValueError("BOOLEAN")
    return v
def project(p):
    if p.get("mode")!="PUBLIC_REFERENCE_PILOT" or p.get("trade_authorized") is not False or p.get("llm_calls")!=0:
        raise ValueError("WRONG_MODE")
    hour=bounded(p["hour"]);created=bounded(p["created_at"],hour,hour+3599)
    if hour%3600:raise ValueError("HOUR_ALIGNMENT")
    jobs=p["jobs"]
    if not isinstance(jobs,list) or len(jobs)!=len(public.PLAN):raise ValueError("SOP_SET")
    out=[];seen=set()
    for j in jobs:
        sop=j["sop"];state=j["latest_state"]
        if sop not in public.PLAN or sop in seen or state not in STATES or j.get("reference_only") is not True:
            raise ValueError("JOB")
        seen.add(sop);due=j["latest_due"]
        if due is not None:bounded(due,0,created)
        last=j["last_success"]
        last_due=None
        if last is not None:
            if last.get("historical_only") is not True:raise ValueError("NOT_REFERENCE")
            last_due=bounded(last["due"],0,created)
        out.append({"sop":sop,"state":state,"due":due,"last_success_due":last_due})
    return {"schema":"QT_HQ_STATUS_V1","mode":"PUBLIC_REFERENCE_PILOT",
            "hour":hour,"created_at":created,"jobs":sorted(out,key=lambda x:x["sop"]),
            "missed_last_24h":bounded(p["missed_last_24h"],0,100000),
            "history_gap":strict_bool(p["history_gap"]),"decision_requested":strict_bool(p["decision_requested"]),
            "llm_calls":0,"trade_authorized":False}
def prepare(db):
    row=db.execute("SELECT payload,digest FROM public_reports ORDER BY hour DESC LIMIT 1").fetchone()
    if not row:raise ValueError("NO_REPORT")
    p=json.loads(row[0])
    if core.digest(p)!=row[1]:raise ValueError("SOURCE_REPORT_CORRUPT")
    view=project(p);sha=core.digest(view)
    body=REPORT_PREFIX+core.canonical({"digest":sha,"status":view})
    with db:db.execute("INSERT OR IGNORE INTO hq_outbox VALUES(?,?,?,'READY',NULL,NULL)",(sha,view["hour"],body))
    stored=db.execute("SELECT * FROM hq_outbox WHERE hour=?",(view["hour"],)).fetchone()
    if stored["digest"]!=sha or stored["body"]!=body:raise ValueError("OUTBOX_CONFLICT")
    return stored
class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self,*a,**kw):return None
class GitHub:
    def __init__(self,token):
        if not re.fullmatch(r"[A-Za-z0-9_]{20,255}",token):raise ValueError("TOKEN_FORMAT")
        self.token=token;self.opener=build_opener(ProxyHandler({}),NoRedirect())
    def request(self,path,body=None):
        if path!="/user" and path!=PATH and not re.fullmatch(re.escape(PATH)+r"\?per_page=100&page=[1-9][0-9]?",path):
            raise ValueError("PATH")
        url=ROOT+path
        payload=None if body is None else core.canonical(body).encode()
        req=Request(url,data=payload,headers={"Authorization":"Bearer "+self.token,
             "Accept":"application/vnd.github+json","Content-Type":"application/json",
             "X-GitHub-Api-Version":"2022-11-28","User-Agent":"QuanTrade-HQ-Pilot/1"},
             method="GET" if body is None else "POST")
        with self.opener.open(req,timeout=8) as res:
            if res.geturl()!=url or res.status not in (200,201):raise ValueError("HTTP_RESPONSE")
            raw=res.read(4_000_001)
        if len(raw)>4_000_000:raise ValueError("HTTP_SIZE")
        return json.loads(raw)
    def actor(self):return bounded(self.request("/user")["id"],1)
    def comments(self):
        result=[]
        for page in range(1,6):
            rows=self.request(PATH+"?per_page=100&page="+str(page))
            if not isinstance(rows,list) or len(rows)>100:raise ValueError("COMMENTS_SHAPE")
            result.extend(rows)
            if len(rows)<100:return result
        # Do not treat incomplete pagination as proof of absence.
        raise ValueError("COMMENTS_PAGE_LIMIT")
    def post(self,body):return self.request(PATH,{"body":body})
def actor_id(comment):
    user=comment.get("user")
    if not isinstance(user,dict):return None
    return user.get("id") if type(user.get("id")) is int else None
def publish(db,api,now,expected_actor):
    row=prepare(db)
    if now<row["hour"] or now-row["hour"]>=7200:raise ValueError("STALE_REPORT")
    if api.actor()!=expected_actor:raise ValueError("PUBLISHER_IDENTITY")
    if row["state"]=="SENT":return "SENT"
    matches=[c for c in api.comments() if actor_id(c)==expected_actor and c.get("body")==row["body"]]
    if len(matches)>1:raise ValueError("DUPLICATE_REMOTE_REPORT")
    if matches:
        cid=bounded(matches[0]["id"],1)
        with db:db.execute("UPDATE hq_outbox SET state='SENT',comment_id=? WHERE digest=?",(cid,row["digest"]))
        return "SENT"
    if row["state"]!="READY":
        # Unknown outcome never blindly re-posts: inspect authoritative remote state.
        return "DELIVERY_UNKNOWN"
    with db:db.execute("UPDATE hq_outbox SET state='DELIVERY_UNKNOWN',attempted=? WHERE digest=?",(now,row["digest"]))
    c=api.post(row["body"])
    if actor_id(c)!=expected_actor or c.get("body")!=row["body"]:raise ValueError("RECEIPT_MISMATCH")
    cid=bounded(c["id"],1)
    with db:db.execute("UPDATE hq_outbox SET state='SENT',comment_id=? WHERE digest=?",(cid,row["digest"]))
    return "SENT"
def epoch(s):
    if not isinstance(s,str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z",s):raise ValueError("TIME")
    return int(datetime.fromisoformat(s.replace("Z","+00:00")).timestamp())
def ingest(db,comments,now,authorized_actor):
    counts={"accepted":0,"rejected":0,"duplicate":0}
    for c in comments:
        body=c.get("body")
        if not isinstance(body,str) or not body.startswith(COMMAND_PREFIX):continue
        try:
            if len(body)>1024 or actor_id(c)!=authorized_actor:raise ValueError("ACTOR")
            cid=bounded(c["id"],1)
            if db.execute("SELECT 1 FROM hq_proposals WHERE comment_id=?",(cid,)).fetchone():
                counts["duplicate"]+=1;continue
            created=epoch(c["created_at"])
            if c["created_at"]!=c["updated_at"] or not created<=now<created+3600:raise ValueError("EDITED_OR_EXPIRED")
            p=json.loads(body[len(COMMAND_PREFIX):])
            if body!=COMMAND_PREFIX+core.canonical(p) or set(p)!={"action","report_digest","sop"} or p["action"]!="REQUEST_REVIEW":
                raise ValueError("COMMAND_SCHEMA")
            sop=p["sop"];sha=p["report_digest"]
            if sop not in public.PLAN or not isinstance(sha,str) or not re.fullmatch(r"[0-9a-f]{64}",sha):raise ValueError("COMMAND_SCOPE")
            r=db.execute("SELECT hour,state FROM hq_outbox WHERE digest=?",(sha,)).fetchone()
            if not r or r["state"]!="SENT" or not r["hour"]<=created<r["hour"]+7200:raise ValueError("REPORT_BINDING")
            # No execution: a proposal is recorded for a future governed Mission mapping.
            with db:db.execute("INSERT INTO hq_proposals VALUES(?,?,?,?,?,'PENDING_GOVERNANCE')",(cid,authorized_actor,sha,sop,created))
            counts["accepted"]+=1
        except (ValueError,KeyError,TypeError,OverflowError):counts["rejected"]+=1
    return counts
def main():
    p=argparse.ArgumentParser();p.add_argument("--db",required=True)
    p.add_argument("action",choices=("prepare","exchange"))
    p.add_argument("--token-file");p.add_argument("--publisher-id",type=int);p.add_argument("--commander-id",type=int)
    a=p.parse_args();os.umask(0o077);path=Path(a.db)
    if not path.is_file():raise ValueError("EXISTING_PUBLIC_DB_REQUIRED")
    with core.locked(path):
        db=core.open_db(path);public.init(db);init(db)
        try:
            if a.action=="prepare":print(prepare(db)["body"]);return
            if not a.token_file or not a.publisher_id or not a.commander_id:p.error("explicit identities and owner-only token file required")
            if os.getenv("QT_HQ_EXCHANGE_ENABLED")!="1":raise ValueError("EXCHANGE_DISABLED")
            # Token file permissions, regular-file ownership checked by local contract.
            api=GitHub(local.read_key(a.token_file).decode("ascii"))
            now=int(time.time());state=publish(db,api,now,a.publisher_id)
            print(core.canonical({"delivery":state,"proposals":ingest(db,api.comments(),now,a.commander_id),
                                  "execution_authorized":False,"llm_calls":0}))
        finally:db.close()
if __name__=="__main__":main()
