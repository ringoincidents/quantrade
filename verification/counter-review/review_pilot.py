"""One-shot synthetic Counter Research QA. Never authorizes investment or live review."""
import hashlib, json, os, sqlite3, sys, unittest
from datetime import datetime, timezone
from urllib.request import Request, build_opener, ProxyHandler, HTTPRedirectHandler
from urllib.error import HTTPError
from unittest.mock import Mock
from research.decision_review.budget_ledger import init,configure_day,reserve,settle
from research.decision_review.decision_review import Case

MODEL="gpt-4o-mini"
INPUT_CAP=4096
OUTPUT_CAP=256
INPUT_RATE=150000
OUTPUT_RATE=600000
BUDGET=1000
TARIFF="openai-standard-2026-11-28"
CODES=["BALANCE_MISMATCH","OPERATING_MARGIN_MISMATCH","NET_MARGIN_MISMATCH","UNSUPPORTED_BUY_CLAIM"]
EXPECTED={"OPERATING_MARGIN_MISMATCH","UNSUPPORTED_BUY_CLAIM"}
# Deliberately false synthetic financial report, NOT any real company.
FIXTURE={"currency_unit":"fictional units","assets":300,"liabilities":100,"equity":200,"revenue":150,"operating_income":30,"net_income":15,"reported_operating_margin_pct":25,"reported_net_margin_pct":10,"conclusion":"Buy solely because the operating margin is high."}
PROMPT="You are an independent counter-research reviewer of a synthetic QA fixture. Recalculate balance and margins, challenge unsupported investment conclusions. Do not use external information or grant approval. Report all applicable finding codes, no other codes. Return JSON with verdict (REVISION_REQUIRED if any issue else NO_ISSUE_FOUND) and findings (array of unique codes from "+json.dumps(CODES)+"). Fixture: "+json.dumps(FIXTURE,sort_keys=True)
def sha(x):return hashlib.sha256(x).hexdigest()
class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self,*a,**kw):return None
def request(key):
    payload={"model":MODEL,"messages":[{"role":"user","content":PROMPT}],"max_completion_tokens":OUTPUT_CAP,"temperature":0,"response_format":{"type":"json_object"}}
    raw=json.dumps(payload).encode()
    if len(raw)>2048:raise ValueError("REQUEST_SIZE")
    return Request("https://api.openai.com/v1/chat/completions",data=raw,headers={"Content-Type":"application/json","Authorization":"Bearer "+key},method="POST")
def parse_review(raw):
    if not isinstance(raw,dict) or set(raw)!={"verdict","findings"}:raise ValueError("REVIEW_SCHEMA")
    findings=raw["findings"]
    if not isinstance(findings,list) or len(findings)>len(CODES) or any(not isinstance(c,str) or c not in CODES for c in findings) or len(set(findings))!=len(findings):raise ValueError("FINDINGS")
    if raw["verdict"]!=("REVISION_REQUIRED" if findings else "NO_ISSUE_FOUND"):raise ValueError("VERDICT")
    return {"verdict":raw["verdict"],"findings":sorted(findings)}
