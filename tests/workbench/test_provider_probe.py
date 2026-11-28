import unittest
from unittest.mock import patch
from quantrade.workbench import provider_probe as p

class ProbeTests(unittest.TestCase):
    def test_krx_match(self):
        row={"BAS_DD":p.DATE.replace("-",""),"ISU_CD":"005930","TDD_CLSPRC":"100000"}
        with patch.object(p,"request_json",return_value=("HTTP_200",{"OutBlock_1":[row]})):
            self.assertEqual(p.krx("stk_bydd_trd","fixture","005930"),"PASS_SCHEMA")
            self.assertEqual(p.krx("stk_bydd_trd","fixture","000000"),"HTTP_200_SCHEMA_OR_SYMBOL_MISMATCH")
    def test_massive_match(self):
        with patch.object(p,"request_json",return_value=("HTTP_200",{"status":"OK","symbol":"AAPL","from":p.DATE,"close":"100.25"})):
            self.assertEqual(p.massive("AAPL","fixture"),"PASS_SCHEMA")
            self.assertEqual(p.massive("IBM","fixture"),"HTTP_200_SCHEMA_OR_SYMBOL_MISMATCH")
    def test_deny(self):
        with patch.object(p,"request_json",return_value=("HTTP_403",None)):
            self.assertEqual(p.krx("stk_bydd_trd","fixture"),"HTTP_403")
            self.assertEqual(p.massive("AAPL","fixture"),"HTTP_403")
    def test_aggregate_exit(self):
        with patch.object(p,"krx",return_value="HTTP_401"), patch.object(p,"massive",return_value="PASS_SCHEMA"), patch("builtins.print") as out:
            self.assertEqual(p.main(),1)
            self.assertTrue(any('"passed": 2' in str(c) for c in out.call_args_list))
        with patch.object(p,"krx",return_value="PASS_SCHEMA"), patch.object(p,"massive",return_value="PASS_SCHEMA"), patch("builtins.print"):
            self.assertEqual(p.main(),0)
    def test_missing(self):
        self.assertEqual(p.request_json("https://example.invalid","AUTH_KEY",""),("KEY_MISSING",None))
    def test_invalid_prices(self):
        for value in [None,"NaN","Infinity","-1","0"]:
            self.assertFalse(p.positive(value))
