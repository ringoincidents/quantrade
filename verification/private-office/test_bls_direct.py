import unittest,json
from datetime import datetime,timezone
from bls_direct import MAP,parse,Cache
NOW=datetime(2026,11,28,12,tzinfo=timezone.utc)
def fixture():
    return {"status":"REQUEST_SUCCEEDED","Results":[{"series":[{"seriesID":k,"data":[{"year":"2026","period":"M10","value":"121" if v!="UNRATE" else "4.1","footnotes":[{"text":"Preliminary."}]},{"year":"2026","period":"M09","value":"110" if v!="UNRATE" else "4.2"},{"year":"2025","period":"M10","value":"100" if v!="UNRATE" else "4.0"}]} for k,v in MAP.items()]}]}
class BLSDirectTests(unittest.TestCase):
    def test_calc_and_identity(self):
        rows=parse(json.dumps(fixture()).encode(),NOW);v={x["id"]:x for x in rows}
        self.assertEqual(len(v),4);self.assertEqual(v["CPIAUCSL"]["mom_pct"],"10.0000")
        self.assertEqual(v["PAYEMS"]["monthly_change_people"],"11000")
        self.assertEqual(v["CPIAUCSL"]["source_series_id"],"CUSR0000SA0")
        self.assertEqual(v["CPIAUCSL"]["footnotes"],["Preliminary."])
    def test_both_shapes(self):
        f=fixture();f["Results"]=f["Results"][0]
        self.assertEqual(len(parse(json.dumps(f).encode(),NOW)),4)
    def test_unknown_and_duplicate(self):
        for key in ("NOT_REQUESTED","CUSR0000SA0L1E"):
            f=fixture();f["Results"][0]["series"][0]["seriesID"]=key
            with self.assertRaises(ValueError):parse(json.dumps(f).encode(),NOW)
    def test_future(self):
        f=fixture();f["Results"][0]["series"][0]["data"][0]["period"]="M12"
        with self.assertRaises(ValueError):parse(json.dumps(f).encode(),NOW)
    def test_failed_and_quota(self):
        calls=[];clock=[0]
        def load(now):
            calls.append(1)
            if len(calls)>1:raise TimeoutError()
            return json.dumps(fixture()).encode()
        c=Cache(load,lambda:clock[0],lambda:NOW)
        self.assertEqual(c.get()["state"],"FETCHED");clock[0]=3600;c.get();self.assertEqual(len(calls),1)
        clock[0]=10800;v=c.get();self.assertEqual(v["state"],"REFRESH_FAILED");self.assertTrue(v["historical_only"]);self.assertEqual(len(v["rows"]),4)
