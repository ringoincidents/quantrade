import datetime as dt
import unittest
from server import parse_rates, parse_csv_rates, issue_state, pr_state

class PreviewTests(unittest.TestCase):
    def test_rates_order_and_future(self):
        def row(date, rate):
            return f"<m:properties><d:NEW_DATE>{date}T00:00:00</d:NEW_DATE><d:BC_2YEAR>3.50</d:BC_2YEAR><d:BC_10YEAR>{rate}</d:BC_10YEAR><d:BC_30YEAR>4.50</d:BC_30YEAR></m:properties>"
        data = ('<feed xmlns:m="http://schemas.microsoft.com/ado/2007/08/dataservices/metadata" xmlns:d="http://schemas.microsoft.com/ado/2007/08/dataservices">'+row("2026-11-28","9")+row("2026-11-26","4.1")+row("2026-11-27","4.2")+'</feed>').encode()
        r=parse_rates(data,dt.date(2026,11,27))
        self.assertEqual(r[-1]["rates"]["10Y"],4.2)
        self.assertEqual(r[-2]["date"],"2026-11-26")
    def test_csv(self):
        data = b"Date,2 Yr,10 Yr,30 Yr\n11/27/2026,3.5,4.2,4.5\n11/25/2026,3.4,4.1,4.4\n11/30/2026,9,9,9\n"
        rows=parse_csv_rates(data,dt.date(2026,11,28))
        self.assertEqual(rows[-1]["date"],"2026-11-27")
        self.assertEqual(rows[-1]["rates"]["10Y"],4.2)
        self.assertEqual(rows[-2]["date"],"2026-11-25")
    def test_invalid(self):
        for data in (b"<feed/>",b"<!DOCTYPE x><feed/>"):
            with self.assertRaises(ValueError):
                parse_rates(data,dt.date(2026,11,27))
    def test_public_metadata_only(self):
        self.assertEqual(issue_state(b'{"number":142,"state":"open","body":"not exposed"}'),{"state":"open","updated":None})
        self.assertEqual(pr_state(b'{"number":141,"state":"open","draft":true}'),{"state":"open","draft":True,"updated":None})
        with self.assertRaises(ValueError):
            issue_state(b'{"number":143,"state":"open"}')
if __name__=="__main__":
    unittest.main()
