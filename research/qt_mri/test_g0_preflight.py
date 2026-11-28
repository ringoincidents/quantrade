import csv
import hashlib
import tempfile
import unittest
from pathlib import Path
from g0_preflight import inspect,FIELDS,Blocked

class PreflightTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        self.manifest={"schema":"qt-mri-g0-package-v1","mode":"SYNTHETIC","track":"BAA_LONG","datasets":[]}
        for sid in ("VIXCLS","DGS10","BAA10Y","SPY","QQQ"):
            price=sid in ("SPY","QQQ")
            spec={"series_id":sid,"file":sid+".csv","source_ref":"fixture:source","rights_evidence_ref":"fixture:rights",
                  "availability_evidence_ref":"fixture:time","revision_evidence_ref":"fixture:revision","revision_policy":"FIRST_KNOWN_ONLY"}
            if price:
                spec.update(price_basis="DISTRIBUTION_AND_SPLIT_ADJUSTED",calendar_evidence_ref="fixture:calendar",adjustment_evidence_ref="fixture:adjustment")
                rows=[[sid,"2020-01-02","100","2020-01-02T21:00:00Z","2020-01-02T21:01:00Z","2020-01-03T00:00:00Z","v1"]]
            else:
                spec["unit"]="INDEX_POINTS" if sid=="VIXCLS" else "PERCENT_POINTS"
                rows=[[sid,"2020-01-02","20","2020-01-02T22:00:00Z","2020-01-03T00:00:00Z","v1"]]
            self.write(spec,rows)
            self.manifest["datasets"].append(spec)
    def tearDown(self):self.tmp.cleanup()
    def write(self,spec,rows):
        p=self.root/spec["file"]
        with p.open("w",newline="") as f:
            w=csv.writer(f);w.writerow(FIELDS["price" if spec["series_id"] in ("SPY","QQQ") else "release"]);w.writerows(rows)
        spec["sha256"]=hashlib.sha256(p.read_bytes()).hexdigest()
    def result(self):return inspect(self.root,self.manifest)
    def reason(self,sid):return next(x.get("reason") for x in self.result()["datasets"] if x["series_id"]==sid)
    def test_fixture_structure_does_not_authorize_g1(self):
        v=self.result();self.assertEqual(v["structure_state"],"STRUCTURE_OK")
        self.assertEqual(v["g0"],"BLOCKED");self.assertFalse(v["g1_authorized"])
    def test_no_credit_substitution(self):
        self.manifest["track"]="HY_SHORT"
        with self.assertRaisesRegex(Blocked,"SERIES_SET_MISMATCH"):self.result()
    def test_hash_mismatch(self):
        (self.root/"VIXCLS.csv").write_text("changed")
        self.assertEqual(self.reason("VIXCLS"),"HASH_MISMATCH")
    def test_missing_rights_evidence(self):
        self.manifest["datasets"][0]["rights_evidence_ref"]=""
        self.assertEqual(self.reason("VIXCLS"),"MISSING_SOURCE_EVIDENCE")
    def test_unknown_publication_and_nonfinite(self):
        s=self.manifest["datasets"][0]
        self.write(s,[["VIXCLS","2020-01-02","20","UNKNOWN","2020-01-03T00:00:00Z","v1"]])
        self.assertEqual(self.reason("VIXCLS"),"INVALID_TIME")
        self.write(s,[["VIXCLS","2020-01-02","NaN","2020-01-02T22:00:00Z","2020-01-03T00:00:00Z","v1"]])
        self.assertEqual(self.reason("VIXCLS"),"INVALID_VALUE")
    def test_price_not_known_before_close(self):
        s=self.manifest["datasets"][3]
        self.write(s,[["SPY","2020-01-02","100","2020-01-02T21:00:00Z","2020-01-02T20:00:00Z","2020-01-03T00:00:00Z","v1"]])
        self.assertEqual(self.reason("SPY"),"PRICE_BEFORE_CLOSE")
    def test_duplicate_observation(self):
        s=self.manifest["datasets"][0];r=["VIXCLS","2020-01-02","20","2020-01-02T22:00:00Z","2020-01-03T00:00:00Z","v1"]
        self.write(s,[r,r]);self.assertEqual(self.reason("VIXCLS"),"DUPLICATE_OBSERVATION")
    def test_real_coverage_is_not_fixture_coverage(self):
        self.manifest["mode"]="RESEARCH_CANDIDATE"
        self.assertEqual(self.reason("SPY"),"COVERAGE_INSUFFICIENT")
    def test_price_basis_not_silently_mixed(self):
        self.manifest["datasets"][3]["price_basis"]="RAW"
        self.assertEqual(self.reason("SPY"),"PRICE_BASIS_UNVERIFIED")
    def test_path_escape(self):
        self.manifest["datasets"][0]["file"]="../VIXCLS.csv"
        self.assertEqual(self.reason("VIXCLS"),"INVALID_FILE_NAME")
