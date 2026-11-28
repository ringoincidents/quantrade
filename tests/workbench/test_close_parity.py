import unittest
from datetime import date,datetime
from decimal import Decimal
from dataclasses import replace
from quantrade.workbench import close_parity as p

class CloseParityTests(unittest.TestCase):
    def setUp(self):
        self.day=date(2026,11,27)
        self.close=datetime.fromisoformat("2026-11-27T15:30:00+09:00")
        self.retrieved=datetime.fromisoformat("2026-11-28T15:00:00+09:00")
        self.now=datetime.fromisoformat("2026-11-28T16:00:00+09:00")
        self.i="KRX:005930"
        self.krx={"OutBlock_1":[{"ISU_CD":"005930","BAS_DD":"20261127","TDD_CLSPRC":"12345"}]}
        self.toss={"result":{"candles":[{"timestamp":"2026-11-27T00:00:00+09:00","currency":"KRW","closePrice":"12345"}]}}
    def primary(self):
        return p.parse_krx_daily(self.krx,instrument=self.i,session=self.day,retrieved_at=self.retrieved,endpoint="stk_bydd_trd")
    def reference(self):
        return p.parse_toss_kr_daily(self.toss,instrument=self.i,session=self.day,retrieved_at=self.retrieved,adjusted=False)
    def cmp(self,a,b):
        return p.compare(a,b,expected_instrument=self.i,expected_session=self.day,scheduled_close=self.close,as_of=self.now)
    def test_exact_match_is_not_authority(self):
        a=self.primary(); b=replace(self.reference(),kind=p.REGULAR)
        r=self.cmp(a,b)
        self.assertEqual(r["state"],"EXACT_MATCH_UNVERIFIED")
        self.assertFalse(r["decision_authorized"])
        self.assertFalse(r["actual_finality_verified"])
        self.assertFalse(r["independent_upstream_verified"])
        self.assertFalse(r["rights_verified"])
        self.assertNotIn("12345",str(r))
    def test_toss_session_definition_unverified(self):
        self.assertEqual(self.cmp(self.primary(),self.reference())["state"],"SESSION_DEFINITION_UNVERIFIED_MATCH")
        self.assertEqual(self.cmp(self.primary(),replace(self.reference(),price=Decimal("12346")))["state"],"SESSION_DEFINITION_UNVERIFIED_MISMATCH")
    def test_exact_mismatch_no_tolerance(self):
        b=replace(self.reference(),kind=p.REGULAR,price=Decimal("12345.000000000001"))
        self.assertEqual(self.cmp(self.primary(),b)["state"],"PRICE_MISMATCH")
    def test_missing_same_provider_and_basis(self):
        a=self.primary()
        self.assertEqual(self.cmp(a,None)["state"],"MISSING_SOURCE")
        self.assertEqual(self.cmp(a,a)["state"],"SAME_PROVIDER")
        self.assertEqual(self.cmp(a,replace(self.reference(),basis="ADJUSTED"))["state"],"CURRENCY_OR_BASIS_MISMATCH")
    def test_identity_time_and_session(self):
        a=self.primary(); b=self.reference()
        self.assertEqual(self.cmp(a,replace(b,instrument="KRX:000660"))["state"],"IDENTITY_OR_SESSION_MISMATCH")
        self.assertEqual(self.cmp(a,replace(b,session=date(2026,11,26)))["state"],"IDENTITY_OR_SESSION_MISMATCH")
        self.assertEqual(self.cmp(a,replace(b,retrieved_at=self.close.replace(hour=14)))["state"],"INVALID_RETRIEVAL_TIME")
        self.assertEqual(self.cmp(a,replace(b,retrieved_at=self.now.replace(hour=17)))["state"],"INVALID_RETRIEVAL_TIME")
    def test_krx_duplicate_or_wrong_date(self):
        self.krx["OutBlock_1"]*=2
        with self.assertRaisesRegex(ValueError,"MISSING_OR_AMBIGUOUS_CLOSE"):
            self.primary()
        self.krx["OutBlock_1"]=[{"ISU_CD":"005930","BAS_DD":"20261126","TDD_CLSPRC":"12345"}]
        with self.assertRaisesRegex(ValueError,"MISSING_OR_AMBIGUOUS_CLOSE"):
            self.primary()
    def test_massive_regular_close_and_adjustment(self):
        q={"status":"OK","symbol":"AAPL","from":"2026-11-27","close":Decimal("123.45"),"afterHours":Decimal("234.56")}
        args=dict(instrument="XNAS:AAPL",session=self.day,retrieved_at=self.retrieved)
        self.assertEqual(p.parse_massive_daily(q,adjusted=False,**args).price,Decimal("123.45"))
        with self.assertRaisesRegex(ValueError,"MARKET_OR_BASIS_MISMATCH"):
            p.parse_massive_daily(q,adjusted=True,**args)
        q["symbol"]="IBM"
        with self.assertRaisesRegex(ValueError,"MISSING_OR_AMBIGUOUS_CLOSE"):
            p.parse_massive_daily(q,adjusted=False,**args)
    def test_toss_us_not_enabled_and_timestamp(self):
        with self.assertRaisesRegex(ValueError,"MARKET_OR_BASIS_MISMATCH"):
            p.parse_toss_kr_daily(self.toss,instrument="XNAS:AAPL",session=self.day,retrieved_at=self.retrieved,adjusted=False)
        self.toss["result"]["candles"][0]["timestamp"]="2026-11-27T00:00:00+00:00"
        with self.assertRaisesRegex(ValueError,"UNVERIFIED_DAILY_TIMESTAMP_CONVENTION"):
            self.reference()
    def test_invalid_numeric_inputs(self):
        for value in (True,1.0,"NaN","0","-1",Decimal("Infinity"),"1.0000000000001"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                p.price(value)