def cost(i,o):return (i*INPUT_RATE+o*OUTPUT_RATE+999999)//1000000
def run(env=None,opener=None):
    env=os.environ if env is None else env
    # No environment variable means no real provider request; explicit one-shot pilot only.
    if env.get("COUNTER_REVIEW_PILOT")!="SYNTHETIC_ONCE":return {"state":"BLOCKED_NOT_ENABLED"}
    key=env.get("OPENAI_API_KEY")
    if not key:return {"state":"BLOCKED_MISSING_KEY"}
    db=sqlite3.connect(":memory:")
    try:
        init(db)
        configure_day(db,datetime.now(timezone.utc).date().isoformat(),max_calls=1,max_micro_usd=BUDGET,policy_ref="founder-pilot-2026-11-28")
        ticket=reserve(db,Case("NEW_HYPOTHESIS"),case_id="SYNTHETIC-QA-001",request_id="SYNTHETIC-QA-001-R1",provider="OPENAI",model=MODEL,prompt_sha=sha(PROMPT.encode()),author_provider="DETERMINISTIC",scope="SYNTHETIC_APPROVED",provider_approved=True,tariff_ref=TARIFF,max_input=INPUT_CAP,max_output=OUTPUT_CAP,input_micro_per_million=INPUT_RATE,output_micro_per_million=OUTPUT_RATE)
        out={"scope":"SYNTHETIC_ONLY","reserved_micro_usd":ticket["reserved_micro_usd"],"provider":"OPENAI","model":MODEL,"investment_authorized":False,"real_report_reviewed":False,"durable_ledger":False}
        try:
            req=request(key)
            if opener is None:opener=build_opener(ProxyHandler({}),NoRedirect())
            with opener.open(req,timeout=20) as response:
                if response.status!=200:raise ValueError("HTTP_STATUS")
                body=response.read(65537)
            if len(body)>65536:raise ValueError("RESPONSE_SIZE")
            data=json.loads(body)
            usage=data["usage"]
            i,o=usage["prompt_tokens"],usage["completion_tokens"]
            if any(type(n) is not int or n<0 or n>10**7 for n in (i,o)):raise ValueError("USAGE")
            c=cost(i,o)
            receipt=sha(body)
            ledger=settle(db,ticket["request_id"],actual_input=i,actual_output=o,reported_micro_usd=c,receipt_sha=receipt)
            out.update({"input_tokens":i,"output_tokens":o,"estimated_micro_usd":c,"receipt_sha256":receipt,"ledger_state":ledger})
            if ledger!="REPORTED":return dict(out,state="BLOCKED_USAGE")
            try:
                if data["choices"][0]["finish_reason"]!="stop":raise ValueError("TRUNCATED")
                review=parse_review(json.loads(data["choices"][0]["message"]["content"]))
            except (ValueError,KeyError,IndexError,TypeError):
                return dict(out,state="BLOCKED_REVIEW_SCHEMA")
            return dict(out,state="PASS_SYNTHETIC_REVIEW" if set(review["findings"])==EXPECTED and review["verdict"]=="REVISION_REQUIRED" else "REVIEW_MISMATCH",review=review)
        except Exception as e:
            settle(db,ticket["request_id"])
            return dict(out,state="BLOCKED_PROVIDER",error="HTTP_"+str(e.code) if isinstance(e,HTTPError) else type(e).__name__,ledger_state="UNKNOWN")
    finally:db.close()

class Tests(unittest.TestCase):
    def env(self):return {"COUNTER_REVIEW_PILOT":"SYNTHETIC_ONCE","OPENAI_API_KEY":"fixture"}
    def opener(self,findings=None):
        m=Mock()
        r=m.open.return_value.__enter__.return_value
        r.status=200
        r.read.return_value=json.dumps({"usage":{"prompt_tokens":300,"completion_tokens":32},"choices":[{"finish_reason":"stop","message":{"content":json.dumps({"verdict":"REVISION_REQUIRED","findings":sorted(EXPECTED) if findings is None else findings})}}]}).encode()
        return m
    def test_closed(self):
        m=Mock();self.assertEqual(run({},m)["state"],"BLOCKED_NOT_ENABLED");m.open.assert_not_called()
    def test_pass(self):
        m=self.opener();r=run(self.env(),m);self.assertEqual(r["state"],"PASS_SYNTHETIC_REVIEW");self.assertEqual(r["ledger_state"],"REPORTED");self.assertEqual(r["estimated_micro_usd"],65);self.assertFalse(r["investment_authorized"]);m.open.assert_called_once()
    def test_miss(self):
        r=run(self.env(),self.opener(["OPERATING_MARGIN_MISMATCH"]));self.assertEqual(r["state"],"REVIEW_MISMATCH")
    def test_untrusted_code(self):
        r=run(self.env(),self.opener(["APPROVE_BUY"]));self.assertEqual(r["state"],"BLOCKED_REVIEW_SCHEMA")
    def test_no_retry(self):
        m=Mock();m.open.side_effect=HTTPError("https://example.invalid",429,"private",{},None)
        r=run(self.env(),m);self.assertEqual(r["ledger_state"],"UNKNOWN");m.open.assert_called_once()
    def test_authority_rejected(self):
        with self.assertRaises(ValueError):parse_review({"verdict":"APPROVED","findings":[]})
    def test_budget(self):
        self.assertLessEqual(cost(INPUT_CAP,OUTPUT_CAP),BUDGET)
        self.assertLessEqual(len(request("fixture").data),2048)
    def test_input_output_limits(self):
        m=self.opener();r=m.open.return_value.__enter__.return_value
        r.read.return_value=json.dumps({"usage":{"prompt_tokens":4097,"completion_tokens":32}}).encode()
        self.assertEqual(run(self.env(),m)["state"],"BLOCKED_USAGE")
if __name__=="__main__":
    if sys.argv[1:]==["--test"]:unittest.main(argv=[sys.argv[0]])
    elif not sys.argv[1:]:print("COUNTER_REVIEW "+json.dumps(run(),sort_keys=True),flush=True)
    else:raise SystemExit(2)
