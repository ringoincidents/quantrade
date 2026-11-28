import unittest
from pipeline import replay
from forecast_ledger import connect

class TestPipeline(unittest.TestCase):
    def test_replay(self):
        rows=[]
        for y in range(2015,2021):
            for q,m in enumerate((1,4,7,10),1):
                endyear=y+(q==4); endmonth=m+3 if q<4 else 1
                rows.append(dict(period=f"{y}Q{q}",unit="REAL_GDP_QOQ_ANNUALIZED_PERCENT",issued_at=f"{y}-{m:02d}-28T00:00:00Z",actual_public_at=f"{endyear}-{endmonth:02d}-20T00:00:00Z",source_sha256="a"*64,vintage="FIRST_RELEASE",actual=2,spf=2,iar=2))
        with connect(":memory:") as db:
            result=replay(db,rows,"2021-02-01T00:00:00Z")
            self.assertEqual(result["n"],20)
            self.assertEqual(len(result["evaluation_ids"]),140)
            self.assertTrue(all(s["mae"]==0 for s in result["scores"].values()))
            count=db.execute("SELECT count(*) FROM events").fetchone()[0]
            replay(db,rows,"2021-02-01T00:00:00Z")
            self.assertEqual(db.execute("SELECT count(*) FROM events").fetchone()[0],count)
            with self.assertRaises(ValueError): replay(db,rows,"2019-01-01T00:00:00Z")
