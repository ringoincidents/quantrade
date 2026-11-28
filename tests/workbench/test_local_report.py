import copy
import json
import sqlite3
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path

from quantrade.workbench.local_report import (
    demo, digest, evaluate, main, render, save_run, utcnow, publish_run, record_local_approval,
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

    def test_rejected_revision_can_be_corrected(self):
        with tempfile.TemporaryDirectory() as tmp:
            save_run(tmp,self.d,evaluate(self.d),utcnow())
            q=copy.deepcopy(self.d["quotes"][0]);q.update(revision=2,price="-1")
            self.d["quotes"].append(q)
            blocked=evaluate(self.d)
            self.assertEqual(self.row()["reason"],"INVALID_PRICE")
            save_run(tmp,self.d,blocked,utcnow())
            with sqlite3.connect(Path(tmp)/"runs.sqlite3") as con:
                self.assertEqual(con.execute("SELECT count(*) FROM inputs WHERE kind='quote'").fetchone()[0],2)
                self.assertEqual(con.execute("SELECT count(*) FROM runs").fetchone()[0],2)
            q["price"]="79"
            save_run(tmp,self.d,evaluate(self.d),utcnow())
            self.assertEqual(self.row()["status"],"REVIEW")
            with sqlite3.connect(Path(tmp)/"runs.sqlite3") as con:
                self.assertEqual(con.execute("SELECT count(*) FROM inputs WHERE kind='quote'").fetchone()[0],3)
            q["price"]="78"
            with self.assertRaisesRegex(ValueError,"IMMUTABLE_INPUT_CONFLICT"):
                save_run(tmp,self.d,evaluate(self.d),utcnow())
            with sqlite3.connect(Path(tmp)/"runs.sqlite3") as con:
                self.assertEqual(con.execute("SELECT count(*) FROM rejected_runs").fetchone()[0],1)
                self.assertEqual(con.execute("SELECT count(*) FROM runs").fetchone()[0],3)

    def test_invalid_revision_does_not_advance_history(self):
        with tempfile.TemporaryDirectory() as tmp:
            q=copy.deepcopy(self.d["quotes"][0]);q.update(revision=9,finality="UNKNOWN")
            self.d["quotes"].append(q)
            save_run(tmp,self.d,evaluate(self.d),utcnow())
            self.assertEqual(self.row()["reason"],"QUOTE_NOT_FINAL")
            self.d["quotes"].pop()
            save_run(tmp,self.d,evaluate(self.d),utcnow())
            self.assertEqual(self.row()["status"],"REVIEW")

    def test_legacy_store_not_silently_migrated_or_shown(self):
        with tempfile.TemporaryDirectory() as tmp:
            db=Path(tmp)/"runs.sqlite3"
            with sqlite3.connect(db) as con:
                con.execute("CREATE TABLE inputs (kind TEXT, identity TEXT, hash TEXT, body TEXT)")
                con.execute("CREATE TABLE runs (id TEXT PRIMARY KEY, report TEXT)")
                con.execute("INSERT INTO runs VALUES (?,?)",(evaluate(self.d)["run_id"],json.dumps(evaluate(self.d))))
            db.chmod(0o600)
            before=db.read_bytes()
            with self.assertRaisesRegex(ValueError,"LEGACY_STORE_QUARANTINED"):
                save_run(tmp,self.d,evaluate(self.d),utcnow())
            self.assertEqual(main(["--store",tmp,"show",evaluate(self.d)["run_id"]]),1)
            self.assertEqual(db.read_bytes(),before)

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

    def test_export_failure_and_retry(self):
        with tempfile.TemporaryDirectory() as tmp:
            r=evaluate(self.d); rid=r["run_id"]
            save_run(tmp,self.d,r,utcnow())
            from quantrade.workbench import local_report as lr
            real_write=lr.atomic_write
            def fail_html(path, data):
                if path.name=="report.html":
                    raise OSError("test interruption")
                real_write(path,data)
            with patch.object(lr,"atomic_write",side_effect=fail_html):
                self.assertEqual(main(["--store",tmp,"show",rid]),1)
            self.assertFalse((Path(tmp)/("report-"+rid)).exists())
            with sqlite3.connect(Path(tmp)/"runs.sqlite3") as con:
                self.assertEqual(con.execute("SELECT state FROM exports WHERE run_id=?",(rid,)).fetchone()[0],"PENDING")
                self.assertEqual(con.execute("SELECT count(*) FROM runs").fetchone()[0],1)
            path=publish_run(tmp,rid)
            self.assertTrue(path.exists())
            self.assertEqual({x.name for x in path.parent.iterdir()},{"report.html","report.json","manifest.json"})
            with sqlite3.connect(Path(tmp)/"runs.sqlite3") as con:
                self.assertEqual(con.execute("SELECT state FROM exports WHERE run_id=?",(rid,)).fetchone()[0],"PUBLISHED")

    def test_reconcile_renamed_bundle_and_reject_tamper(self):
        with tempfile.TemporaryDirectory() as tmp:
            r=evaluate(self.d); rid=r["run_id"]
            save_run(tmp,self.d,r,utcnow())
            path=publish_run(tmp,rid)
            with sqlite3.connect(Path(tmp)/"runs.sqlite3") as con:
                con.execute("UPDATE exports SET state='PENDING',manifest=NULL")
            self.assertEqual(publish_run(tmp,rid),path)
            path.write_text("tampered")
            with self.assertRaisesRegex(ValueError,"EXPORT_BUNDLE_INVALID"):
                publish_run(tmp,rid)

    def test_v2_additive_migration_keeps_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            r=evaluate(self.d);rid=r["run_id"]
            save_run(tmp,self.d,r,utcnow())
            with sqlite3.connect(Path(tmp)/"runs.sqlite3") as con:
                original=con.execute("SELECT report FROM runs WHERE id=?",(rid,)).fetchone()[0]
                con.execute("DROP TABLE exports")
                con.execute("DROP TABLE local_approval_events")
                con.execute("PRAGMA user_version=2")
            self.assertTrue(publish_run(tmp,rid).exists())
            with sqlite3.connect(Path(tmp)/"runs.sqlite3") as con:
                self.assertEqual(con.execute("PRAGMA user_version").fetchone()[0],4)
                self.assertEqual(con.execute("SELECT report FROM runs WHERE id=?",(rid,)).fetchone()[0],original)

    def test_historical_price_never_used_for_decision(self):
        with tempfile.TemporaryDirectory() as tmp:
            save_run(tmp,self.d,evaluate(self.d),utcnow())
            self.d["quotes"].pop(0)
            self.d["as_of"]="2026-11-29T08:00:00+09:00"
            r=evaluate(self.d);rid=r["run_id"]
            save_run(tmp,self.d,r,utcnow())
            path=publish_run(tmp,rid)
            data=json.loads((path.parent/"report.json").read_text())
            row=next(x for x in data["rows"] if x["instrument"]=="XNYS:DEMO_A")
            self.assertEqual(row["status"],"BLOCKED")
            self.assertEqual(row["reason"],"MISSING_QUOTE")
            self.assertIsNone(row["price"])
            self.assertIsNone(row["gap"])
            self.assertEqual(row["last_validated_quote"]["price"],"80")
            self.assertEqual(row["last_validated_quote"]["qualification"],"HISTORICAL_INPUT_ONLY_NOT_VERIFIED_MARKET_DATA")
            self.assertGreater(row["last_validated_quote"]["age_seconds"],86400)
            self.assertIn("참고 전용",path.read_text())
            self.assertEqual(publish_run(tmp,rid),path)

    def manual_fixture(self):
        d=json.loads(json.dumps(demo()).replace("2026-11-","2024-11-").replace("2026-12-","2024-12-"))
        d["mode"]="MANUAL"
        d["approvals"]=[]
        for q in d["quotes"]:
            q["source"]="MANUAL_FIXTURE"
        return d

    def test_local_approval_not_backdated_or_authenticated(self):
        d=self.manual_fixture(); t=d["targets"][0]
        with tempfile.TemporaryDirectory() as tmp:
            from quantrade.workbench import local_report as lr
            with patch.object(lr,"utcnow",return_value="2024-11-29T00:00:00+00:00"):
                approval=record_local_approval(tmp,t,"declared-operator")
                self.assertEqual(record_local_approval(tmp,t,"declared-operator"),approval)
                with self.assertRaisesRegex(ValueError,"LOCAL_APPROVAL_CONFLICT"):
                    record_local_approval(tmp,t,"different")
            d["approvals"].append(approval)
            report=evaluate(d,manual_confirmed=True);rid=report["run_id"]
            save_run(tmp,d,report,utcnow())
            path=publish_run(tmp,rid)
            row=next(r for r in json.loads((path.parent/"report.json").read_text())["rows"] if r["instrument"]==t["instrument"])
            self.assertEqual(row["status"],"BLOCKED")
            self.assertEqual(row["approval_evidence"]["qualification"],"LOCAL_RECORD_AFTER_AS_OF")
            self.assertFalse(row["approval_evidence"]["authenticated"])
            self.assertNotEqual(row["approval_evidence"]["recorded_at"],row["approval_evidence"]["effective_at"])
            d["as_of"]="2024-11-30T08:00:00+09:00"
            report=evaluate(d,manual_confirmed=True)
            save_run(tmp,d,report,utcnow())
            path=publish_run(tmp,report["run_id"])
            row=next(r for r in json.loads((path.parent/"report.json").read_text())["rows"] if r["instrument"]==t["instrument"])
            self.assertEqual(row["status"],"BLOCKED")
            self.assertEqual(row["approval_evidence"]["qualification"],"LOCAL_DECLARATION_RECORDED_UNAUTHENTICATED")

    def test_imported_approval_is_not_local_record(self):
        d=self.manual_fixture();t=d["targets"][0]
        d["approvals"].append(dict(ref=t["approval_ref"],target_hash=digest(t),operator="claimed",approved_at=t["approved_at"]))
        with tempfile.TemporaryDirectory() as tmp:
            report=evaluate(d,manual_confirmed=True)
            save_run(tmp,d,report,utcnow())
            path=publish_run(tmp,report["run_id"])
            row=next(r for r in json.loads((path.parent/"report.json").read_text())["rows"] if r["instrument"]==t["instrument"])
            self.assertEqual(row["approval_evidence"]["qualification"],"LOCAL_RECORD_NOT_FOUND")
            self.assertFalse(row["approval_evidence"]["authenticated"])
            self.assertEqual(row["status"],"BLOCKED")

    def test_html_escape_and_cli(self):
        self.d["quotes"][0]["source"]="<script>alert(1)</script>"
        h=render(evaluate(self.d))
        self.assertNotIn("<script>",h); self.assertIn("&lt;script&gt;",h)
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(main(["--store",tmp,"demo"]),0)
            rid=evaluate(demo())["run_id"]
            self.assertTrue((Path(tmp)/("report-"+rid)/"report.html").is_file())
            self.assertEqual(main(["--store",tmp,"show",rid]),0)
            j=json.loads((Path(tmp)/("report-"+rid)/"report.json").read_text())
            self.assertEqual(j["mode"],"SYNTHETIC")

if __name__=="__main__":
    unittest.main()
