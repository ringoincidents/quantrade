"""Evidence-bound review candidates, with no promotion or decision authority.

This validates provenance and explicit structured claim semantics, NOT the truth of
arbitrary natural-language arguments. Candidate output never becomes Evidence,
a risk veto, an InstitutionalKernel Challenge, or an approval automatically.
"""
import hashlib,json,re
from dataclasses import dataclass

CODES={"UNSUPPORTED_BUY_CLAIM","UNSUPPORTED_CAUSALITY","UNSUPPORTED_EXTRAPOLATION","CONTRADICTS_EVIDENCE"}
MODES={"ASSERTS_CAUSALITY","DENIES_CAUSALITY","HYPOTHESIZES_CAUSALITY","ASSERTS_BUY","ASSERTS_GUARANTEE","DESCRIPTIVE","UNKNOWN"}
KINDS={"CO_OCCURRENCE_ONLY","NO_VALUATION_OR_RISK","SINGLE_PERIOD_ONLY","EXPLICIT_CONTRADICTION","SUPPORT","UNKNOWN"}
ID=re.compile(r"[A-Za-z0-9_.:-]{1,80}")
def require(ok,code):
    if not ok:raise ValueError(code)
def valid_id(v):return isinstance(v,str) and ID.fullmatch(v) is not None
def bounded_text(v):return isinstance(v,str) and 1<=len(v)<=2000 and bool(v.strip())
def canonical(obj):
    return json.dumps(obj,sort_keys=True,separators=(",",":"),ensure_ascii=False,allow_nan=False).encode()
def digest(obj):return hashlib.sha256(canonical(obj)).hexdigest()
@dataclass(frozen=True)
class Claim:
    id:str
    text:str
    mode:str
@dataclass(frozen=True)
class Evidence:
    id:str
    text:str
    kind:str
    claim_id:str

def packet(claims,evidence,*,case_id,scope):
    require(valid_id(case_id),"CASE_ID")
    require(scope in {"SYNTHETIC_ONLY","PUBLIC_CANDIDATE"},"SCOPE")
    require(1<=len(claims)<=16 and 1<=len(evidence)<=64,"PACKET_SIZE")
    require(all(isinstance(c,Claim) and valid_id(c.id) and bounded_text(c.text) and c.mode in MODES for c in claims),"CLAIM_SCHEMA")
    claim_ids={c.id for c in claims}
    require(len(claim_ids)==len(claims),"DUPLICATE_CLAIM")
    require(all(isinstance(e,Evidence) and valid_id(e.id) and bounded_text(e.text) and e.kind in KINDS and e.claim_id in claim_ids for e in evidence),"EVIDENCE_SCHEMA")
    require(len({e.id for e in evidence})==len(evidence),"DUPLICATE_EVIDENCE")
    body={"case_id":case_id,"scope":scope,"claims":[vars(c) for c in claims],"evidence":[vars(e) for e in evidence]}
    return {"body":body,"packet_sha256":digest(body)}

def semantic_check(code,mode,kinds):
    # Structured annotations are supplied by a trusted upstream validator, not LLM.
    # Natural language annotations must be independently verified before real use.
    if mode=="UNKNOWN" or "UNKNOWN" in kinds or "SUPPORT" in kinds:
        return "NEEDS_HUMAN_REVIEW"
    rules={
      "UNSUPPORTED_BUY_CLAIM":("ASSERTS_BUY","NO_VALUATION_OR_RISK"),
      "UNSUPPORTED_CAUSALITY":("ASSERTS_CAUSALITY","CO_OCCURRENCE_ONLY"),
      "UNSUPPORTED_EXTRAPOLATION":("ASSERTS_GUARANTEE","SINGLE_PERIOD_ONLY"),
    }
    if code=="CONTRADICTS_EVIDENCE":
        return "CANDIDATE" if "EXPLICIT_CONTRADICTION" in kinds else "NEEDS_HUMAN_REVIEW"
    expected,kind=rules[code]
    if mode!=expected:
        return "REJECTED_MODE"
    if kind not in kinds:
        return "NEEDS_HUMAN_REVIEW"
    return "CANDIDATE"

def validate(p,response):
    require(isinstance(p,dict) and set(p)=={"body","packet_sha256"},"PACKET_SCHEMA")
    require(digest(p["body"])==p["packet_sha256"],"PACKET_DIGEST")
    b=p["body"]
    # Rebuild to validate even packets read from a file or untrusted transport.
    require(packet([Claim(**c) for c in b["claims"]],[Evidence(**e) for e in b["evidence"]],case_id=b["case_id"],scope=b["scope"])==p,"PACKET_CANONICAL")
    require(isinstance(response,dict) and set(response)=={"packet_sha256","reviews"},"RESPONSE_SCHEMA")
    require(response["packet_sha256"]==p["packet_sha256"],"RESPONSE_BINDING")
    cs={c["id"]:c for c in b["claims"]};es={e["id"]:e for e in b["evidence"]}
    reviews=response["reviews"]
    require(isinstance(reviews,list) and len(reviews)==len(cs),"REVIEW_COVERAGE")
    seen=set();out=[]
    for r in reviews:
        require(isinstance(r,dict) and set(r)=={"claim_id","disposition","findings"},"REVIEW_SCHEMA")
        cid=r["claim_id"];require(valid_id(cid) and cid in cs and cid not in seen,"CLAIM_BINDING");seen.add(cid)
        disp=r["disposition"];fs=r["findings"]
        require(disp in ("CHALLENGE","NO_ISSUE_FOUND","ABSTAIN") and isinstance(fs,list) and len(fs)<=4,"DISPOSITION")
        require(bool(fs)==(disp=="CHALLENGE"),"FINDING_DISPOSITION")
        findings=[];codes=set()
        for f in fs:
            require(isinstance(f,dict) and set(f)=={"code","claim_quote","evidence_ids","reason","limitation"},"FINDING_SCHEMA")
            code=f["code"];require(isinstance(code,str) and code in CODES and code not in codes,"FINDING_CODE");codes.add(code)
            require(bounded_text(f["claim_quote"]) and f["claim_quote"] in cs[cid]["text"],"CLAIM_QUOTE")
            require(bounded_text(f["reason"]) and bounded_text(f["limitation"]),"REASON_LIMITATION")
            refs=f["evidence_ids"]
            require(isinstance(refs,list) and 1<=len(refs)<=8 and all(valid_id(x) and x in es and es[x]["claim_id"]==cid for x in refs),"EVIDENCE_BINDING")
            require(len(set(refs))==len(refs),"EVIDENCE_DUPLICATE")
            # Include ALL bound evidence in conflict check: cannot cherry-pick only adverse rows.
            kinds={e["kind"] for e in es.values() if e["claim_id"]==cid}
            cited={es[x]["kind"] for x in refs}
            status=semantic_check(code,cs[cid]["mode"],kinds)
            if status=="CANDIDATE" and semantic_check(code,cs[cid]["mode"],cited)!="CANDIDATE":
                status="NEEDS_HUMAN_REVIEW"
            findings.append({**f,"status":status})
        out.append({"claim_id":cid,"disposition":disp,"findings":findings})
    return {"schema":"qt_counter_review_candidate_v1","case_id":b["case_id"],"packet_sha256":p["packet_sha256"],"response_sha256":digest(response),"reviews":out,"state":"REVIEW_REQUIRED","annotation_provenance":"UNVERIFIED_UPSTREAM","independent_review_completed":False,"challenge_promotion_authorized":False,"committee_authorized":False,"trade_authorized":False}
