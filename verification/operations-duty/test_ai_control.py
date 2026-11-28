import sqlite3,tempfile,unittest
from unittest.mock import patch
from datetime import datetime,timezone,timedelta
from pathlib import Path
import ai_control as a
from pinned_review import budget_ledger as ledger
from pinned_review.decision_review import Case

class AIControl(unittest.TestCase):
    def setUp(self):
        self.db=sqlite3.connect(":memory:")
        a.init(self.db)
        self.day=datetime.now(timezone.utc).date().isoformat()
    def tearDown(self):self.db.close()
    def cfg(self,daily_calls=2,daily_micro=10000,monthly_calls=2,monthly_micro=10000):
        a.configure_synthetic(self.db,self.day,daily_calls=daily_calls,daily_micro_usd=daily_micro,
          monthly_calls=monthly_calls,monthly_micro_usd=monthly_micro)
    def reserve(self,i,**overrides):
        args=dict(case_id="c"+str(i),request_id="r"+str(i),provider="ANTHROPIC",model="synthetic-model",
          prompt_sha="a"*64,author_provider="OPENAI",scope="SYNTHETIC_APPROVED",provider_approved=True,
          tariff_ref="synthetic-tariff",max_input=1000,max_output=1000,input_micro_per_million=1000000,
          output_micro_per_million=1000000)
        args.update(overrides)
        return a.reserve_synthetic(self.db,Case("NEW_HYPOTHESIS"),**args)
    def test_no_routine_call(self):
        p=a.plan(Case("REGRESSION_TEST"))
        self.assertEqual(p["planned_calls"],0);self.assertFalse(p["actual_call_authorized"])
        self.assertEqual(a.triage("INPUT_UNVERIFIED"),"D0_REPAIR_REQUIRED")
    def test_default_deny(self):
        with self.assertRaises(ValueError):self.reserve(1)
        self.assertFalse(a.plan(Case("NEW_HYPOTHESIS"))["actual_call_authorized"])
    def test_month_cost_atomic(self):
        self.cfg(daily_micro=3000,monthly_micro=3000)
        self.assertEqual(self.reserve(1)["reserved_micro_usd"],2000)
        with self.assertRaises(ValueError):self.reserve(2)
        self.assertEqual(self.db.execute("SELECT count(*) FROM gateway_attempt").fetchone()[0],1)
    def test_month_cap_across_days(self):
        self.day="2026-11-10"
        self.cfg(daily_calls=1,monthly_calls=1)
        with patch.object(ledger,"datetime",wraps=datetime) as clock:
            clock.now.return_value=datetime(2026,11,10,tzinfo=timezone.utc)
            self.reserve(1)
            a.settle_synthetic(self.db,"r1",actual_input=1000,actual_output=1000,reported_micro_usd=2000,receipt_sha="b"*64)
            ledger.configure_day(self.db,"2026-11-11",max_calls=1,max_micro_usd=10000,policy_ref="synthetic.fixture")
            clock.now.return_value=datetime(2026,11,11,tzinfo=timezone.utc)
            with self.assertRaisesRegex(sqlite3.IntegrityError,"MONTH_CALL_LIMIT"):self.reserve(2)
        self.assertEqual(self.db.execute("SELECT count(*) FROM gateway_attempt").fetchone()[0],1)
    def test_cross_day_unknown(self):
        self.day="2026-11-10"
        self.cfg(daily_calls=1,monthly_calls=2)
        with patch.object(ledger,"datetime",wraps=datetime) as clock:
            clock.now.return_value=datetime(2026,11,10,tzinfo=timezone.utc)
            self.reserve(1)
            ledger.configure_day(self.db,"2026-11-11",max_calls=1,max_micro_usd=10000,policy_ref="synthetic.fixture")
            clock.now.return_value=datetime(2026,11,11,tzinfo=timezone.utc)
            with self.assertRaisesRegex(sqlite3.IntegrityError,"UNRECONCILED_PRIOR_USAGE"):self.reserve(2)
    def test_month_cost_trigger(self):
        self.cfg(daily_micro=10000,monthly_micro=10000)
        self.reserve(1)
        with self.db:self.db.execute("UPDATE ai_pilot_month SET max_micro_usd=3000")
        with self.assertRaisesRegex(sqlite3.IntegrityError,"MONTH_COST_LIMIT"):self.reserve(2)
    def test_month_trigger_even_if_day_cap_passes(self):
        self.cfg(daily_calls=2,monthly_calls=2)
        self.reserve(1);a.settle_synthetic(self.db,"r1",actual_input=0,actual_output=0,reported_micro_usd=0,receipt_sha="b"*64)
        # Direct fixture mutation demonstrates monthly trigger independently.
        with self.db:self.db.execute("UPDATE ai_pilot_month SET max_calls=1")
        with self.assertRaisesRegex(sqlite3.IntegrityError,"MONTH_CALL_LIMIT"):self.reserve(2)
        self.assertEqual(self.db.execute("SELECT count(*) FROM gateway_attempt").fetchone()[0],1)
    def test_unknown_blocks(self):
        self.cfg()
        self.reserve(1)
        self.assertEqual(a.settle_synthetic(self.db,"r1"),"UNKNOWN")
        with self.assertRaises(ValueError):self.reserve(2)
    def test_switch_blocks(self):
        self.cfg()
        with self.db:self.db.execute("UPDATE ai_pilot_switch SET enabled=0")
        with self.assertRaisesRegex(sqlite3.IntegrityError,"PILOT_DISABLED"):self.reserve(1)
    def test_no_private_or_live_reservation(self):
        self.cfg()
        with self.assertRaises(ValueError):self.reserve(1,scope="PUBLIC_APPROVED")
        with tempfile.TemporaryDirectory() as tmp:
            d=sqlite3.connect(Path(tmp)/"actual.sqlite")
            try:
                with self.assertRaisesRegex(ValueError,"TEST_DB_ONLY"):a.configure_synthetic(d,self.day,daily_calls=1,daily_micro_usd=1,monthly_calls=1,monthly_micro_usd=1)
            finally:d.close()
    def test_same_provider_not_independent(self):
        self.cfg()
        with self.assertRaisesRegex(ValueError,"INDEPENDENCE_NOT_ESTABLISHED"):self.reserve(1,provider="OPENAI")
if __name__=="__main__":unittest.main()
