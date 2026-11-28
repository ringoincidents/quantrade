"""Local, synthetic-only report acknowledgement / review-request ingress.
No remote transport, GPT identity, execution authority or paid calls.
A signature authenticates possession of a local pilot key, not a person.
"""
import hashlib
import hmac
import json
import os
import re
import stat

FIELDS={"id","action","issued_at","expires_at","report_digest","sop","signature"}
ACTIONS={"ACK_REPORT","REQUEST_REVIEW"}
MAX_TTL=3600
SCHEMA="""
CREATE TABLE IF NOT EXISTS command_receipts(
 id TEXT PRIMARY KEY, received_at INTEGER NOT NULL,
 action TEXT NOT NULL, sop TEXT, report_digest TEXT NOT NULL,
 envelope_digest TEXT NOT NULL, state TEXT NOT NULL);
"""
def canonical(value):
    return json.dumps(value,sort_keys=True,separators=(",",":"),allow_nan=False).encode()
def sign(payload,key):
    return hmac.new(key,canonical(payload),hashlib.sha256).hexdigest()
def read_key(path):
    with open(path,"rb") as f:
        st=os.fstat(f.fileno())
        if not stat.S_ISREG(st.st_mode) or st.st_uid!=os.getuid() or stat.S_IMODE(st.st_mode)!=0o600:
            raise ValueError("KEY_FILE_PERMISSIONS")
        key=f.read(129)
    if not 32<=len(key)<=128: raise ValueError("KEY_LENGTH")
    return key
def read_envelope(path):
    with open(path,"rb") as f: data=f.read(8193)
    if len(data)>8192: raise ValueError("ENVELOPE_TOO_LARGE")
    def unique(pairs):
        out={}
        for k,v in pairs:
            if k in out: raise ValueError("DUPLICATE_FIELD")
            out[k]=v
        return out
    return json.loads(data,object_pairs_hook=unique)
def accept(db,envelope,key,now,allowed_sops):
    if not 32<=len(key)<=128:raise ValueError("KEY_LENGTH")
    if not isinstance(envelope,dict) or set(envelope)!=FIELDS:raise ValueError("FIELDS")
    ident,action,sop=envelope["id"],envelope["action"],envelope["sop"]
    issued,expires=envelope["issued_at"],envelope["expires_at"]
    report_sig=envelope["report_digest"]; signature=envelope["signature"]
    if not isinstance(ident,str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,80}",ident):
        raise ValueError("ID")
    if not isinstance(action,str) or action not in ACTIONS:raise ValueError("ACTION")
    if action=="ACK_REPORT" and sop is not None:raise ValueError("SOP")
    if action=="REQUEST_REVIEW" and (not isinstance(sop,str) or sop not in allowed_sops):raise ValueError("SOP")
    if type(issued) is not int or type(expires) is not int or not issued<=now<expires or not 0<expires-issued<=MAX_TTL:
        raise ValueError("TTL")
    if any(not isinstance(v,str) or not re.fullmatch(r"[0-9a-f]{64}",v) for v in (report_sig,signature)):
        raise ValueError("DIGEST")
    payload={k:v for k,v in envelope.items() if k!="signature"}
    if not hmac.compare_digest(sign(payload,key),signature):raise ValueError("SIGNATURE")
    env_digest=hashlib.sha256(canonical(envelope)).hexdigest()
    with db:
        existing=db.execute("SELECT envelope_digest FROM command_receipts WHERE id=?",(ident,)).fetchone()
        if existing:
            if existing[0]!=env_digest:raise ValueError("ID_CONFLICT")
            return "ALREADY_RECORDED"
        report=db.execute("SELECT body FROM reports WHERE digest=?",(report_sig,)).fetchone()
        if not report or hashlib.sha256(canonical(json.loads(report[0]))).hexdigest()!=report_sig:
            raise ValueError("REPORT_MISSING_OR_CORRUPT")
        state="ACKNOWLEDGED" if action=="ACK_REPORT" else "REVIEW_REQUESTED"
        db.execute("INSERT INTO command_receipts VALUES(?,?,?,?,?,?,?)",(ident,now,action,sop,report_sig,env_digest,state))
    return state
