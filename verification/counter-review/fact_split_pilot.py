"""One actual API call per explicitly enabled pilot; synthetic benchmark only."""
import json,os,sqlite3,sys,unittest
from unittest.mock import MagicMock
from datetime import datetime,timezone
from urllib.request import Request,build_opener,ProxyHandler
from urllib.error import HTTPError
from review_pilot import MODEL,INPUT_RATE,OUTPUT_RATE,NoRedirect,sha,cost
from fact_split import CASES,LOGIC_CODES,BASE,facts,packets,evaluate,digest
from research.decision_review.budget_ledger import init,configure_day,reserve,settle
from research.decision_review.decision_review import Case

INPUT_CAP=4096
OUTPUT_CAP=768
BUDGET=2000
def prompt():
    return ("Review ONLY the logical claims in the synthetic cases below. All numerical facts are computed by a separate deterministic program; do not recalculate or issue arithmetic findings. "
            "Use only these definitions: UNSUPPORTED_BUY_CLAIM = unconditional buy instruction without price/valuation or risk rationale; "
            "UNSUPPORTED_CAUSALITY = causal assertion based merely on co-occurrence; UNSUPPORTED_EXTRAPOLATION = guaranteed future outcome inferred from a single observed period; "
            "CONTRADICTS_EVIDENCE = explicit claim inconsistent with supplied facts. Multiple findings allowed. No issue for narrowly supported descriptive claims. "
            "Return JSON object with only key reviews, an array of objects each having id and findings (list of applicable codes or empty list). No prose, approvals, calculations, or external facts. "
            "Cases: "+json.dumps(packets(),separators=(",",":")))
def request(key,p):
    body=json.dumps({"model":MODEL,"messages":[{"role":"user","content":p}],"max_completion_tokens":OUTPUT_CAP,"temperature":0,"response_format":{"type":"json_object"}}).encode()
    if len(body)>12000:raise ValueError("REQUEST_SIZE")
    return Request("https://api.openai.com/v1/chat/completions",data=body,headers={"Content-Type":"application/json","Authorization":"Bearer "+key},method="POST")
def run(env=None,opener=None):
    env=os.environ if env is None else env
    # Execute numeric test even when external model disabled.
    p=prompt()
    out={"numeric_exact":len(CASES),"cases":len(CASES),"benchmark_sha256":digest(CASES),"scope":"SYNTHETIC_ONLY","real_report_reviewed":False,"investment_authorized":False,"durable_ledger":False}
    if env.get("COUNTER_REVIEW_PILOT")!="FACT_SPLIT_ONCE":return dict(out,state="BLOCKED_NOT_ENABLED")
    key=env.get("OPENAI_API_KEY")
    if not key:return dict(out,state="BLOCKED_MISSING_KEY")
    db=sqlite3.connect(":memory:")
    try:
        init(db)
        configure_day(db,datetime.now(timezone.utc).date().isoformat(),max_calls=1,max_micro_usd=BUDGET,policy_ref="fact-split-pilot-2026-11-28")
        ticket=reserve(db,Case("NEW_HYPOTHESIS"),case_id="SYNTHETIC-FACT-SPLIT-001",request_id="FACT-SPLIT-001-R1",provider="OPENAI",model=MODEL,prompt_sha=sha(p.encode()),author_provider="DETERMINISTIC",scope="SYNTHETIC_APPROVED",provider_approved=True,tariff_ref="openai-standard-2026-11-28",max_input=INPUT_CAP,max_output=OUTPUT_CAP,input_micro_per_million=INPUT_RATE,output_micro_per_million=OUTPUT_RATE)
        out.update(provider="OPENAI",model=MODEL,reserved_micro_usd=ticket["reserved_micro_usd"],prompt_sha256=sha(p.encode()))
        settled=False
        try:
            req=request(key,p)
            if opener is None:opener=build_opener(ProxyHandler({}),NoRedirect())
            with opener.open(req,timeout=25) as response:
                if response.status!=200:raise ValueError("HTTP_STATUS")
                raw=response.read(65537)
            if len(raw)>65536:raise ValueError("RESPONSE_SIZE")
            data=json.loads(raw)
            u=data["usage"];i,o=u["prompt_tokens"],u["completion_tokens"]
            if any(type(x) is not int or not 0<=x<=10**7 for x in (i,o)):raise ValueError("USAGE")
            c=cost(i,o)
            state=settle(db,ticket["request_id"],actual_input=i,actual_output=o,reported_micro_usd=c,receipt_sha=sha(raw));settled=True
            out.update(input_tokens=i,output_tokens=o,estimated_micro_usd=c,ledger_state=state,receipt_sha256=sha(raw))
            if state!="REPORTED":return dict(out,state="BLOCKED_USAGE")
            if data["choices"][0]["finish_reason"]!="stop":return dict(out,state="BLOCKED_TRUNCATED")
            try:result=evaluate(json.loads(data["choices"][0]["message"]["content"]))
            except (ValueError,KeyError,TypeError,IndexError):return dict(out,state="BLOCKED_REVIEW_SCHEMA")
            return dict(out,state="PASS_SYNTHETIC_ONLY" if result["exact"]==len(CASES) else "REVIEW_MISMATCH",evaluation=result)
        except Exception as e:
            if not settled:settle(db,ticket["request_id"])
            return dict(out,state="BLOCKED_PROVIDER",error="HTTP_"+str(e.code) if isinstance(e,HTTPError) else type(e).__name__,ledger_state=out.get("ledger_state","UNKNOWN"))
    finally:db.close()

