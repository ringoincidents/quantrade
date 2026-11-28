"""Bounded verification work lifecycle. Not canonical InstitutionalKernel authority."""
import copy, hashlib, json, secrets, threading, time
from datetime import datetime, timezone

MAX_RUNS=2
COOLDOWN=3600
STATES=("REQUESTED","ASSIGNED","RUNNING","SUBMITTED","REVIEWING","REVIEW_BLOCKED")
FAILED=("REQUESTED","ASSIGNED","RUNNING","FAILED")

def digest(report):
    return hashlib.sha256(json.dumps(report,sort_keys=True,separators=(",",":"),allow_nan=False).encode()).hexdigest()

class Lifecycle:
    def __init__(self,clock=time.time,launch=None):
        self.clock=clock
        self.launch=launch or (lambda target:threading.Thread(target=target,daemon=True).start())
        self.lock=threading.Lock()
        self.runs=0
        self.last_start=None
        self.events=[]
        self.work_id=None
        self.report=None
        self.running=False
    def event(self,state):
        self.events.append({"state":state,"at":datetime.fromtimestamp(self.clock(),timezone.utc).isoformat()})
    def dispatch(self,job):
        with self.lock:
            now=self.clock()
            if self.running or self.runs>=MAX_RUNS or (self.last_start is not None and now-self.last_start<COOLDOWN):
                return False
            self.runs+=1;self.last_start=now;self.running=True
            self.work_id="FUNDAMENTAL-005930-"+secrets.token_hex(8)
            self.events=[];self.report=None
            self.event("REQUESTED");self.event("ASSIGNED");self.event("RUNNING")
        def execute():
            try:
                r=job()
                if r.get("state")!="REPORT_READY":raise ValueError("JOB_BLOCKED")
                with self.lock:
                    self.report=copy.deepcopy(r)
                    self.event("SUBMITTED");self.event("REVIEWING")
                    # Transport QA is not independent research. No approval or paid call.
                    self.event("REVIEW_BLOCKED")
            except Exception:
                with self.lock:
                    self.report=None
                    self.event("FAILED")
            finally:
                with self.lock:self.running=False
        try:self.launch(execute)
        except Exception:
            with self.lock:
                self.report=None;self.running=False;self.event("FAILED")
        return True
    def snapshot(self):
        with self.lock:
            state=self.events[-1]["state"] if self.events else "IDLE"
            return {"schema":"qt-verification-work-v1","work_id":self.work_id,
                "department":"FUNDAMENTAL_RESEARCH","review_department":"COUNTER_RESEARCH",
                "state":state,"events":copy.deepcopy(self.events),
                "runs":self.runs,"max_runs":MAX_RUNS,"cooldown_seconds":COOLDOWN,
                "review_status":"BLOCKED_NO_INDEPENDENT_REVIEW" if state=="REVIEW_BLOCKED" else "NOT_SUBMITTED",
                "report_sha256":digest(self.report) if self.report else None,
                "report":copy.deepcopy(self.report),"durable":False,"approved":False,
                "external_model_called":False,"trade_authorized":False}
