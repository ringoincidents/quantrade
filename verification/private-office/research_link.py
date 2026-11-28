"""Bounded private research report transport, using existing HMAC primitives.
No broker permissions, trade, private data, public listener, or durable storage.
"""
import hashlib, hmac, http.client, json, re, secrets, time, threading
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from link_transport import key_bytes, mac, HEX, NONCE, SKEW, MAX_NONCES

HOST="f08-entry-monitor.railway.internal"
PORT=8080
PATH="/internal/v1/fundamental/005930"
LIMIT=8192
MAX_AGE=3600
FIELDS={"assets","liabilities","equity","revenue","operating_income","net_income"}
RATIOS={"operating_margin_pct","net_margin_pct","liabilities_to_equity_pct"}

def request_message(stamp,nonce):
    return ("qt-research-v1\nGET\n"+PATH+"\n"+stamp+"\n"+nonce).encode("ascii")

def response_message(stamp,nonce,body):
    return ("qt-research-response-v1\n"+stamp+"\n"+nonce+"\n"+hashlib.sha256(body).hexdigest()).encode("ascii")

class Verifier:
    def __init__(self,key,clock=time.time):
        self.key=key_bytes(key);self.clock=clock;self.used={};self.lock=threading.Lock()
    def verify(self,stamp,nonce,sig):
        if not self.key:return False
        if not re.fullmatch(r"[0-9]{1,12}",stamp or "") or not NONCE.fullmatch(nonce or "") or not HEX.fullmatch(sig or ""):return False
        now=int(self.clock())
        if abs(now-int(stamp))>SKEW or not hmac.compare_digest(mac(self.key,request_message(stamp,nonce)),sig):return False
        with self.lock:
            self.used={k:v for k,v in self.used.items() if v>=now}
            if nonce in self.used or len(self.used)>=MAX_NONCES:return False
            self.used[nonce]=int(stamp)+SKEW
        return True

def validate(obj,clock=time.time):
    if not isinstance(obj,dict) or obj.get("state")!="REPORT_READY":raise ValueError("REPORT_NOT_READY")
    if obj.get("asset_id")!="KRX:005930" or obj.get("period")!="2025-12-31" or obj.get("metric_unit")!="KRW_TRILLION":raise ValueError("IDENTITY")
    if obj.get("independent_review")!="PENDING" or obj.get("accounting_identity_check")!="PASS_WITHIN_1000_KRW":raise ValueError("REVIEW_STATE")
    if any(obj.get(k) is not False for k in ("valuation_authority","portfolio_authority","trade_authority")):raise ValueError("AUTHORITY")
    if not re.fullmatch(r"[0-9]{14}",obj.get("filing_ref","")):raise ValueError("FILING")
    observed=obj.get("observed_at")
    dt=datetime.fromisoformat(observed)
    if dt.tzinfo is None or not 0<=clock()-dt.timestamp()<=MAX_AGE:raise ValueError("STALE")
    published=datetime.fromisoformat(obj["publication_date_eod"])
    if published.tzinfo is None or published>dt:raise ValueError("PUBLICATION")
    clean={k:obj[k] for k in ("state","asset_id","period","metric_unit","independent_review","accounting_identity_check","valuation_authority","portfolio_authority","trade_authority","filing_ref","publication_date_eod","observed_at")}
    for key,fields,places in (("metrics",FIELDS,3),("ratios",RATIOS,2)):
        values=obj.get(key)
        if not isinstance(values,dict) or set(values)!=fields:raise ValueError("SCHEMA")
        if any(not isinstance(v,str) or not re.fullmatch(r"-?[0-9]{1,12}\.[0-9]{"+str(places)+r"}",v) for v in values.values()):raise ValueError("NUMBER")
        clean[key]=dict(values)
    m={k:Decimal(v) for k,v in clean["metrics"].items()}
    if min(m["assets"],m["equity"],m["revenue"])<=0 or m["liabilities"]<0 or abs(m["assets"]-m["equity"]-m["liabilities"])>Decimal("0.002"):raise ValueError("BALANCE")
    # Rounded source amounts: verify reported ratios to bounded display tolerance.
    expected={"operating_margin_pct":m["operating_income"]/m["revenue"]*100,"net_margin_pct":m["net_income"]/m["revenue"]*100,"liabilities_to_equity_pct":m["liabilities"]/m["equity"]*100}
    if any(abs(Decimal(clean["ratios"][k])-v)>Decimal("0.02") for k,v in expected.items()):raise ValueError("RATIO")
    clean["handoff"]="AUTHENTICATED_INTERNAL_REPORT"
    clean["durable_storage"]=False
    clean["raw_retained"]=False
    return clean

