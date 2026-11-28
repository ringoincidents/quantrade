import unittest
from tempfile import TemporaryDirectory
from pathlib import Path
from source_archive import archive, check_url, HOST

URL="https://"+HOST+"/-/media/test.txt"
class TestArchive(unittest.TestCase):
    def test_capture(self):
        with TemporaryDirectory() as d:
            m=archive(b"fixture",URL,d)
            self.assertEqual((Path(d)/m["sha256"]).read_bytes(),b"fixture")
            self.assertIsNone(m["original_public_at"])
            self.assertEqual(archive(b"fixture",URL,d)["sha256"],m["sha256"])
    def test_url(self):
        for url in ["http://"+HOST+"/-/media/test.txt","https://example.com/-/media/test.txt","https://"+HOST+"/other"]:
            with self.assertRaises(ValueError): check_url(url)
    def test_corruption(self):
        with TemporaryDirectory() as d:
            m=archive(b"fixture",URL,d)
            (Path(d)/m["sha256"]).write_bytes(b"corrupt")
            with self.assertRaises(ValueError): archive(b"fixture",URL,d)
