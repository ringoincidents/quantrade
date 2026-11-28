import unittest
from tempfile import TemporaryDirectory
from pathlib import Path
from contextlib import closing
from forecast_ledger import connect, forecast, read
from ledger_backup import snapshot, restore

class TestBackup(unittest.TestCase):
    def test_roundtrip(self):
        with TemporaryDirectory() as d, closing(connect(":memory:")) as db:
            p=Path(d)
            with db:
                key=forecast(db,"2020Q1","2020-02-01T00:00:00Z","test","1",2,"a"*64)
            sha=snapshot(db,p/"backup")
            restore(p/"backup",p/"restored",sha)
            with closing(connect(p/"restored")) as recovered:
                self.assertEqual(read(recovered,key,"forecast")["value"],2)
            with self.assertRaises(FileExistsError): restore(p/"backup",p/"restored",sha)
            with self.assertRaises(ValueError): restore(p/"backup",p/"bad","0"*64)
    def test_pending(self):
        with TemporaryDirectory() as d, closing(connect(":memory:")) as db:
            forecast(db,"2020Q1","2020-02-01T00:00:00Z","test","1",2,"a"*64)
            with self.assertRaises(ValueError): snapshot(db,Path(d)/"backup")
