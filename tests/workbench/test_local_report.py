import copy
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from quantrade.workbench.local_report import (
    demo, digest, evaluate, main, render, save_run, utcnow,
)

class LocalReportTests(unittest.TestCase):
    def setUp(self):
        self.d = demo()

    def row(self, symbol="DEMO_A", **kwargs):
        return next(r for r in evaluate(self.d, **kwargs)["rows"] if r["instrument"]=="XNYS:"+symbol)

    def reapprove(self, index=0):
        self.d["approvals"][index]["target_hash"] = digest(self.d["targets"][index])

    def test_demo_and_boundary(self):
        r = evaluate(self.d)
        self.assertEqual([x["status"] for x in r["rows"]],["REVIEW","BLOCKED","WAIT"])
        self.assertEqual(self.row()["entry_price"],"80.00")
        self.assertEqual(self.row()["gap"],"0")
        self.assertEqual(self.row("DEMO_B")["gap"],"0.040625")
        self.assertEqual(self.row("DEMO_C")["reason"],"MISSING_QUOTE")
        self.assertEqual(r["data_health"],"INCOMPLETE")

    def test_weekend_expected_early_close(self):
        self.d["as_of"]="2026-11-29T18:00:00+09:00"
        self.assertEqual(self.row()["status"],"REVIEW")
        self.d["quotes"][0]["observed_at"]="2026-11-27T16:00:00-05:00"
        self.assertEqual(self.row()["reason"],"CLOSE_TIME_MISMATCH")

    def test_wrong_session(self):
        self.d["quotes"][0]["session_date"]="2026-11-25"
        self.assertEqual(self.row()["reason"],"SESSION_MISMATCH")

    def test_currency(self):
        self.d["quotes"][0]["currency"]="KRW"
        self.assertEqual(self.row()["reason"],"CURRENCY_MISMATCH")

    def test_unknown_finality(self):
        self.d["quotes"][0]["finality"]="UNKNOWN"
        self.assertEqual(self.row()["reason"],"QUOTE_NOT_FINAL")

    def test_basis(self):
        self.d["quotes"][0]["price_basis"]="ADJUSTED"
        self.assertEqual(self.row()["reason"],"PRICE_BASIS_MISMATCH")

    def test_corporate_action(self):
        self.d["quotes"][0]["corporate_action_status"]="UNKNOWN"
        self.assertEqual(self.row()["reason"],"CORPORATE_ACTION_UNVERIFIED")

    def test_availability(self):
        self.d["quotes"][0]["retrieved_at"]="2026-11-30T13:10:00-05:00"
        self.assertEqual(self.row()["reason"],"FUTURE_QUOTE_REVISION")

    def test_expiry(self):
        self.d["targets"][0]["expires_at"]=self.d["as_of"]
        self.reapprove()
        self.assertEqual(self.row()["reason"],"TARGET_NOT_CURRENT")

    def test_revoked(self):
        self.d["revocations"].append(dict(ref="r1",operator="test",target_hash=digest(self.d["targets"][0]),revoked_at=self.d["as_of"]))
        self.assertEqual(self.row()["reason"],"TARGET_NOT_CURRENT")

    def test_duplicate_target(self):
        t = copy.deepcopy(self.d["targets"][0]); t["version"]="v2"
        self.d["targets"].append(t)
        self.assertEqual(self.row()["reason"],"DUPLICATE_APPROVAL")

    def test_modified_target_no_approval(self):
        self.d["targets"][0]["value"]="99"
        self.assertEqual(self.row()["reason"],"APPROVAL_MISMATCH")

    def test_duplicate_quote(self):
        self.d["quotes"].append(copy.deepcopy(self.d["quotes"][0]))
        self.assertEqual(self.row()["reason"],"AMBIGUOUS_QUOTE")

    def test_latest_revision(self):
        q=copy.deepcopy(self.d["quotes"][0]);q.update(revision=2,price="81")
        self.d["quotes"].append(q)
        self.assertEqual(self.row()["status"],"WAIT")

    def test_decimal_no_float(self):
        self.d["quotes"][0]["price"]=80.0
        self.assertEqual(self.row()["reason"],"INVALID_DECIMAL")
        self.d["quotes"][0]["price"]="80.000000000001"
        self.assertEqual(self.row()["status"],"WAIT")

    def test_manual_confirmation(self):
        self.d["mode"]="MANUAL"
        with self.assertRaisesRegex(ValueError,"MANUAL_CONFIRMATION_REQUIRED"):
            evaluate(self.d)
        for q in self.d["quotes"]:
            q["source"]="MANUAL_FIXTURE"
        # Move the fictitious dates to a completed historical period, independent of runner clock.
        self.d=json.loads(json.dumps(self.d).replace("2026-11-","2024-11-").replace("2026-12-","2024-12-"))
        for i,a in enumerate(self.d["approvals"]):
            a["operator"]="test-operator"
            self.reapprove(i)
        self.assertEqual(self.row(manual_confirmed=True)["status"],"BLOCKED")
        self.assertEqual(self.row(manual_confirmed=True)["reason"],"SESSION_FRESHNESS_UNVERIFIED")
        self.d["as_of"]="2024-12-15T18:00:00+09:00"
        self.assertEqual(self.row(manual_confirmed=True)["reason"],"SESSION_FRESHNESS_UNVERIFIED")

    def test_malformed_session_existing_store(self):
        with tempfile.TemporaryDirectory() as tmp:
            save_run(tmp,self.d,evaluate(self.d),utcnow())
            self.d["expected_sessions"]["XNYS"]=[]
            with self.assertRaisesRegex(ValueError,"INVALID_SESSION_MAP"):
                evaluate(self.d)
            path=Path(tmp)/"bad.json"
            path.write_text(json.dumps(self.d))
            self.assertEqual(main(["--store",tmp,"run",str(path)]),1)
            with sqlite3.connect(Path(tmp)/"runs.sqlite3") as con:
                self.assertEqual(con.execute("SELECT count(*) FROM runs").fetchone()[0],1)

    def test_persist_repeat_and_conflict(self):
        with tempfile.TemporaryDirectory() as tmp:
            r=evaluate(self.d)
            save_run(tmp,self.d,r,utcnow());save_run(tmp,self.d,r,utcnow())
            with sqlite3.connect(Path(tmp)/"runs.sqlite3") as con:
                self.assertEqual(con.execute("SELECT count(*) FROM runs").fetchone()[0],1)
            self.d["quotes"][0]["price"]="81"
            with self.assertRaisesRegex(ValueError,"IMMUTABLE_INPUT_CONFLICT"):
                save_run(tmp,self.d,evaluate(self.d),utcnow())

    def test_persist_revocation_cannot_disappear(self):
        with tempfile.TemporaryDirectory() as tmp:
            r=dict(ref="r1",operator="test",target_hash=digest(self.d["targets"][0]),revoked_at=self.d["as_of"])
            self.d["revocations"].append(r)
            save_run(tmp,self.d,evaluate(self.d),utcnow())
            self.d["revocations"].clear()
            with self.assertRaisesRegex(ValueError,"MISSING_PRIOR_REVOCATION"):
                save_run(tmp,self.d,evaluate(self.d),utcnow())

    def test_prior_quote_revision_cannot_disappear(self):
        with tempfile.TemporaryDirectory() as tmp:
            q=copy.deepcopy(self.d["quotes"][0]);q.update(revision=2,price="81")
            self.d["quotes"].append(q)
            save_run(tmp,self.d,evaluate(self.d),utcnow())
            self.d["quotes"].pop()
            with self.assertRaisesRegex(ValueError,"MISSING_PRIOR_QUOTE_REVISION"):
                save_run(tmp,self.d,evaluate(self.d),utcnow())

    def test_prior_active_target_cannot_disappear(self):
        with tempfile.TemporaryDirectory() as tmp:
            save_run(tmp,self.d,evaluate(self.d),utcnow())
            self.d["targets"].pop(0)
            with self.assertRaisesRegex(ValueError,"MISSING_PRIOR_ACTIVE_TARGET"):
                save_run(tmp,self.d,evaluate(self.d),utcnow())

    def test_revoked_target_can_be_replaced(self):
        with tempfile.TemporaryDirectory() as tmp:
            save_run(tmp,self.d,evaluate(self.d),utcnow())
            t=self.d["targets"][0]
            self.d["revocations"].append(dict(ref="r1",operator="test",target_hash=digest(t),revoked_at=self.d["as_of"]))
            replacement=copy.deepcopy(t);replacement.update(version="v2",approval_ref="new-approval",value="101")
            self.d["targets"][0]=replacement
            self.d["approvals"].append(dict(ref="new-approval",target_hash=digest(replacement),operator="SYNTHETIC",approved_at=replacement["approved_at"]))
            save_run(tmp,self.d,evaluate(self.d),utcnow())
            self.assertEqual(self.row()["target_version"],"v2")

    def test_html_escape_and_cli(self):
        self.d["quotes"][0]["source"]="<script>alert(1)</script>"
        h=render(evaluate(self.d))
        self.assertNotIn("<script>",h); self.assertIn("&lt;script&gt;",h)
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(main(["--store",tmp,"demo"]),0)
            rid=evaluate(demo())["run_id"]
            self.assertTrue((Path(tmp)/("report-"+rid+".html")).is_file())
            self.assertEqual(main(["--store",tmp,"show",rid]),0)
            j=json.loads((Path(tmp)/("report-"+rid+".json")).read_text())
            self.assertEqual(j["mode"],"SYNTHETIC")

if __name__=="__main__":
    unittest.main()