def validate_work(w,clock=time.time):
    from work_lifecycle import STATES, FAILED, MAX_RUNS, COOLDOWN, digest
    if not isinstance(w,dict) or w.get("schema")!="qt-verification-work-v1":raise ValueError("WORK_SCHEMA")
    if w.get("department")!="FUNDAMENTAL_RESEARCH" or w.get("review_department")!="COUNTER_RESEARCH":raise ValueError("WORK_OWNER")
    if any(w.get(k) is not False for k in ("durable","approved","external_model_called","trade_authorized")):raise ValueError("WORK_AUTHORITY")
    if type(w.get("runs")) is not int or not 1<=w["runs"]<=MAX_RUNS or w.get("max_runs")!=MAX_RUNS or w.get("cooldown_seconds")!=COOLDOWN:raise ValueError("WORK_LIMIT")
    if not re.fullmatch(r"FUNDAMENTAL-005930-[0-9a-f]{16}",w.get("work_id") or ""):raise ValueError("WORK_ID")
    events=w["events"]
    if not isinstance(events,list) or not 3<=len(events)<=len(STATES):raise ValueError("WORK_EVENTS")
    actual=tuple(e["state"] for e in events)
    if actual not in (STATES[:3],STATES,FAILED):raise ValueError("WORK_SEQUENCE")
    stamps=[datetime.fromisoformat(e["at"]) for e in events]
    if any(d.tzinfo is None or d.timestamp()>clock()+SKEW for d in stamps) or stamps!=sorted(stamps):raise ValueError("WORK_CLOCK")
    state=w["state"]
    if state!=actual[-1] and not (state=="STALE" and actual==STATES):raise ValueError("WORK_STATE")
    expected_review="BLOCKED_NO_INDEPENDENT_REVIEW" if actual==STATES else "NOT_SUBMITTED"
    if w.get("review_status")!=expected_review:raise ValueError("WORK_REVIEW")
    clean={k:w[k] for k in ("schema","work_id","department","review_department","state","events","runs","max_runs","cooldown_seconds","review_status","report_sha256","durable","approved","external_model_called","trade_authorized")}
    if state=="REVIEW_BLOCKED":
        if not HEX.fullmatch(w.get("report_sha256") or "") or digest(w["report"])!=w["report_sha256"]:raise ValueError("WORK_HASH")
        r=validate(w["report"],clock)
        r["workflow"]=clean
        return r
    if w.get("report") is not None or w.get("report_sha256") is not None:raise ValueError("WORK_UNEXPECTED_REPORT")
    return {"state":state,"workflow":clean}

def fetch(key,*,connection_factory=http.client.HTTPConnection,clock=time.time):
    key=key_bytes(key)
    if not key:return {"state":"LINK_KEY_NOT_CONFIGURED"}
    nonce=secrets.token_hex(16);stamp=str(int(clock()));conn=None
    try:
        conn=connection_factory(HOST,PORT,timeout=5)
        conn.request("GET",PATH,headers={"X-QT-Time":stamp,"X-QT-Nonce":nonce,"X-QT-Signature":mac(key,request_message(stamp,nonce))})
        res=conn.getresponse()
        if res.status!=200:return {"state":"WORKER_PENDING_OR_REJECTED"}
        body=res.read(LIMIT+1)
        if len(body)>LIMIT:return {"state":"RESPONSE_TOO_LARGE"}
        sig=res.getheader("X-QT-Response-Signature","")
        if not HEX.fullmatch(sig) or not hmac.compare_digest(sig,mac(key,response_message(stamp,nonce,body))):return {"state":"INVALID_RESPONSE_AUTH"}
        return validate_work(json.loads(body),clock)
    except (ValueError,TypeError,KeyError,InvalidOperation,OverflowError,AttributeError):
        return {"state":"REPORT_INVALID_OR_STALE"}
    except (OSError,http.client.HTTPException):
        return {"state":"WORKER_UNAVAILABLE"}
    finally:
        if conn is not None:conn.close()
