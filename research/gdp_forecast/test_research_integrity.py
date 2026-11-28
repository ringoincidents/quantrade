import unittest
from unittest.mock import patch
from tempfile import TemporaryDirectory
from pathlib import Path
import json
from forecast_ledger import connect
from pipeline import replay
from run_research import run

def fixture():
    return [dict(period=f"{2019+i//4}Q{i%4+1}",unit="REAL_GDP_QOQ_ANNUALIZED_PERCENT",issued_at=f"{2019+i//4}-{1+3*(i%4):02d}-28T00:00:00Z",actual_public_at=f"{2019+(i+1)//4}-{1+3*((i+1)%4):02d}-20T00:00:00Z",source_sha256="a"*64,vintage="FIRST_RELEASE",actual=2,spf=2,iar=2) for i in range(6)]

class TestIntegrity(unittest.TestCase):
    def test_rollback(self):
        db=connect(":memory:")
        try:
            with patch("pipeline.ledger.evaluate",side_effect=RuntimeError("injected failure")):
                with self.assertRaises(RuntimeError): replay(db,fixture(),"2022-01-01T00:00:00Z")
            self.assertEqual(db.execute("SELECT count(*) FROM events").fetchone()[0],0)
        finally: db.close()
    def test_bad_evidence(self):
        with TemporaryDirectory() as d:
            p=Path(d)
            (p/("a"*64)).write_bytes(b"wrong")
            (p/"input.json").write_text(json.dumps(fixture()))
            with self.assertRaisesRegex(ValueError,"Evidence hash mismatch"):
                run(p/"input.json",p,p/"ledger.sqlite","2022-01-01T00:00:00Z")
            self.assertFalse((p/"ledger.sqlite").exists())