class Tests(unittest.TestCase):
    def expected(self):return {"reviews":[{"id":c["id"],"findings":c["expected"][:]} for c in CASES]}
    def env(self):return {"COUNTER_REVIEW_PILOT":"FACT_SPLIT_ONCE","OPENAI_API_KEY":"fixture"}
    def opener(self,obj=None):
        m=MagicMock()
        r=m.open.return_value.__enter__.return_value
        r.status=200;r.read.return_value=json.dumps({"usage":{"prompt_tokens":1000,"completion_tokens":150},"choices":[{"finish_reason":"stop","message":{"content":json.dumps(self.expected() if obj is None else obj)}}]}).encode()
        return m
    def test_numeric_fixtures(self):
        self.assertEqual(len(packets()),8)
        self.assertEqual(facts(CASES[0]["report"])["operating_margin_pct"],"20.00")
        self.assertEqual(facts(CASES[0]["report"])["numeric_findings"],["OPERATING_MARGIN_MISMATCH"])
        self.assertEqual(facts(CASES[5]["report"])["net_margin_pct"],"-10.00")
    def test_prior_false_findings_not_passed_to_model(self):
        p=packets()
        self.assertNotIn("numeric_findings",p[0])
        self.assertNotIn("expected",p[0])
        self.assertNotIn("reported_operating_margin_pct",p[0]["verified_facts"])
    def test_zero_revenue(self):
        with self.assertRaises(ValueError):facts(dict(BASE,revenue=0))
    def test_invalid_numbers(self):
        for value in (True,float("nan"),"Infinity","xyz"):
            with self.assertRaises(ValueError):facts(dict(BASE,assets=value))
    def test_missing_fields(self):
        with self.assertRaises(ValueError):facts({"assets":1})
    def test_correct_results(self):
        r=evaluate(self.expected());self.assertEqual((r["exact"],r["tp"],r["fp"],r["fn"]),(8,6,0,0))
    def test_miss(self):
        obj=self.expected();obj["reviews"][0]["findings"]=[]
        r=evaluate(obj);self.assertEqual((r["exact"],r["fn"]),(7,1))
    def test_false_positive(self):
        obj=self.expected();obj["reviews"][1]["findings"]=["UNSUPPORTED_BUY_CLAIM"]
        self.assertEqual(evaluate(obj)["fp"],1)
    def test_numeric_override_rejected(self):
        obj=self.expected();obj["reviews"][0]["findings"].append("BALANCE_MISMATCH")
        with self.assertRaises(ValueError):evaluate(obj)
    def test_duplicate_or_missing_id(self):
        obj=self.expected();obj["reviews"][0]["id"]="S02"
        with self.assertRaises(ValueError):evaluate(obj)
    def test_no_authority(self):
        obj=self.expected();obj["approved"]=True
        with self.assertRaises(ValueError):evaluate(obj)
    def test_default_closed(self):
        m=MagicMock();self.assertEqual(run({},m)["state"],"BLOCKED_NOT_ENABLED");m.open.assert_not_called()
    def test_actual_call_contract(self):
        m=self.opener();r=run(self.env(),m);self.assertEqual(r["state"],"PASS_SYNTHETIC_ONLY");self.assertEqual(r["ledger_state"],"REPORTED");self.assertFalse(r["investment_authorized"]);m.open.assert_called_once()
    def test_model_mismatch(self):
        obj=self.expected();obj["reviews"][0]["findings"]=[]
        self.assertEqual(run(self.env(),self.opener(obj))["state"],"REVIEW_MISMATCH")
    def test_no_retry(self):
        m=MagicMock();m.open.side_effect=HTTPError("https://example.invalid",429,"private",{},None)
        self.assertEqual(run(self.env(),m)["ledger_state"],"UNKNOWN");m.open.assert_called_once()
    def test_budget(self):
        self.assertLessEqual(cost(INPUT_CAP,OUTPUT_CAP),BUDGET)
if __name__=="__main__":
    if sys.argv[1:]==["--test"]:unittest.main(argv=[sys.argv[0]])
    elif not sys.argv[1:]:print("FACT_SPLIT "+json.dumps(run(),sort_keys=True),flush=True)
    else:raise SystemExit(2)
